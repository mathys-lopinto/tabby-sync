from tabby.app.models import User
from django.contrib.auth import login


class TokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token_value = None
        if "auth_token" in request.GET:
            token_value = request.GET["auth_token"]
        if request.META.get("HTTP_AUTHORIZATION"):
            token_type, *credentials = request.META["HTTP_AUTHORIZATION"].split()
            if token_type == "Bearer" and len(credentials):
                token_value = credentials[0]

        user = User.objects.filter(config_sync_token=token_value).first()

        if user:
            request.session.save = lambda *args, **kwargs: None
            setattr(user, "backend", "django.contrib.auth.backends.ModelBackend")
            login(request, user)
            setattr(request, "_dont_enforce_csrf_checks", True)

        response = self.get_response(request)

        if user:
            response.set_cookie = lambda *args, **kwargs: None

        return response
