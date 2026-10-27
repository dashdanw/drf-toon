import re

import toons
from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class TOONParser(BaseParser):
    media_type = "application/toon"

    # Deepest indentation, in leading spaces, that a document may use. ``toons`` parses
    # recursively in native code and crashes the whole process (SIGSEGV) on extremely
    # deep documents, which cannot be caught from Python. Every nesting level needs at
    # least one space of indentation, so bounding the indentation bounds the depth.
    max_indent = 2000

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

        if re.search(rf"^ {{{self.max_indent + 1}}}", text, re.MULTILINE):
            raise ParseError("TOON parse error - document is nested too deeply")

        try:
            return toons.loads(text)
        except toons.ToonDecodeError as e:
            raise ParseError(f"TOON parse error - {str(e)}") from e
