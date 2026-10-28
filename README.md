# drf-toon

Native [TOON](https://toonformat.dev/) (Token Oriented Object Notation) parser and renderer for [Django REST Framework](https://www.django-rest-framework.org/).

TOON is a token-efficient serialization format designed for LLM contexts. It can result in **30–60% fewer tokens** than JSON.

`drf-toon` is built on [`toon-format`](https://github.com/toon-format/toon-python), the official pure-Python TOON implementation, which follows the interface of the standard `json` module.

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

Or, with uv:

```bash
uv add drf-toon
```

## Usage

Add the parser and renderer to your DRF settings:

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "drf_toon.parsers.TOONParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "drf_toon.renderers.TOONRenderer",
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

DRF answers `Accept: */*` with the first renderer, so list `JSONRenderer`
first to keep JSON the default and serve TOON only when it is requested.

The renderer encodes values through DRF's JSON encoder first, so `UUID`,
`datetime`, `date` and `Decimal` values render as they do in JSON. `None`
renders an empty body (like `JSONRenderer`), and `{}` renders a single
newline, which is the same empty document but keeps DRF from dropping the
`Content-Type` header.

## Security notes

- **Request size:** `TOONParser` rejects bodies larger than Django's `DATA_UPLOAD_MAX_MEMORY_SIZE`
  (2.5 MiB by default) with a 413, reading at most one byte past the limit. Django itself only
  applies this setting to `request.body`, which DRF never reads, so JSON bodies are not capped
  unless you add a limit of your own. `toon-format` is pure Python, so an uncapped TOON body costs
  far more CPU and memory than the same JSON; a 4 MB document of empty list items takes about a
  second and 250 MB to parse. Set the limit to what your endpoints need and also cap bodies in
  your reverse proxy. `None` disables the check.
- **Charset:** only text charsets are accepted. Compression "charsets" such as `zlib` or `bz2`
  are rejected with a 400, and invalid bytes also return a 400.
- **Malformed input:** documents that `toon-format` rejects (duplicate keys, out-of-range or
  oversized numbers, excessive nesting, wrong declared array lengths) return a 400.
- **Rendering:** values are encoded through DRF's JSON encoder first, so circular references,
  non-finite floats and unsupported types raise an error instead of rendering silently.

## Performance

`toon-format` is pure Python, so it is slower than the Rust `toons` package that versions up to
0.2.0 used. As a rough guide, 10,000 small records take about 90 ms to render and 110 ms to
parse. Consider this when serving very large responses.

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
