from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

@api_view(["GET"])
def validate_token(request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    try:
        token = auth_header.split(" ")[1]
        UntypedToken(token)  # validates token
        return Response({"valid": True}, status=200)

    except (InvalidToken, TokenError):
        return Response(status=status.HTTP_401_UNAUTHORIZED)