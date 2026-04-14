from tabby.app.models import User, hash_token


class TokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = self._extract_token(request)
        if token:
            user = User.objects.filter(
                config_sync_token_hash=hash_token(token), is_active=True
            ).first()
            if user:
                request.user = user
                request._dont_enforce_csrf_checks = True

        return self.get_response(request)

    @staticmethod
    def _extract_token(request):
        if "auth_token" in request.GET:
            return request.GET["auth_token"]
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        # Tolerate any kind of whitespace (space, tab, multiple) between
        # the scheme and the value, like the upstream middleware did.
        parts = auth.split(maxsplit=1)
        if len(parts) == 2 and parts[0] == "Bearer":
            return parts[1].strip()
        return None
