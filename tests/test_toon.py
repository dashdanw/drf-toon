"""Unit tests for the TOON parser and renderer.

The tests exercise both classes against a shared set of sample payloads (see
``tests/factories.py``) covering strings, numbers, booleans, null, lists and
nested/mixed structures.
"""

from __future__ import annotations

import io
import uuid
import zlib
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import toon_format
from rest_framework.exceptions import ParseError

from drf_toon.parsers import RequestEntityTooLarge, TOONParser
from drf_toon.renderers import TOONRenderer

from .factories import SAMPLE_PAYLOADS

# One pytest parameter per sample payload, each labelled with its readable id.
PAYLOAD_PARAMS = [pytest.param(payload.value, id=payload.id) for payload in SAMPLE_PAYLOADS]

# ``None`` means "no data" to DRF, so the renderer emits an empty body (like ``JSONRenderer``)
# instead of a ``null`` document; it is covered by ``test_render_returns_empty_body_for_no_data``.
RENDER_PARAMS = [
    pytest.param(payload.value, id=payload.id)
    for payload in SAMPLE_PAYLOADS
    if payload.id != "none"
]


def _make_stream(value: object) -> io.BytesIO:
    """Serialize ``value`` to TOON bytes and wrap it in a byte stream."""
    return io.BytesIO(toon_format.dumps(value).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #
class TestTOONRenderer:
    @pytest.mark.parametrize("value", RENDER_PARAMS)
    def test_render_matches_toon_format_dumps(self, value):
        renderer = TOONRenderer()

        rendered = renderer.render(value)

        assert isinstance(rendered, bytes)
        assert rendered == (toon_format.dumps(value).encode(renderer.charset) or b"\n")

    @pytest.mark.parametrize("value", RENDER_PARAMS)
    def test_render_is_parseable_back(self, value):
        renderer = TOONRenderer()

        rendered = renderer.render(value)

        assert toon_format.loads(rendered.decode(renderer.charset)) == value

    def test_render_encodes_types_toon_format_cannot_serialize(self):
        renderer = TOONRenderer()
        pk = uuid.uuid4()

        rendered = renderer.render(
            {
                "id": pk,
                "at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
                "on": date(2026, 1, 2),
                "amount": Decimal("1.50"),
            }
        )

        assert toon_format.loads(rendered.decode(renderer.charset)) == {
            "id": str(pk),
            "at": "2026-01-02T03:04:05Z",
            "on": "2026-01-02",
            "amount": 1.5,
        }

    def test_render_empty_object_is_a_non_empty_document(self):
        rendered = TOONRenderer().render({})

        assert rendered == b"\n"
        assert toon_format.loads(rendered.decode()) == {}

    def test_render_returns_empty_body_for_no_data(self):
        assert TOONRenderer().render(None) == b""

    def test_non_string_keys_are_coerced_like_json(self):
        rendered = TOONRenderer().render({1: "a", 1.5: "b", None: "c"})

        assert toon_format.loads(rendered.decode()) == {"1": "a", "1.5": "b", "null": "c"}

    def test_integers_beyond_64_bits_keep_precision(self):
        rendered = TOONRenderer().render({"n": 2**100})

        assert toon_format.loads(rendered.decode()) == {"n": 2**100}

    def test_unsupported_key_raises(self):
        with pytest.raises(TypeError):
            TOONRenderer().render({(1, 2): "a"})

    def test_circular_reference_raises(self):
        data: dict = {}
        data["self"] = data

        with pytest.raises(ValueError, match="ircular"):
            TOONRenderer().render(data)

    def test_extremely_deep_data_raises_instead_of_crashing(self):
        data: dict = {}
        node = data
        for _ in range(100_000):
            node["a"] = {}
            node = node["a"]

        with pytest.raises(RecursionError):
            TOONRenderer().render(data)

    def test_non_finite_floats_are_rejected_like_json(self):
        with pytest.raises(ValueError):
            TOONRenderer().render({"n": float("nan")})

    def test_media_type_and_format(self):
        renderer = TOONRenderer()

        assert renderer.media_type == "application/toon"
        assert renderer.format == "toon"

    def test_render_respects_renderer_context(self):
        renderer = TOONRenderer()

        # renderer_context / accepted_media_type are accepted but optional.
        rendered = renderer.render(
            {"a": 1},
            accepted_media_type="application/toon",
            renderer_context={"response": None},
        )

        assert rendered == toon_format.dumps({"a": 1}).encode(renderer.charset)


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
class TestTOONParser:
    @pytest.mark.parametrize("value", PAYLOAD_PARAMS)
    def test_parse_returns_python_value(self, value):
        parser = TOONParser()

        result = parser.parse(_make_stream(value))

        assert result == value

    def test_media_type(self):
        assert TOONParser().media_type == "application/toon"

    def test_parse_uses_provided_encoding(self):
        parser = TOONParser()
        value = {"name": "héllo", "emoji": "🌍"}
        stream = io.BytesIO(toon_format.dumps(value).encode("utf-8"))

        result = parser.parse(stream, parser_context={"encoding": "utf-8"})

        assert result == value

    @pytest.mark.parametrize("codec", ["zlib", "bz2", "hex", "base64"])
    def test_non_text_codec_is_rejected_without_decoding(self, codec):
        with pytest.raises(ParseError, match="unsupported charset"):
            TOONParser().parse(io.BytesIO(b"a: 1"), parser_context={"encoding": codec})

    def test_unknown_charset_is_rejected(self):
        with pytest.raises(ParseError, match="unsupported charset"):
            TOONParser().parse(io.BytesIO(b"a: 1"), parser_context={"encoding": "bogus"})

    def test_invalid_utf8_raises_parse_error(self):
        with pytest.raises(ParseError, match="not valid"):
            TOONParser().parse(io.BytesIO(b"a: \xff\xfe"))

    def test_other_text_charsets_still_work(self):
        stream = io.BytesIO("a: héllo".encode("utf-16"))

        assert TOONParser().parse(stream, parser_context={"encoding": "utf-16"}) == {"a": "héllo"}

    @pytest.mark.parametrize(
        "body",
        [
            b"a: 1e400",
            b"a: " + b"9" * 5000,
            b"a: 1\na: 2",
            b"[1000000000]: 1,2",
        ],
        ids=["out-of-range-float", "huge-integer", "duplicate-key", "declared-length"],
    )
    def test_documents_toon_format_rejects_raise_parse_error(self, body):
        with pytest.raises(ParseError):
            TOONParser().parse(io.BytesIO(body))

    def test_extremely_deep_document_raises_parse_error(self, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = None
        depth = 5_000
        text = "".join("  " * i + "a:\n" for i in range(depth)) + "  " * depth + "x: 1\n"

        with pytest.raises(ParseError, match="nested too deeply"):
            TOONParser().parse(io.BytesIO(text.encode()))

    def test_body_over_the_upload_limit_is_rejected(self, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 7

        with pytest.raises(RequestEntityTooLarge):
            TOONParser().parse(io.BytesIO(b"a: 12345"))

    def test_body_at_the_upload_limit_is_parsed(self, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 7

        assert TOONParser().parse(io.BytesIO(b"a: 1234")) == {"a": 1234}

    def test_oversized_body_is_not_read_past_the_limit(self, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 8
        stream = io.BytesIO(b"a: " + b"1" * 10_000_000)

        with pytest.raises(RequestEntityTooLarge):
            TOONParser().parse(stream)

        assert stream.tell() == 9

    def test_upload_limit_can_be_disabled(self, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = None

        body = b"a: " + b"x" * 3_000_000

        assert TOONParser().parse(io.BytesIO(body)) == {"a": "x" * 3_000_000}

    def test_parse_invalid_toon_raises_parse_error(self):
        parser = TOONParser()
        # Declared array length does not match the number of elements.
        stream = io.BytesIO(b"[999]: 1,2,3")

        with pytest.raises(ParseError) as exc_info:
            parser.parse(stream)

        assert "TOON parse error" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", RENDER_PARAMS)
def test_render_then_parse_roundtrip(value):
    renderer = TOONRenderer()
    parser = TOONParser()

    rendered = renderer.render(value)
    parsed = parser.parse(io.BytesIO(rendered))

    assert parsed == value


# --------------------------------------------------------------------------- #
# Integration coverage: full DRF request/response cycle
# --------------------------------------------------------------------------- #
class TestTOONIntegration:
    """Drive payloads through the real DRF stack via the ``/echo/`` endpoint.

    Posting ``application/toon`` exercises ``TOONParser`` inside DRF content
    negotiation, and requesting it back exercises ``TOONRenderer`` when the
    response is rendered.
    """

    # ``None`` renders an empty body, so the HTTP response carries no body or Content-Type header.
    # That is a degenerate transport case, not a parser/renderer concern, and it is already covered
    # by the unit tests above -- so it is excluded from the end-to-end run.
    integration_params = [
        pytest.param(payload.value, id=payload.id)
        for payload in SAMPLE_PAYLOADS
        if payload.id != "none"
    ]

    @pytest.mark.parametrize("value", integration_params)
    def test_echo_roundtrip_through_drf(self, api_client, value):
        request_body = toon_format.dumps(value).encode("utf-8")

        response = api_client.post(
            "/echo/",
            data=request_body,
            content_type="application/toon",
            HTTP_ACCEPT="application/toon",
        )

        assert response.status_code == 200
        assert response["content-type"].startswith("application/toon")
        assert toon_format.loads(response.content.decode("utf-8")) == value

    def test_invalid_toon_body_returns_400(self, api_client):
        # Declared array length does not match the number of elements.
        response = api_client.post(
            "/echo/",
            data=b"[999]: 1,2,3",
            content_type="application/toon",
            HTTP_ACCEPT="application/toon",
        )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        ("body", "content_type"),
        [
            (zlib.compress(b"a: " + b"x" * 1_000_000), "application/toon; charset=zlib"),
            (b"a: 1", "application/toon; charset=hex"),
            (b"a: \xff\xfe", "application/toon"),
            (b"a: 1\n", "application/toon; charset=utf-16"),
        ],
        ids=["zlib-bomb", "hex-codec", "invalid-utf8", "charset-mismatch"],
    )
    def test_bad_encoding_returns_400_not_500(self, api_client, body, content_type):
        response = api_client.post(
            "/echo/", data=body, content_type=content_type, HTTP_ACCEPT="application/toon"
        )

        assert response.status_code == 400

    def test_oversized_body_returns_413(self, api_client, settings):
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1024

        response = api_client.post(
            "/echo/",
            data=b"a: " + b"x" * 2048,
            content_type="application/toon",
            HTTP_ACCEPT="application/toon",
        )

        assert response.status_code == 413
        assert response["content-type"].startswith("application/toon")

    def test_raw_non_serializer_data_renders(self, api_client):
        response = api_client.get("/rich/", HTTP_ACCEPT="application/toon")

        assert response.status_code == 200
        assert toon_format.loads(response.content.decode("utf-8")) == {
            "1": "int key",
            "id": str(uuid.UUID(int=1)),
            "big": 2**100,
            "tags": ["a"],
        }
