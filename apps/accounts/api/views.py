from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.auth_service import (
    activate_user_account,
    authenticate_admin,
    authenticate_client,
    authenticate_user,
    get_tokens_for_user,
    register_user,
    reset_user_password,
    send_password_reset_otp,
)
from ..services.otp_service import check_otp_code, generate_and_send_email_otp, verify_otp_code
from .serializers import (
    ChangePasswordSerializer,
    EmailVerifyOTPSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
    VerifyPasswordOTPSerializer,
)


class RegisterAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = register_user(**serializer.validated_data)
        generate_and_send_email_otp(email=user.email, purpose='REGISTER_VERIFY')
        return Response({'detail': 'Registration successful. Please verify your email.'}, status=status.HTTP_201_CREATED)


class VerifyOTPAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = EmailVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verify_otp_code(**serializer.validated_data)
        user = activate_user_account(email=serializer.validated_data['email'])
        return Response(
            {
                'detail': 'Account verified successfully.',
                'email': user.email,
                'tokens': get_tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class LoginAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate_user(**serializer.validated_data)
        return Response(
            {
                'detail': 'Login successful.',
                'email': user.email,
                'role': user.role,
                'tokens': get_tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class AdminLoginAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate_admin(**serializer.validated_data)
        return Response(
            {
                'detail': 'Admin login successful.',
                'email': user.email,
                'role': user.role,
                'tokens': get_tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class ClientLoginAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate_client(**serializer.validated_data)
        return Response(
            {
                'detail': 'Client login successful.',
                'email': user.email,
                'role': user.role,
                'tokens': get_tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_password_reset_otp(email=serializer.validated_data['email'])
        return Response({'detail': 'Password reset OTP sent to your email.'}, status=status.HTTP_200_OK)


class VerifyPasswordResetOTPAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = VerifyPasswordOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        check_otp_code(
            email=serializer.validated_data['email'],
            code=serializer.validated_data['code'],
            purpose='PASSWORD_RESET',
        )
        return Response({'detail': 'OTP verified successfully.'}, status=status.HTTP_200_OK)


class ResetPasswordAPIView(APIView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_user_password(**serializer.validated_data)
        return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)


class ProfileAPIView(APIView):
    """Authenticated user: retrieve or update own profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(UserProfileSerializer(request.user).data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def patch(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'detail': 'Profile updated successfully.',
                'profile': serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(APIView):
    """Authenticated user: change own password after verifying the current one."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
