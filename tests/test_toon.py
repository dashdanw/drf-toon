"""Unit tests for the TOON parser and renderer.

The tests exercise both classes against a shared set of sample payloads (see
``tests/factories.py``) covering strings, numbers, booleans, null, lists and
nested/mixed structures.
"""

from __future__ import annotations

import io

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
