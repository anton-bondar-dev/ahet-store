"""TEMPORARY store parser — populates the catalog from a store URL via JSON-LD.

    python manage.py parse_store "https://some-shop.example/category" --limit 40

Strategy: fetch the page, pull every <script type="application/ld+json"> block,
and harvest schema.org Product objects (whether embedded directly, inside an
ItemList, or under an @graph). For each product we create/update a Product,
download its images into the gallery, and seed random trending counters so the
Trending Engine has data immediately.

NOTE: This command is a one-off data-population tool and is meant to be deleted
once the database is seeded. It intentionally keeps everything self-contained.
"""

import random
import re
from decimal import Decimal, InvalidOperation
from json import JSONDecodeError, loads
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DEFAULT_CATEGORY = "Імпортовані товари"
MAX_IMAGES_PER_PRODUCT = 6
REQUEST_TIMEOUT = 20


class Command(BaseCommand):
    help = (
        "TEMPORARY: parse products from a store URL (schema.org JSON-LD) and "
        "populate the database. Remove once the catalog is seeded."
    )

    def add_arguments(self, parser):
        parser.add_argument("url", help="Store listing or product page URL")
        parser.add_argument(
            "--limit", type=int, default=50, help="Max products to import"
        )
        parser.add_argument(
            "--category",
            type=str,
            default=None,
            help="Force every parsed product into this category name",
        )
        parser.add_argument(
            "--follow",
            action="store_true",
            help="If the page only lists product URLs, fetch each to read its JSON-LD",
        )

    # -- top-level flow -------------------------------------------------------
    def handle(self, *args, **opts):
        url = opts["url"]
        limit = opts["limit"]
        self.stdout.write(self.style.MIGRATE_HEADING(f"Fetching {url} …"))

        html = self._fetch(url)
        blobs = self._extract_jsonld(html)
        self.stdout.write(f"   found {len(blobs)} JSON-LD block(s)")

        products = self._collect_products(blobs)
        if not products and opts["follow"]:
            products = self._follow_item_urls(blobs, url, limit)

        if not products:
            raise CommandError(
                "No schema.org Product data found in the page's JSON-LD. "
                "Try a product or category page, or pass --follow."
            )

        products = products[:limit]
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Importing {len(products)} product(s)…")
        )

        forced_category = None
        if opts["category"]:
            forced_category = self._get_category(opts["category"])

        saved = skipped = 0
        for raw in products:
            try:
                if self._save_product(raw, url, forced_category):
                    saved += 1
                else:
                    skipped += 1
            except Exception as exc:  # never let one bad product abort the run
                skipped += 1
                name = raw.get("name") if isinstance(raw, dict) else "?"
                self.stdout.write(self.style.ERROR(f"❌ Failed: {name} — {exc}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. Saved {saved}, skipped {skipped}.")
        )

    # -- fetching + JSON-LD extraction ---------------------------------------
    def _fetch(self, url: str) -> bytes:
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"Could not fetch {url}: {exc}")
        # Return raw bytes and let BeautifulSoup detect the encoding from the
        # <meta charset>/BOM — requests defaults text/* to Latin-1 when the
        # server omits a charset, which would mangle Cyrillic product names.
        return resp.content

    def _extract_jsonld(self, html: bytes) -> list:
        soup = BeautifulSoup(html, "html.parser")
        blobs = []
        for tag in soup.find_all("script", type="application/ld+json"):
            raw = tag.string or tag.get_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            try:
                blobs.append(loads(raw))
            except JSONDecodeError:
                # Some sites emit slightly malformed JSON (trailing commas, HTML
                # entities). Best-effort cleanup, then skip if still invalid.
                cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
                try:
                    blobs.append(loads(cleaned))
                except JSONDecodeError:
                    self.stdout.write(
                        self.style.WARNING("   ⚠ skipped an invalid JSON-LD block")
                    )
        return blobs

    def _collect_products(self, blobs: list) -> list:
        """Walk every JSON-LD blob and gather all schema.org Product objects,
        wherever they sit (top level, @graph, ItemList/itemListElement)."""
        found: list = []
        seen: set = set()

        def is_product(node) -> bool:
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            return any(isinstance(x, str) and "Product" in x for x in types)

        def walk(node):
            if isinstance(node, dict):
                if is_product(node):
                    key = node.get("name") or node.get("sku") or id(node)
                    if key not in seen:
                        seen.add(key)
                        found.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for blob in blobs:
            walk(blob)
        return found

    def _follow_item_urls(self, blobs: list, base_url: str, limit: int) -> list:
        """Fallback: an ItemList that only carries product URLs. Fetch each page
        (bounded by --limit) and read its own JSON-LD Product."""
        urls: list = []

        def walk(node):
            if isinstance(node, dict):
                if node.get("@type") == "ListItem":
                    target = node.get("url") or node.get("item")
                    if isinstance(target, dict):
                        target = target.get("url") or target.get("@id")
                    if isinstance(target, str):
                        urls.append(urljoin(base_url, target))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for blob in blobs:
            walk(blob)

        products: list = []
        for link in dict.fromkeys(urls):  # dedupe, keep order
            if len(products) >= limit:
                break
            self.stdout.write(f"   ↳ following {link}")
            try:
                products.extend(self._collect_products(self._extract_jsonld(self._fetch(link))))
            except CommandError:
                continue
        return products

    # -- persistence ----------------------------------------------------------
    def _save_product(self, raw: dict, page_url: str, forced_category) -> bool:
        name = (raw.get("name") or "").strip()
        if not name:
            return False

        price = self._to_decimal(self._extract_price(raw))
        if price is None:
            self.stdout.write(self.style.WARNING(f"⚠ No price, skipped: {name}"))
            return False

        category = forced_category or self._category_for(raw)
        slug = self._unique_slug(name)
        description = self._clean_text(raw.get("description") or "")
        sku = self._safe_sku(raw.get("sku") or raw.get("mpn"))

        created = False
        with transaction.atomic():
            product, created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": name,
                    "category": category,
                    "price": price,
                    "description": description,
                    "sku": sku,
                    "stock": random.randint(3, 60),
                    "is_active": True,
                },
            )
            if not created:
                # Refresh the mutable bits; keep counters/images as they are.
                product.title = name
                product.price = price
                product.description = description
                product.save(update_fields=["title", "price", "description"])
            else:
                # Seed a realistic funnel so the Trending Engine has data now.
                views = random.randint(50, 5000)
                carts = random.randint(0, views // 4)
                purchases = random.randint(0, carts)
                product.views_count = views
                product.cart_adds_count = carts
                product.purchases_count = purchases
                product.save(
                    update_fields=[
                        "views_count", "cart_adds_count", "purchases_count"
                    ]
                )

        # Download images only when the product has no gallery yet.
        image_count = 0
        if not product.gallery.exists():
            image_count = self._save_images(product, self._image_urls(raw, page_url))

        tag = "Saved" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {tag}: {name}  ({price} ₴, {image_count} img, "
                f"cat «{category.name}»)"
            )
        )
        return True

    def _save_images(self, product: Product, urls: list) -> int:
        count = 0
        for position, url in enumerate(urls[:MAX_IMAGES_PER_PRODUCT]):
            try:
                resp = requests.get(
                    url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                if not resp.content:
                    continue
                filename = self._image_filename(url, product.slug, position)
                ProductImage.objects.create(
                    product=product,
                    image=ContentFile(resp.content, name=filename),
                    position=position,
                )
                count += 1
            except (requests.RequestException, OSError) as exc:
                self.stdout.write(
                    self.style.WARNING(f"   ⚠ image failed ({url}): {exc}")
                )
        return count

    # -- category helpers -----------------------------------------------------
    def _category_for(self, raw: dict):
        cat = raw.get("category")
        if isinstance(cat, dict):
            cat = cat.get("name")
        if isinstance(cat, list) and cat:
            cat = cat[-1]
        name = (cat or "").strip() if isinstance(cat, str) else ""
        return self._get_category(name or DEFAULT_CATEGORY)

    def _get_category(self, name: str):
        category, _ = Category.objects.get_or_create(
            slug=slugify(name, allow_unicode=True) or "imported",
            defaults={"name": name},
        )
        return category

    # -- field extraction / parsing ------------------------------------------
    def _extract_price(self, raw: dict):
        offers = raw.get("offers")
        candidates = offers if isinstance(offers, list) else [offers]
        for offer in candidates:
            if not isinstance(offer, dict):
                continue
            for key in ("price", "lowPrice", "highPrice"):
                if offer.get(key) not in (None, ""):
                    return offer[key]
            spec = offer.get("priceSpecification")
            if isinstance(spec, dict) and spec.get("price") not in (None, ""):
                return spec["price"]
        # Some feeds put price directly on the product.
        return raw.get("price")

    def _to_decimal(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return Decimal(str(round(value, 2)))
        s = re.sub(r"[^0-9.,]", "", str(value))
        if "," in s and "." in s:
            s = s.replace(",", "")  # comma = thousands separator
        elif "," in s:
            s = s.replace(",", ".")  # comma = decimal separator
        try:
            value = Decimal(s)
            return value if value > 0 else None
        except (InvalidOperation, ValueError):
            return None

    def _image_urls(self, raw: dict, page_url: str) -> list:
        node = raw.get("image")
        urls: list = []

        def add(item):
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                candidate = item.get("url") or item.get("contentUrl")
                if candidate:
                    urls.append(candidate)

        if isinstance(node, list):
            for item in node:
                add(item)
        else:
            add(node)

        # Absolutize relative URLs, dedupe, keep only http(s).
        absolute = []
        for u in dict.fromkeys(urls):
            full = urljoin(page_url, u)
            if urlparse(full).scheme in ("http", "https"):
                absolute.append(full)
        return absolute

    def _clean_text(self, value: str) -> str:
        # Descriptions often contain HTML — strip it to plain text.
        text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
        return text[:5000]

    # -- misc helpers ---------------------------------------------------------
    def _unique_slug(self, name: str) -> str:
        base = slugify(name, allow_unicode=True) or "product"
        base = base[:230]
        slug = base
        i = 2
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"
            i += 1
        return slug

    def _safe_sku(self, value):
        if not value:
            return None
        sku = str(value).strip()[:50]
        # sku is unique; drop it rather than hit an IntegrityError on collision.
        if not sku or Product.objects.filter(sku=sku).exists():
            return None
        return sku

    def _image_filename(self, url: str, slug: str, position: int) -> str:
        path = urlparse(url).path
        ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp", "gif", "avif"):
            ext = "jpg"
        return f"{slug[:60]}-{position}.{ext}"
