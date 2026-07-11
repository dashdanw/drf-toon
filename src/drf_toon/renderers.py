from rest_framework.renderers import BaseRenderer

import toons

class TOONRenderer(BaseRenderer):
    media_type = 'application/toon'
    format = 'toon'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return toons.dumps(data).encode(self.charset)