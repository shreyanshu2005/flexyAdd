from __future__ import annotations

import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema


@extend_schema(
    tags=["Health & Root"],
    summary="Health Check",
    description="Verify API is running and healthy.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "healthy"},
                "message": {"type": "string", "example": "Finance Dashboard API is running"},
            },
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint to verify API is running."""
    return Response(
        {
            "status": "healthy",
            "message": "Finance Dashboard API is running",
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Health & Root"],
    summary="API Root - Information & Links",
    description="Root endpoint providing API information, documentation links, and available endpoints.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string", "example": "Finance Dashboard API"},
                "version": {"type": "string", "example": "1.0.0"},
                "status": {"type": "string", "example": "operational"},
                "documentation": {
                    "type": "object",
                    "properties": {
                        "swagger": {"type": "string", "example": "/api/docs/"},
                        "openapi_schema": {"type": "string", "example": "/api/schema/"},
                        "implementation_guide": {"type": "string"},
                    },
                },
                "endpoints": {"type": "object"},
                "repository": {"type": "string"},
            },
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def root_endpoint(request):
    """Root endpoint with links to documentation and resources."""
    # Get GitHub URL from environment variable, with fallback
    github_url = os.getenv("GITHUB_REPO_URL", "https://github.com/sandeshlavshetty/finance-dashboard")
    
    return Response(
        {
            "success": True,
            "message": "Finance Dashboard API",
            "version": "1.0.0",
            "status": "operational",
            "documentation": {
                "swagger": request.build_absolute_uri("/api/docs/"),
                "openapi_schema": request.build_absolute_uri("/api/schema/"),
                "implementation_guide": github_url,
            },
            "endpoints": {
                "users": request.build_absolute_uri("/api/users/"),
                "records": request.build_absolute_uri("/api/records/"),
                "dashboard": request.build_absolute_uri("/api/dashboard/"),
                "login": request.build_absolute_uri("/api/auth/login/"),
                "health": request.build_absolute_uri("/health/"),
            },
            "repository": github_url,
        },
        status=status.HTTP_200_OK,
    )
