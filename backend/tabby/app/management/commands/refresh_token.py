from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Regenerate a sync user's token and print the new value on stdout. "
        "The previous token is invalidated immediately. Status messages go "
        "to stderr so stdout can be piped: "
        "TOKEN=$(./manage.sh refresh_token alice)"
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, username, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {username!r} does not exist.") from exc

        token = user.set_new_token()
        user.save()

        self.stderr.write(
            self.style.WARNING(
                f"rotated sync token for {username!r} (id={user.pk}); "
                "the previous token is now invalid."
            )
        )
        self.stdout.write(token)
