"""Request-scoped account preference activation."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone, translation


class AccountPreferenceMiddleware:
    """Apply persisted locale and timezone preferences for authenticated users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous_language = translation.get_language()
        previous_timezone = timezone.get_current_timezone()
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated:
            translation.activate(user.locale)
            request.LANGUAGE_CODE = user.locale
            try:
                timezone.activate(ZoneInfo(user.timezone))
            except ZoneInfoNotFoundError:
                timezone.activate(ZoneInfo("UTC"))

        try:
            return self.get_response(request)
        finally:
            if previous_language:
                translation.activate(previous_language)
            else:
                translation.deactivate()
            timezone.activate(previous_timezone)
