from fastapi import Request, Response
from fastapi.security import APIKeyHeader
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Define the API key header
X_API_KEY = APIKeyHeader(name="MCP-Auth-Token", auto_error=False)

async def verify_auth_token(request: Request, call_next):
    """
    Middleware to verify auth_token for all incoming requests
    """
    # Skip authentication for health endpoint
    if request.url.path == "/health":
        response = await call_next(request)
        return response

    try:
        # Get the auth token from header
        auth_token = await X_API_KEY(request)
        
        if not auth_token:
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "Missing authentication token",
                    "status": "unauthorized"
                }),
                status_code=401,
                media_type="application/json"
            )

        # In a production environment, you would typically:
        # 1. Validate the token against a secret or JWT verification
        # 2. Check token expiration
        # 3. Verify against a user database or auth service
        # For this example, we'll check against an environment variable
        expected_token = os.getenv("BACKEND_INCOMING_AUTH_TOKEN")
        
        if not expected_token or auth_token != expected_token:
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "Invalid authentication token",
                    "status": "unauthorized"
                }),
                status_code=401,
                media_type="application/json"
            )

        # Store auth_token in request.state for use in routes
        request.state.auth_token = auth_token

        # Call the next middleware or route handler
        response = await call_next(request)
        return response

    except Exception as e:
        return Response(
            content=json.dumps({
                "success": False,
                "error": f"Authentication error: {str(e)}",
                "status": "error"
            }),
            status_code=500,
            media_type="application/json"
        )