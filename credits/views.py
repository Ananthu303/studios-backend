from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsStaffOrSuperAdmin

from .models import CreditPack
from .serializers import (
    CreditBalanceSerializer,
    CreditPackSerializer,
    TransactionSerializer,
)
from .services import get_credit_balance, get_ledger, grant_credit_pack


def _parse_as_of(request):
    raw = request.query_params.get("as_of")
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ValidationError({"as_of": "Use an ISO 8601 datetime."})
    return parsed


def _target_member(request):
    member_id = request.query_params.get("member")
    if not member_id:
        return request.user
    if not request.user.is_studio_staff:
        raise PermissionDenied("Members may only read their own credits.")
    return get_object_or_404(User, pk=member_id)


class CreditPackViewSet(viewsets.ModelViewSet):
    serializer_class = CreditPackSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsStaffOrSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = CreditPack.objects.select_related("member").order_by(
            "expires_at",
            "id",
        )
        if self.request.user.is_studio_staff:
            member_id = self.request.query_params.get("member")
            if member_id:
                queryset = queryset.filter(member_id=member_id)
            return queryset
        return queryset.filter(member=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pack = grant_credit_pack(
            serializer.validated_data["member"],
            serializer.validated_data["granted_credits"],
            serializer.validated_data["expires_at"],
            serializer.validated_data.get("granted_at"),
        )
        output = self.get_serializer(pack)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=["get"], url_path="balance")
    def balance(self, request):
        payload = get_credit_balance(
            _target_member(request),
            _parse_as_of(request),
        )
        return Response(CreditBalanceSerializer(payload).data)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return get_ledger(
            _target_member(self.request),
            _parse_as_of(self.request),
        )
