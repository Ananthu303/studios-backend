from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsMember

from .models import Booking
from .serializers import BookingSerializer
from .services import create_booking


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "partial_update", "update"):
            return [IsMember()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = (
            Booking.objects.select_related(
                "fitness_class",
                "fitness_class__studio",
                "member",
                "slot",
            ).order_by("-booked_at", "-id")
        )
        if self.request.user.is_studio_staff:
            member_id = self.request.query_params.get("member")
            fitness_class_id = self.request.query_params.get("fitness_class")
            status_param = self.request.query_params.get("status")
            if member_id:
                try:
                    queryset = queryset.filter(member_id=int(member_id))
                except (ValueError, TypeError):
                    queryset = queryset.none()
            if fitness_class_id:
                try:
                    queryset = queryset.filter(fitness_class_id=int(fitness_class_id))
                except (ValueError, TypeError):
                    queryset = queryset.none()
            if status_param:
                queryset = queryset.filter(status=status_param)
            return queryset

        status_param = self.request.query_params.get("status")
        queryset = queryset.filter(member=self.request.user)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = create_booking(
            request.user,
            serializer.validated_data["fitness_class"].pk,
            request.headers.get("Idempotency-Key"),
        )
        output = self.get_serializer(booking)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)



