import toons
from rest_framework.renderers import BaseRenderer
from rest_framework.utils.encoders import JSONEncoder

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class TOONRenderer(BaseRenderer):
    media_type = "application/toon"
    format = "toon"

    # Deepest nesting that will be rendered. ``toons`` serializes recursively in native
    # code and crashes the whole process (SIGSEGV) on circular references and on extremely
    # deep data, so both are rejected here, where they raise a catchable error instead.
    max_depth = 128

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return toons.dumps(self._normalize(data)).encode(self.charset)

    def _normalize(self, obj, depth=0):
        """Reduce ``obj`` to the plain types ``toons`` handles correctly.

        ``toons`` turns types it does not know (UUID, bytes, sets, ...) into ``null``,
        loses precision on integers beyond 64 bits and panics on non-string keys. DRF's
        ``JSONEncoder`` is used for the former so the output matches ``JSONRenderer``.
        """
        if obj is None or isinstance(obj, str | bool | float):
            return obj
        if isinstance(obj, int):
            # Larger integers would be silently rounded to a float.
            return obj if _INT64_MIN <= obj <= _INT64_MAX else str(obj)

        if depth >= self.max_depth:
            raise ValueError(f"Data is nested deeper than {self.max_depth} levels or is circular.")

        if isinstance(obj, dict):
            return {self._key(k): self._normalize(v, depth + 1) for k, v in obj.items()}
        if isinstance(obj, list | tuple):
            return [self._normalize(item, depth + 1) for item in obj]

        try:
            converted = JSONEncoder().default(obj)
        except TypeError:
            raise TypeError(
                f"Object of type {type(obj).__name__} is not TOON serializable"
            ) from None
        return self._normalize(converted, depth + 1)

    @staticmethod
    def _key(key):
        if isinstance(key, str):
            return key
        # Same coercions as the standard ``json`` module.
        if key is True:
            return "true"
        if key is False:
            return "false"
        if key is None:
            return "null"
        if isinstance(key, int | float):
            return str(key)
        raise TypeError(f"Keys must be str, int, float, bool or None, not {type(key).__name__}")
