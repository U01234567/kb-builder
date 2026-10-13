"""python manage.py review: review the answers in kb.xlsx in your browser, on this computer only."""

import threading
import webbrowser

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from kb import project
from kb.management.commands.preflight import check


class Command(BaseCommand):
    """python manage.py review [--port 8765]"""

    help = "Open the review app for kb.xlsx in your browser (this computer only)."

    def add_arguments(self, parser):
        """--port changes the port, when 8765 is taken."""
        parser.add_argument("--port", type=int, default=8765)

    def handle(self, *args, port, **options):
        """Check the workbook, then serve the app on 127.0.0.1 and open it in the browser."""
        check(self, project.load(settings.PROJECT_DIR), with_materials=False)
        url = f"http://127.0.0.1:{port}/"
        self.stdout.write(f"Review app: {url}  (Ctrl+C stops it)")
        threading.Timer(1.5, webbrowser.open, [url]).start()
        call_command("runserver", f"127.0.0.1:{port}", use_reloader=False)
