"""Unit tests for the TOON parser and renderer.

The tests exercise both classes against a shared set of sample payloads (see
``tests/factories.py``) covering strings, numbers, booleans, null, lists and
nested/mixed structures.
"""

from __future__ import annotations

import bz2
import datetime
import decimal
import io
import uuid
import zlib

import pytest
import toons
from rest_framework.exceptions import ParseError

from drf_toon.parsers import TOONParser
from drf_toon.renderers import TOONRenderer

from .factories import SAMPLE_PAYLOADS

# One pytest parameter per sample payload, each labelled with its readable id.
PAYLOAD_PARAMS = [pytest.param(payload.value, id=payload.id) for payload in SAMPLE_PAYLOADS]


def _make_stream(value: object) -> io.BytesIO:
    """Serialize ``value`` to TOON bytes and wrap it in a byte stream."""
    return io.BytesIO(toons.dumps(value).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #
class TestTOONRenderer:
    @pytest.mark.parametrize("value", PAYLOAD_PARAMS)
    def test_render_matches_toons_dumps(self, value):
        renderer = TOONRenderer()

        rendered = renderer.render(value)

        assert isinstance(rendered, bytes)
        assert rendered == toons.dumps(value).encode(renderer.charset)

    @pytest.mark.parametrize("value", PAYLOAD_PARAMS)
    def test_render_is_parseable_back(self, value):
        renderer = TOONRenderer()

        rendered = renderer.render(value)

        assert toons.loads(rendered.decode(renderer.charset)) == value

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

        assert rendered == toons.dumps({"a": 1}).encode(renderer.charset)


class TestTOONRendererNormalization:
    """Values ``toons`` would drop, corrupt or crash on are normalized first."""

    def _roundtrip(self, value):
        return toons.loads(TOONRenderer().render(value).decode("utf-8"))

    def test_uuid_is_rendered_as_string(self):
        value = uuid.uuid4()

        assert self._roundtrip({"id": value}) == {"id": str(value)}

    def test_temporal_and_decimal_types(self):
        result = self._roundtrip(
            {
                "d": datetime.date(2026, 1, 2),
                "dt": datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
                "n": decimal.Decimal("1.5"),
            }
        )

        assert result == {"d": "2026-01-02", "dt": "2026-01-02T03:04:05Z", "n": 1.5}

    def test_bytes_and_sets(self):
        assert self._roundtrip({"b": b"abc", "s": {7}}) == {"b": "abc", "s": [7]}

    def test_tuples_become_lists(self):
        assert self._roundtrip({"t": (1, 2)}) == {"t": [1, 2]}

    @pytest.mark.parametrize("value", [2**63, -(2**63) - 1, 2**100])
    def test_integers_beyond_64_bits_keep_precision(self, value):
        assert self._roundtrip({"n": value}) == {"n": str(value)}

    @pytest.mark.parametrize("value", [2**63 - 1, -(2**63)])
    def test_64_bit_integers_stay_integers(self, value):
        assert self._roundtrip({"n": value}) == {"n": value}

    def test_non_string_keys_are_coerced_like_json(self):
        assert self._roundtrip({1: "a", 1.5: "b", None: "d"}) == {"1": "a", "1.5": "b", "null": "d"}
        assert self._roundtrip({True: "c"}) == {"true": "c"}
        assert self._roundtrip({False: "c"}) == {"false": "c"}

    def test_unsupported_key_raises_instead_of_panicking(self):
        with pytest.raises(TypeError, match="Keys must be"):
            TOONRenderer().render({(1, 2): "a"})

    def test_unsupported_value_raises(self):
        with pytest.raises(TypeError, match="not TOON serializable"):
            TOONRenderer().render({"a": object()})

    def test_circular_reference_raises_instead_of_crashing(self):
        data: dict = {}
        data["self"] = data

        with pytest.raises(ValueError, match="circular"):
            TOONRenderer().render(data)

    def test_excessive_depth_raises_instead_of_crashing(self):
        data: dict = {}
        node = data
        for _ in range(100_000):
            node["a"] = {}
            node = node["a"]

        with pytest.raises(ValueError, match="nested deeper"):
            TOONRenderer().render(data)

    def test_depth_just_under_the_limit_renders(self):
        renderer = TOONRenderer()
        data: dict = {}
        node = data
        for _ in range(renderer.max_depth - 2):
            node["a"] = {}
            node = node["a"]
        node["leaf"] = 1

        assert toons.loads(renderer.render(data).decode("utf-8")) == data


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
        stream = io.BytesIO(toons.dumps(value).encode("utf-8"))

        result = parser.parse(stream, parser_context={"encoding": "utf-8"})

        assert result == value

    def test_parse_invalid_toon_raises_parse_error(self):
        parser = TOONParser()
        # Declared array length does not match the number of elements.
        stream = io.BytesIO(b"[999]: 1,2,3")

        with pytest.raises(ParseError) as exc_info:
            parser.parse(stream)

        assert "TOON parse error" in str(exc_info.value)


class TestTOONParserHardening:
    @pytest.mark.parametrize("codec", ["zlib", "bz2", "hex", "base64"])
    def test_non_text_codec_is_rejected_without_decoding(self, codec):
        body = bz2.compress(b"a: " + b"x" * 5_000_000) if codec == "bz2" else b"a: 1"

        with pytest.raises(ParseError, match="unsupported charset"):
            TOONParser().parse(io.BytesIO(body), parser_context={"encoding": codec})

    def test_unknown_charset_is_rejected(self):
        with pytest.raises(ParseError, match="unsupported charset"):
            TOONParser().parse(io.BytesIO(b"a: 1"), parser_context={"encoding": "bogus"})

    def test_invalid_utf8_raises_parse_error(self):
        with pytest.raises(ParseError, match="not valid"):
            TOONParser().parse(io.BytesIO(b"a: \xff\xfe"))

    def test_other_text_charsets_still_work(self):
        stream = io.BytesIO("a: héllo".encode("utf-16"))

        assert TOONParser().parse(stream, parser_context={"encoding": "utf-16"}) == {"a": "héllo"}

    @staticmethod
    def _nested(indent: int) -> io.BytesIO:
        text = "".join(" " * i + "a:\n" for i in range(indent)) + " " * indent + "x: 1\n"
        return io.BytesIO(text.encode("utf-8"))

    def test_indentation_at_the_limit_parses(self):
        parser = TOONParser()

        result = parser.parse(self._nested(parser.max_indent))

        assert isinstance(result, dict)

    def test_indentation_beyond_the_limit_is_rejected(self):
        parser = TOONParser()

        with pytest.raises(ParseError, match="nested too deeply"):
            parser.parse(self._nested(parser.max_indent + 1))

    def test_max_indent_can_be_overridden(self):
        class StrictParser(TOONParser):
            max_indent = 10

        with pytest.raises(ParseError, match="nested too deeply"):
            StrictParser().parse(self._nested(11))


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", PAYLOAD_PARAMS)
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

    # ``{}`` serializes to an empty (zero-byte) TOON document, so the HTTP
    # response carries no body or Content-Type header. That is a degenerate
    # transport case, not a parser/renderer concern, and it is already covered
    # by the unit tests above -- so it is excluded from the end-to-end run.
    integration_params = [
        pytest.param(payload.value, id=payload.id)
        for payload in SAMPLE_PAYLOADS
        if payload.id != "empty_dict"
    ]

    @pytest.mark.parametrize("value", integration_params)
    def test_echo_roundtrip_through_drf(self, api_client, value):
        request_body = toons.dumps(value).encode("utf-8")

        response = api_client.post(
            "/echo/",
            data=request_body,
            content_type="application/toon",
            HTTP_ACCEPT="application/toon",
        )

        assert response.status_code == 200
        assert response["content-type"].startswith("application/toon")
        assert toons.loads(response.content.decode("utf-8")) == value

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

    def test_raw_non_serializer_data_renders(self, api_client):
        response = api_client.get("/rich/", HTTP_ACCEPT="application/toon")

        assert response.status_code == 200
        assert toons.loads(response.content.decode("utf-8")) == {
            "1": "int key",
            "id": str(uuid.UUID(int=1)),
            "big": str(2**100),
            "tags": ["a"],
        }
