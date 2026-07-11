# drf-toon

Native [TOON](https://toonformat.dev/) (Token Oriented Object Notation) parser and renderer for [Django REST Framework](https://www.django-rest-framework.org/).

TOON is a token-efficient serialization format designed for LLM contexts. It can result in **30–60% fewer tokens** than JSON. 

`drf-toon` is built on [`toons`](https://github.com/alesanfra/toons), a high-performance Rust implementation meant to mimic the native python `json` package.

## Compatibility

`drf-toon` supports **Django 5.2 LTS** on **Python 3.10–3.13**, matching
Django's own [support matrix](https://docs.djangoproject.com/en/stable/faq/install/#what-python-version-can-i-use-with-django).
Every supported Python version is exercised in CI.

| Django  | Python                 |
| ------- | ---------------------- |
| 5.2 LTS | 3.10, 3.11, 3.12, 3.13 |

Support for additional Django releases can be added later by extending the CI
matrix.

## Installation

```bash
pip install drf-toon
```

## Usage

Add the parser and renderer to your DRF settings:

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "drf_toon.parsers.TOONParser",
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "drf_toon.renderers.TOONRenderer",
        "rest_framework.renderers.JSONRenderer",
    ],
}
```

Or enable them per-view:

```python
from rest_framework.views import APIView
from rest_framework.response import Response

from drf_toon.parsers import TOONParser
from drf_toon.renderers import TOONRenderer


class UserView(APIView):
    parser_classes = [TOONParser]
    renderer_classes = [TOONRenderer]

    def get(self, request):
        return Response({"name": "Alice", "age": 30})
```

Both classes use the `application/toon` media type. Send requests with
`Content-Type: application/toon` to parse, and `Accept: application/toon`
(or `?format=toon`) to render.

## Development

Install the dev dependencies and run the checks with uv:

```bash
uv sync --dev

uv run ruff check .          # lint
uv run ruff format .         # format
uv run ruff format --check . # format check (CI)
uv run mypy                  # type check
uv run pytest                # tests + coverage
```

Optionally install the git hooks:

```bash
uv run pre-commit install
```

## License

MIT

