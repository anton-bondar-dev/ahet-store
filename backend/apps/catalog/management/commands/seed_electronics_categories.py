"""Seed a realistic, deep electronics category tree.

Idempotent: categories are upserted by slug, so re-running never duplicates.
The two pre-existing flat categories are reused as leaves of the new tree
(matched by their existing slugs), so every existing product keeps its category
FK untouched — no remapping, no data loss, the PROTECT relation is never hit.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category

# Tree definition: (name, slug, [children]). Slugs `noutbuki` and
# `mobilni-telefoni` intentionally match the existing rows so they are reused.
TREE = [
    (
        "Комп'ютери та ноутбуки",
        "kompiutery-ta-noutbuky",
        [
            (
                "Ноутбуки",
                "noutbuki",  # existing → reused (keeps its 7 products)
                [
                    ("Ігрові ноутбуки", "igrovi-noutbuki", []),
                    ("Ультрабуки", "ultrabuky", []),
                ],
            ),
            (
                "Комп'ютерні комплектуючі",
                "kompiuterni-komplektuiuchi",
                [
                    ("Відеокарти", "videokarty", []),
                    ("Процесори", "protsesory", []),
                    ("Оперативна пам'ять", "operatyvna-pamyat", []),
                    ("Накопичувачі SSD", "ssd-nakopychuvachi", []),
                    (
                        "Клавіатури та миші",
                        "klaviaturi-ta-myshi",
                        [
                            ("Клавіатури", "klaviaturi", []),
                            (
                                "Комп'ютерні миші",
                                "kompiuterni-myshi",
                                [
                                    ("Комп'ютерні миші Logitech", "myshi-logitech", []),
                                    ("Комп'ютерні миші A4Tech", "myshi-a4tech", []),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            ("Монітори", "monitory", []),
        ],
    ),
    (
        "Смартфони та телефони",
        "smartfony-ta-telefony",
        [
            ("Мобільні телефони", "mobilni-telefoni", []),  # existing → reused (5 products)
            (
                "Аксесуари для телефонів",
                "aksesuary-dlia-telefoniv",
                [
                    ("Чохли", "chokhly", []),
                    ("Захисне скло", "zakhysne-sklo", []),
                    ("Зарядні пристрої", "zaryadni-prystroi", []),
                ],
            ),
        ],
    ),
    (
        "Аудіо",
        "audio",
        [
            (
                "Навушники",
                "navushnyky",
                [
                    ("Бездротові навушники", "bezdrotovi-navushnyky", []),
                    ("Провідні навушники", "providni-navushnyky", []),
                ],
            ),
            ("Портативні колонки", "portatyvni-kolonky", []),
            ("Домашня акустика", "domashnia-akustyka", []),
        ],
    ),
    (
        "ТВ та відео",
        "tv-ta-video",
        [
            ("Телевізори", "televizory", []),
            ("Проектори", "proektory", []),
        ],
    ),
]


class Command(BaseCommand):
    help = "Populate a deep electronics category tree (idempotent, non-destructive)."

    def handle(self, *args, **options):
        with transaction.atomic():
            created, reused = self._build(TREE, parent=None, created=0, reused=0)
            # Recompute every path/depth from the final parent links in one pass.
            Category.rebuild_paths()

        total = Category.objects.count()
        max_depth = max(
            (c.depth for c in Category.objects.all()), default=0
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Category tree ready: {total} categories, "
                f"max depth {max_depth} (+1 = {max_depth + 1} levels). "
                f"{created} created, {reused} reused."
            )
        )

    def _build(self, nodes, parent, created, reused):
        for name, slug, children in nodes:
            slug = slug or slugify(name, allow_unicode=True)
            category, was_created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            if was_created:
                created += 1
            else:
                reused += 1
            # Re-parent (safe on re-run); save() maintains path/depth.
            if category.parent_id != (parent.pk if parent else None):
                category.parent = parent
                category.save()
            created, reused = self._build(children, category, created, reused)
        return created, reused
