import sys

import django
from django.conf import settings
from django.test.utils import get_runner

def setup_env():
    sys.path.append('./src/')
    try:

        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'nsync',
                'tests',
            ],
        )

        setup = django.setup()

    except ImportError:
        import traceback
        traceback.print_exc()
        raise ImportError('To fix this error, sort out the imports')


def run_tests(*test_args):
    if not test_args:
        test_args = ['tests']

    setup_env()
    # Run tests
    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    failures = test_runner.run_tests(test_args)

    sys.exit(failures)


if __name__ == '__main__':
    run_tests(*sys.argv[1:])
