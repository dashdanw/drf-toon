import json

import toons
from rest_framework.renderers import BaseRenderer, JSONRenderer


class TOONRenderer(BaseRenderer):
    media_type = "application/toon"
    format = "toon"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        # toons only serializes plain JSON types; DRF's encoder handles UUID, datetime, Decimal...
        return toons.dumps(json.loads(JSONRenderer().render(data))).encode(self.charset)
