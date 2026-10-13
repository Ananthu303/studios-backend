from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsStaffOrSuperAdmin
from .models import FitnessClass, Studio
from .serializers import FitnessClassSerializer, StudioSerializer
from rest_framework.permissions import IsAuthenticated


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
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(start_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_time__date__lte=end_date)
        return queryset
