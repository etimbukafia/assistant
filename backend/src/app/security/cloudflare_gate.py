"""
Cloudflare Zero Trust Service Token gate.

Enforced when ENV is not "production" (i.e. development, staging).
In production, Cloudflare's tunnel handles access control directly,
so this middleware is a no-op — set ENV=production and the code
stays exactly the same.

Requires CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET in .env
for non-production environments.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.infra.config import get_settings


class CloudflareGateMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # In production, Cloudflare tunnel enforces access — skip
        if settings.ENV == "production":
            return await call_next(request)

        # Non-production: require service token headers
        if not settings.CF_ACCESS_CLIENT_ID or not settings.CF_ACCESS_CLIENT_SECRET:
            return await call_next(request)

        client_id = request.headers.get("CF-Access-Client-Id", "")
        client_secret = request.headers.get("CF-Access-Client-Secret", "")

        if (
            client_id != settings.CF_ACCESS_CLIENT_ID
            or client_secret != settings.CF_ACCESS_CLIENT_SECRET
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden"},
            )

        return await call_next(request)
