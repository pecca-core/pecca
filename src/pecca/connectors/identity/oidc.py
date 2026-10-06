from __future__ import annotations

import base64
import getpass
import json
import os
from typing import Any

from pecca.connectors.base import Identity, register


@register("identity", "oidc")
class OidcIdentity(Identity):
    """Reads ``groups`` from the claims of the JWT in ``PECCA_ID_TOKEN`` (signature is NOT verified:
    use it for convenience checks only, never as authentication). Without a token: local user."""

    def __init__(self, token_env: str = "PECCA_ID_TOKEN", groups_claim: str = "groups", **_: Any) -> None:
        self.token_env, self.claim = token_env, groups_claim

    def current_principal(self) -> dict[str, Any]:
        tok = os.environ.get(self.token_env)
        if not tok:
            return {"user": os.environ.get("USER") or getpass.getuser(), "groups": ["local"]}
        try:
            payload = tok.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except Exception:  # noqa: BLE001
            return {"user": "unknown", "groups": []}
        user = claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "unknown"
        groups = claims.get(self.claim) or []
        return {"user": user, "groups": [groups] if isinstance(groups, str) else list(groups)}
