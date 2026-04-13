from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = 'Create the initial superadmin account'

    def add_arguments(self, parser):
        parser.add_argument('--email',    required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--name',     default='Super Admin')

    def handle(self, *args, **options):
        email = options['email']
        if User.objects.filter(email=email).exists():
            self.stdout.write(f'User {email} already exists.')
            return
        User.objects.create_user(
            email=email,
            full_name=options['name'],
            password=options['password'],
            role='superadmin',
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Superadmin {email} created.'))
