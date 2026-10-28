from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser

from drf_toon import _codec


class TOONParser(BaseParser):
    media_type = "application/toon"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)

        # ``bytes.decode`` refuses non-text codecs (zlib, bz2, hex, ...) up front. Going
        # through ``codecs.getreader`` instead would let a client pick a decompression
        # codec via the ``Content-Type`` charset and bypass body size limits.
        try:
            text = stream.read().decode(encoding)
        except LookupError as e:
            raise ParseError("TOON parse error - unsupported charset") from e
        except UnicodeError as e:
            raise ParseError(f"TOON parse error - body is not valid {encoding}") from e

        try:
            return _codec.decode(text)
        except _codec.DecodeError as e:
            raise ParseError(f"TOON parse error - {str(e)}") from e
