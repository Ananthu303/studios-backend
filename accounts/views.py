from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import User
from .permissions import IsStaffOrSuperAdmin
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TokenRefreshInputSerializer,
    TokenSerializer,
    UserDetailSerializer,
)
from .utils import AuthUtil


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.none()
    serializer_class = UserDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        if IsStaffOrSuperAdmin().has_permission(self.request, self):
            return User.objects.all()
        return User.objects.filter(pk=user.pk)

    def get_permissions(self):
        if self.action in ("register", "login", "refresh_token"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "register":
            return RegisterSerializer
        if self.action == "login":
            return LoginSerializer
        if self.action == "refresh_token":
            return TokenRefreshInputSerializer
        return UserDetailSerializer

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="register",
    )
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = UserDetailSerializer(user)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="login",
    )
    def login(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token_pair = AuthUtil.generate_token_pair(user)
        token_serializer = TokenSerializer(data=token_pair)
        token_serializer.is_valid(raise_exception=True)
        return Response(
            {
                "message": "Login successful.",
                **token_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="token/refresh",
    )
    def refresh_token(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {"access": serializer.validated_data["refresh"]},
            status=status.HTTP_200_OK,
        )
