from django.core.management.base import BaseCommand

from ingestion.services import run_source
from sources.models import Source


class Command(BaseCommand):
    help = "Run one source now, even if it is disabled."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--limit", type=int,
                            help="Stop after this many records (testing).")

    def handle(self, *args, **options):
        source = Source.objects.get(slug=options["slug"])
        run = run_source(source, limit=options["limit"])
        self.stdout.write(
            f"Run {run.pk}: {run.status} | complete={run.complete} | seen={run.seen_count} "
            f"new={run.new_count} changed={run.changed_count} removed={run.removed_count} "
            f"failed={run.failed_count}"
        )
        if run.error_summary:
            self.stdout.write(run.error_summary)
