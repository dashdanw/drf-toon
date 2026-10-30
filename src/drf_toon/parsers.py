import toon_format
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException, ParseError
from rest_framework.parsers import BaseParser

DEFAULT_MAX_BODY_SIZE = 1024 * 1024
DEFAULT_MAX_OBJECTS = 100_000


class RequestEntityTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body too large."
    default_code = "request_entity_too_large"


def _max_body_size():
    limits = [
        getattr(settings, "DRF_TOON_MAX_BODY_SIZE", DEFAULT_MAX_BODY_SIZE),
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE,
    ]
    return min((limit for limit in limits if limit is not None), default=None)


def _object_budget(limit):
    remaining = limit

    def count(obj):
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise ParseError(f"TOON parse error - document has more than {limit} objects")
        return obj

    return count


class TOONParser(BaseParser):
    media_type = "application/toon"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)

        # Django only enforces DATA_UPLOAD_MAX_MEMORY_SIZE when ``request.body`` is read, which
        # DRF's stream parsing never does. TOON is pure Python and costs far more memory per byte
        # than JSON, so it also gets a lower default cap.
        max_size = _max_body_size()
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

        # A tabular header can nest field groups, so one short row decodes into many objects;
        # bounding the object count bounds the memory regardless of how small the body is.
        max_objects = getattr(settings, "DRF_TOON_MAX_OBJECTS", DEFAULT_MAX_OBJECTS)
        object_hook = None if max_objects is None else _object_budget(max_objects)
        try:
            return toon_format.loads(text, object_hook=object_hook)
        except toon_format.ToonDecodeError as e:
            raise ParseError(f"TOON parse error - {str(e)}") from e
