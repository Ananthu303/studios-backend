from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        return Response(_detail(exc), status=400)
    return drf_exception_handler(exc, context)


def _detail(exc):
    if hasattr(exc, "message_dict") and exc.message_dict:
        return exc.message_dict
    if hasattr(exc, "messages") and exc.messages:
        if len(exc.messages) == 1:
            return {"detail": exc.messages[0]}
        return {"detail": exc.messages}
    return {"detail": str(exc)}
