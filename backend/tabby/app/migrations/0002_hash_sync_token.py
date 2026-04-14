import hashlib

from django.db import migrations, models


def hash_existing_tokens(apps, schema_editor):
    User = apps.get_model("app", "User")
    for user in User.objects.all():
        cleartext = getattr(user, "config_sync_token", None)
        if cleartext:
            user.config_sync_token_hash = hashlib.sha256(
                cleartext.encode("ascii")
            ).hexdigest()
            user.save(update_fields=["config_sync_token_hash"])


def noop(apps, schema_editor):
    # Reverse path: existing hashes cannot be turned back into cleartext.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="config_sync_token_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.RunPython(hash_existing_tokens, noop),
        migrations.RemoveField(
            model_name="user",
            name="config_sync_token",
        ),
    ]
