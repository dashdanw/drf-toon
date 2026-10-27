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

Until `drf-toon` is published to PyPI, install it directly from the git
repository:

```bash
pip install git+https://github.com/dashdanw/drf-toon.git
```

Or, with uv:

```bash
uv add git+https://github.com/dashdanw/drf-toon.git
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

## Security notes

- **Request size:** `TOONParser` reads the whole body into memory. Like DRF's own parsers it
  does not cap the size, so set a body limit in your reverse proxy.
- **Charset:** only text charsets are accepted. Compression "charsets" such as `zlib` or `bz2`
  are rejected with a 400, and invalid bytes also return a 400.
- **Depth limits:** `toons` crashes the process on extremely deep documents, so
  `TOONParser.max_indent` (default 2000 leading spaces) and `TOONRenderer.max_depth`
  (default 128 levels) reject them first. Both can be overridden in a subclass.
- **Rendering:** values are normalized the way `JSONRenderer` does it before reaching `toons`
  (UUIDs, dates, `Decimal`, sets, `bytes`, non-string keys). Integers beyond 64 bits are
  rendered as strings so they keep their precision. `NaN` and `Infinity` render as `null`,
  as the TOON spec requires.
- **Parsing numbers:** `toons` turns integers beyond 64 bits into floats and out-of-range
  floats into `inf`. Validate numeric fields with a DRF serializer.

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
uv run pre-commit install --install-hooks
```

This wires up both a **pre-commit** hook (autofix + format) and a **pre-push**
hook that blocks the push if the code is not properly linted/formatted.

## License

MIT
