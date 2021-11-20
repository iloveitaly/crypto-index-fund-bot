import json

from django.core.management.base import BaseCommand, CommandError

from users.models import User


class Command(BaseCommand):
    help = "Exports a user information as a set of environment variables"

    def add_arguments(self, parser):
        parser.add_argument("user_id", type=int)

    def handle(self, *args, **options):
        user_id = options["user_id"]
        user = User.objects.get(id=user_id).bot_user()

        if not user:
            raise CommandError('User "%s" does not exist' % user_id)

        print(
            f"""
# user ID {user.id} for user {user.name}
USER_BINANCE_API_KEY="{user.binance_api_key}"
USER_BINANCE_SECRET_KEY="{user.binance_secret_key}"
USER_EXTERNAL_PORTFOLIO='{json.dumps(user.external_portfolio)}'
USER_PREFERENCES='{json.dumps(user.preferences)}'
        """
        )
