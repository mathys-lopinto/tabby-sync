from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError


class Command(BaseCommand):
    help = (
        "Create a sync user and print its freshly generated token on stdout. "
        "Status messages go to stderr so stdout can be piped: "
        "TOKEN=$(./manage.sh create_sync_user alice)"
    )

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--email",
            default="",
            help="Optional email address to store on the user.",
        )

    def handle(self, username, email, **options):
        User = get_user_model()
        try:
            user = User(username=username, email=email)
            user.set_unusable_password()
            user.save()
        except IntegrityError as exc:
            raise CommandError(f"User {username!r} already exists.") from exc

        token = getattr(user, "_just_generated_token", None)
        if not token:
            raise CommandError("User was created but no cleartext token was captured.")

        self.stderr.write(self.style.SUCCESS(f"created sync user {username!r} (id={user.pk})"))
        self.stdout.write(token)
