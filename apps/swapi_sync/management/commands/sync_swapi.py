from django.core.management.base import BaseCommand

from apps.swapi_sync.services.sync import run_full_sync


class Command(BaseCommand):
    help = "Synchronise the local catalog (films, starships, characters) from SWAPI."

    def handle(self, *args, **options):
        self.stdout.write("Starting SWAPI sync...")
        result = run_full_sync()

        self.stdout.write(self.style.SUCCESS(f"Films synced: {result.films_synced}"))
        self.stdout.write(self.style.SUCCESS(f"Starships synced: {result.starships_synced}"))
        self.stdout.write(self.style.SUCCESS(f"Characters synced: {result.characters_synced}"))

        if result.errors:
            self.stdout.write(self.style.WARNING(f"{len(result.errors)} record(s) failed to sync:"))
            for error in result.errors:
                self.stdout.write(self.style.WARNING(f"  - {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("Sync completed with no errors."))
