from django.http import HttpResponse


def health(request):
    return HttpResponse("ok\n", content_type="text/plain")
