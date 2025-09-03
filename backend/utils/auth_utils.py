
import json
import time
from typing import Dict
import urllib.request

from fastapi import Depends, HTTPException, status, Request
from jose import jwk, jwt
from jose.exceptions import JWTError

# === Cognito Configuration (replace with your actual values) ===
# You can find these in your AWS Cognito User Pool settings.
# To keep them secure, consider using environment variables.
import os
from dotenv import load_dotenv

load_dotenv()

COGNITO_REGION = "eu-north-1"  # e.g., "us-east-1"
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")

# --- Advanced Configuration ---
# These are constructed from the settings above.
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
COGNITO_JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

# =================================================================

# Cache for Cognito's public keys (JWKS)
# This avoids fetching the keys on every single request.
jwks_cache = {
    "keys": [],
    "expiration_time": 0,
}

def get_jwks():
    """
    Retrieves the JSON Web Key Set (JWKS) from Cognito.
    Caches the keys to improve performance.
    """
    global jwks_cache
    # Check if cache is still valid
    print(f"Fetching JWKS from: {COGNITO_JWKS_URL}")
    try:
        with urllib.request.urlopen(COGNITO_JWKS_URL) as response:
            jwks_data = json.loads(response.read().decode("utf-8"))
        
        # Cache the keys and set an expiration time (e.g., 24 hours)
        jwks_cache = {
            "keys": jwks_data["keys"],
            "expiration_time": time.time() + (60 * 60 * 24)
        }
        return jwks_cache["keys"]
    except Exception as e:
        print(f"Error fetching JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch Cognito public keys for token validation."
        )


def get_current_user(request: Request) -> Dict[str, any]:
    """
    FastAPI dependency to validate the Cognito JWT from the Authorization header.

    Usage:
        @app.get("/secure-data", dependencies=[Depends(get_current_user)])
        def secure_endpoint():
            return {"message": "This is secure data."}
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    # The token is expected to be in the format "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    
    token = parts[1]
    jwks = get_jwks()

    # Find the right key to use for decoding
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header"
        )

    rsa_key = {}
    for key in jwks:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
            break
    
    if not rsa_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find a matching public key to verify the token",
        )

    # Decode and validate the token
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID,
            issuer=COGNITO_ISSUER,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token has expired"
        )
    except jwt.JWTClaimsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {e}"
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during token validation: {e}"
        )
