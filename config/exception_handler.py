from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, DjangoValidationError):
        detail = _detail(exc)
        msg = str(detail.get("detail", detail) if isinstance(detail, dict) else detail)
        if "not found" in msg.lower():
            return Response(detail, status=status.HTTP_404_NOT_FOUND)
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, (ValueError, OverflowError)):
        view = context.get("view")
        kwargs = context.get("kwargs", {})
        action = getattr(view, "action", None)
        msg = str(exc)

        is_detail_lookup = bool(
            "pk" in kwargs
            or action in ("retrieve", "destroy", "update", "partial_update")
            or "expected a number" in msg
            or "invalid literal for int()" in msg
        )
        if is_detail_lookup:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

    return drf_exception_handler(exc, context)


def _detail(exc):
    if hasattr(exc, "message_dict") and exc.message_dict:
        return exc.message_dict
    if hasattr(exc, "messages") and exc.messages:
        if len(exc.messages) == 1:
            return {"detail": exc.messages[0]}
        return {"detail": exc.messages}
    return {"detail": str(exc)}
