import pytest
from django.conf import settings


def pytest_configure(config):
    settings.configure(
        DEBUG=True,
        USE_TZ=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "django.contrib.staticfiles",
            "rest_framework",
            "drf_spectacular",
            "drf_toon",
        ],
        ROOT_URLCONF="tests.urls",
        REST_FRAMEWORK={
            "DEFAULT_PARSER_CLASSES": [
                "drf_toon.parsers.TOONParser",
                "rest_framework.parsers.JSONParser",
            ],
            "DEFAULT_RENDERER_CLASSES": [
                "drf_toon.renderers.TOONRenderer",
                "rest_framework.renderers.JSONRenderer",
            ],
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()

