from rest_framework import status
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
    EmailVerifyOTPSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
    VerifyPasswordOTPSerializer,
)


class RegisterAPIView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = register_user(**serializer.validated_data)
        generate_and_send_email_otp(email=user.email, purpose='REGISTER_VERIFY')
        return Response({'detail': 'Registration successful. Please verify your email.'}, status=status.HTTP_201_CREATED)


class VerifyOTPAPIView(APIView):
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
    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_password_reset_otp(email=serializer.validated_data['email'])
        return Response({'detail': 'Password reset OTP sent to your email.'}, status=status.HTTP_200_OK)


class VerifyPasswordResetOTPAPIView(APIView):
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
    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_user_password(**serializer.validated_data)
        return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)
