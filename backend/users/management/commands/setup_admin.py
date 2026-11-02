from django.core.management.base import BaseCommand, CommandError

from core.constants import ADMIN
from users.models import User


class Command(BaseCommand):
    help = "Create the first ADMIN user (use --skip-if-exists for idempotent deploy scripts)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--skip-if-exists", action="store_true", help="Do nothing if any user already exists.")
        parser.add_argument("--force", action="store_true", help="Create the admin even if users already exist.")

    def handle(self, *args, **opts):
        if User.objects.exists() and not opts["force"]:
            if opts["skip_if_exists"]:
                self.stdout.write("Users already exist; skipping admin creation.")
                return
            raise CommandError("Users already exist. Use --force to add another admin.")
        if len(opts["password"]) < 8:
            raise CommandError("Password must be at least 8 characters.")
        user = User.objects.create_user(opts["email"], opts["password"], role=ADMIN, is_staff=True)
        self.stdout.write(self.style.SUCCESS(f"Admin created: {user.email}"))
