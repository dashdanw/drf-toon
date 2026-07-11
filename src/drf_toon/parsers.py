import codecs

import toons
from django.conf import settings

from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser



class TOONParser(BaseParser):
    media_type = 'application/toon'

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)
        decoded_stream = codecs.getreader(encoding)(stream)

        try:
            return toons.load(decoded_stream)
        except toons.ToonDecodeError as e:
            raise ParseError(f"TOON parse error - {str(e)}")