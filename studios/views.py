from datetime import datetime

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsStaffOrSuperAdmin

from .models import FitnessClass, Studio
from .serializers import FitnessClassSerializer, StudioSerializer


class StudioViewSet(ModelViewSet):
    queryset = Studio.objects.all()
    serializer_class = StudioSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsStaffOrSuperAdmin()]


class FitnessClassViewSet(ModelViewSet):
    queryset = FitnessClass.objects.select_related("studio").all()
    serializer_class = FitnessClassSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsStaffOrSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        studio_id = self.request.query_params.get("studio")
        if studio_id:
            queryset = queryset.filter(studio_id=studio_id)
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(start_time__date__gte=_parse_date(start_date))
        if end_date:
            queryset = queryset.filter(start_time__date__lte=_parse_date(end_date))
        return queryset


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(
            {"detail": "Dates must use YYYY-MM-DD."}
        ) from exc
