from rest_framework_simplejwt.tokens import RefreshToken


class AuthUtil:
    @staticmethod
    def generate_token_pair(user):
        refresh = RefreshToken.for_user(user)
        token_data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        return token_data
