import toon_format
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException, ParseError
from rest_framework.parsers import BaseParser


class RequestEntityTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body too large."
    default_code = "request_entity_too_large"


class TOONParser(BaseParser):
    media_type = "application/toon"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)

        # Django only enforces DATA_UPLOAD_MAX_MEMORY_SIZE when ``request.body`` is read, which
        # DRF's stream parsing never does. TOON is pure Python, so an uncapped body costs far more
        # CPU and memory than the same JSON body.
        max_size = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        raw = stream.read() if max_size is None else stream.read(max_size + 1)
        if max_size is not None and len(raw) > max_size:
            raise RequestEntityTooLarge(f"Request body exceeds the {max_size} byte limit.")

        # ``bytes.decode`` refuses non-text codecs (zlib, bz2, hex, ...) up front. Going
        # through ``codecs.getreader`` instead would let a client pick a decompression
        # codec via the ``Content-Type`` charset and bypass body size limits.
        try:
            text = raw.decode(encoding)
        except LookupError as e:
            raise ParseError("TOON parse error - unsupported charset") from e
        except UnicodeError as e:
            raise ParseError(f"TOON parse error - body is not valid {encoding}") from e

        try:
            return toon_format.loads(text)
        except toon_format.ToonDecodeError as e:
            raise ParseError(f"TOON parse error - {str(e)}") from e
