import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.api import api


class Command(BaseCommand):
    help = "Export the Django Ninja OpenAPI schema to a JSON file (defaults to /frontend/openapi.json)."

    def default_output(self) -> Path:
        # settings.BASE_DIR points at /backend; its parent is the monorepo root.
        return Path(settings.BASE_DIR).parent / "frontend" / "openapi.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Destination path for openapi.json. Defaults to the frontend directory.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"]).resolve() if options["output"] else self.default_output()
        output.parent.mkdir(parents=True, exist_ok=True)

        schema = api.get_openapi_schema()
        output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")

        self.stdout.write(self.style.SUCCESS(f"OpenAPI schema exported to {output}"))
