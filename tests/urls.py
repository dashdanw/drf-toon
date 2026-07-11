from django.urls import URLPattern, URLResolver, path
from rest_framework.response import Response
from rest_framework.views import APIView


class EchoView(APIView):
    """Echoes the parsed request body back so a full parse -> render cycle runs."""

    def post(self, request):
        return Response(request.data)


urlpatterns: list[URLPattern | URLResolver] = [
    path("echo/", EchoView.as_view(), name="echo"),
]
