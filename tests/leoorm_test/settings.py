import copy
import os

from django.utils.log import DEFAULT_LOGGING

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'sar(86uqs1viw!8v_$4^j7cz&9my8c-6!7=i!-5qdebp(ku2xp'
DEBUG = True

ALLOWED_HOSTS = ['*']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'leoorm_test',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'leoorm_test.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'leoorm_test.wsgi.application'

# psql
# CREATE DATABASE leoorm_test;
# CREATE USER leoorm_test;
# ALTER USER leoorm_test PASSWORD 'leoorm_test';
# GRANT ALL ON DATABASE leoorm_test TO leoorm_test;
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'leoorm_test',
        'USER': 'leoorm_test',
        'PASSWORD': 'leoorm_test',
        'HOST': 'localhost',
        'PORT': '',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'

LOGGING = copy.deepcopy(DEFAULT_LOGGING)
LOGGING.setdefault('formatters', {}).update({
    'simple': {
        'format': u'%(levelname)-8s [%(asctime)s] %(message)s',
    },
})

LOGGING['handlers']['console'].update({
    'level': 'DEBUG',
    'filters': [],
    'formatter': 'simple',
})

LOGGING['handlers']['stdout'] = {
    'level': 'DEBUG',
    'class': 'logging.StreamHandler',
}

LOGGING['loggers'] = {
    # 'leoorm': {
    #     'handlers': ['console'],
    #     'level': 'DEBUG',
    # },
    # 'django.db.backends': {
    #     'handlers': ['console'],
    #     'level': 'DEBUG',
    # },
}
