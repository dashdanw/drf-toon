import uuid

from django.urls import URLPattern, URLResolver, path
from rest_framework.response import Response
from rest_framework.views import APIView


class EchoView(APIView):
    """Echoes the parsed request body back so a full parse -> render cycle runs."""

    def post(self, request):
        return Response(request.data)


class RichView(APIView):
    """Returns raw (non-serializer) data that a JSON renderer would also accept."""

    def get(self, request):
        return Response({1: "int key", "id": uuid.UUID(int=1), "big": 2**100, "tags": {"a"}})


urlpatterns: list[URLPattern | URLResolver] = [
    path("echo/", EchoView.as_view(), name="echo"),
    path("rich/", RichView.as_view(), name="rich"),
]
