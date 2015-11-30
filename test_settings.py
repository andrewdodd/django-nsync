SECRET_KEY = 'fake-key'


INSTALLED_APPS = (
    'django.contrib.contenttypes',
)

# THIRD_PARTY_APPS = (
#     'rest_framework',
#     'rest_framework.authtoken',
#     'django_extensions',
#     'polymorphic',
#     'mptt',
# )

# PROJECT_APPS = (
#     'core',
#     'integration',
#     'devices',
#     'siteassets',
#     'spatial',
#
# )


PROJECT_APPS = (
    'nsync',
    'tests',
)

INSTALLED_APPS += PROJECT_APPS
# INSTALLED_APPS += THIRD_PARTY_APPS

# MIDDLEWARE_CLASSES = (
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# )
#


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/tmp/integration_test.db',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
