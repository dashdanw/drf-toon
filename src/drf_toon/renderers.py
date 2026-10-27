import json

import toon_format
from rest_framework.renderers import BaseRenderer, JSONRenderer


class TOONRenderer(BaseRenderer):
    media_type = "application/toon"
    format = "toon"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        # toon_format follows JSON's data model; DRF's encoder handles UUID, datetime, Decimal...
        rendered = toon_format.dumps(json.loads(JSONRenderer().render(data))).encode(self.charset)
        # `{}` is zero bytes, so DRF would drop Content-Type; a newline is the same document.
        return rendered or b"\n"
