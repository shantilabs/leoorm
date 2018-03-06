import unittest

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    def handle(self, *args, **options):
        testsuite = unittest.TestLoader().discover(settings.BASE_DIR)
        unittest.TextTestRunner(verbosity=1).run(testsuite)
