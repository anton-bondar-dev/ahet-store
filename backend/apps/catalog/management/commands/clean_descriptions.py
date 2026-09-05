"""Strip CSS/HTML wreckage that the store parser left inside product descriptions.

The scraper flattened the vendor pages to text without dropping <style> blocks
or stray tag names, so descriptions can open with things like

    @media (max-width: 720px) td img @media (max-width: 900px) { EVOLVE — ...
    li:last-child PlayStation 5 Slim 1TB — ...

Only leading noise is peeled off token by token; after that, any surviving
@media rule or bare brace is removed anywhere in the text. Real prose is left
untouched. Idempotent — running it twice changes nothing.

    python manage.py clean_descriptions [--dry-run]
"""

import re

from django.core.management.base import BaseCommand

from apps.catalog.models import Product

# One leading junk token: an @media rule, a brace, a CSS declaration, a
# pseudo-selector, or a bare HTML tag name left stranded by the scraper.
LEADING_JUNK = re.compile(
    r"^\s*(?:"
    r"@media\s*\([^)]*\)"                                    # @media (max-width: 720px)
    r"|[{},+>~*]"                                              # braces and selector combinators
    r"|[a-z-]+\s*:\s*[^;{}]+;"                                # max-width: 720px;
    r"|[a-z]*:?(?:first|last|nth|only|t)-(?:child|of-type)(?:\([^)]*\))?"   # p:first-child, t-child
    r"|(?:td|tr|th|img|p|li|ul|ol|div|span|a|br|table|tbody|thead|figure|h[1-6])\b"
    r")",
    re.IGNORECASE,
)
STRAY_MEDIA = re.compile(r"@media\s*\([^)]*\)", re.IGNORECASE)


def clean(text: str) -> str:
    out = text or ""
    while True:
        m = LEADING_JUNK.match(out)
        if not m:
            break
        out = out[m.end():]
    out = STRAY_MEDIA.sub(" ", out)
    out = out.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", out).strip()


class Command(BaseCommand):
    help = "Remove scraper CSS/HTML artifacts from product descriptions."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        changed = 0
        for p in Product.objects.all().only("id", "title", "description"):
            new = clean(p.description or "")
            if new != (p.description or ""):
                changed += 1
                if changed <= 5:
                    self.stdout.write(f"  {p.title[:46]}")
                    self.stdout.write(f"    before: {(p.description or '')[:80]!r}")
                    self.stdout.write(f"    after:  {new[:80]!r}")
                if not dry:
                    p.description = new
                    p.save(update_fields=["description"])
        verb = "would clean" if dry else "cleaned"
        self.stdout.write(self.style.SUCCESS(f"{verb} {changed} product description(s)."))
