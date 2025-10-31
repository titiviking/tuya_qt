from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
import string
import time
from typing import Any

import aiohttp

from .const import TUYA_ENDPOINTS, AUTO_REGIONS

_LOGGER = logging.getLogger(__name__)


class TuyaS6ApiError(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


# ---------- Signing helpers (Tuya 2025 spec) ----------

_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _content_sha256(body_s: str) -> str:
    if not body_s:
        return _EMPTY_SHA256
    return _sha256_hex(body_s)


def _string_to_sign(method: str, path_with_query: str, body_s: str) -> str:
    """
    Tuya new signature:
      stringToSign =
        HTTPMethod + "\n" +
        Content-SHA256 + "\n" +
        Optional_Signature_Headers + "\n" +
        URL (path + sorted query string)

    We do not use extra signature headers, so the middle line is empty.
    """
    return "\n".join(
        [
            method.upper(),
            _content_sha256(body_s),
            "",  # no extra signature headers
            path_with_query,
        ]
    )


def _hmac_upper(msg: str, secret: bytes) -> str:
    return hmac.new(secret, msg=msg.encode("utf-8"), digestmod=hashlib.sha256).hexdigest().upper()


def _rand_nonce(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


# ------------------------------------------------------


class TuyaS6Api:
    """
    Tuya OpenAPI client for S6.
    - Auto-detects data center (EU/US/IN/CN) if region='auto'
    - Follows 2025 signing (stringToSign + Content-SHA256) for ALL requests
    - Tries with-nonce and without-nonce for token, caches whichever works
    """

    def __init__(self, session: aiohttp.ClientSession, region: str, access_id: str, access_secret: str) -> None:
        self._session = session
        self._access_id = access_id.strip()
        self._access_secret = access_secret.strip().encode()
        self._region_in = region.strip().lower()

        # Resolved endpoint (e.g. https://openapi.tuyaeu.com) once detected
        self._base: str | None = None

        # Whether the project expects a nonce in signature
        self._use_nonce: bool | None = None

        # Token cache
        self._token: str | None = None
        self._token_expire_ts: float = 0.0

    # ---------------- Token (detect region + nonce) ----------------

    async def _request_token_once(self, base: str, use_nonce: bool) -> dict[str, Any]:
        """Call /v1.0/token?grant_type=1 once with a specific base + nonce mode; return parsed payload."""
        path = "/v1.0/token"
        query = "grant_type=1"
        path_with_query = f"{path}?{query}"

        # Token request is GET without body
        body_s = ""
        sts = _string_to_sign("GET", path_with_query, body_s)

        t_ms = int(time.time() * 1000)
        t = str(t_ms)

        if use_nonce:
            nonce = _rand_nonce()
            sign_str = self._access_id + t + nonce + sts
        else:
            nonce = None
            sign_str = self._access_id + t + sts

        sign = _hmac_upper(sign_str, self._access_secret)

        headers = {
            "client_id": self._access_id,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "sign": sign,
        }
        if nonce:
            headers["nonce"] = nonce

        url = f"{base}{path_with_query}"

        _LOGGER.debug("tuya_s6_qt: token (nonce=%s) -> %s", use_nonce, url)
        _LOGGER.debug("tuya_s6_qt: client timestamp (ms) = %s", t_ms)

        try:
            async with self._session.get(
                url, headers=headers, raise_for_status=False, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                status = resp.status
        except Exception as err:
            _LOGGER.error("tuya_s6_qt: network error requesting token: %s", err)
            raise TuyaS6ApiError(f"network error requesting token: {err}") from err

        # Parse JSON
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            _LOGGER.error("tuya_s6_qt: token response not JSON (status %s): %s", status, text)
            raise TuyaS6ApiError("token response not JSON", {"raw": text})

        # Helpful clock drift log
        srv_t = payload.get("t")
        if srv_t is not None:
            try:
                diff = int(srv_t) - t_ms
            except Exception:
                diff = "n/a"
            _LOGGER.debug("tuya_s6_qt: server timestamp (ms) = %s (diff=%s ms)", srv_t, diff)

        return payload

    async def _ensure_token(self) -> None:
        """Get a token if missing/near expiry. Auto-detect base and nonce mode."""
        now = time.time()
        if self._token and now < self._token_expire_ts - 60:
            return

        # Prepare list of bases to try
        if self._base:
            bases = [self._base]
        else:
            if self._region_in in TUYA_ENDPOINTS:
                bases = [TUYA_ENDPOINTS[self._region_in]]
            elif self._region_in == "auto":
                bases = [TUYA_ENDPOINTS[r] for r in AUTO_REGIONS]
            elif self._region_in.startswith("http"):
                bases = [self._region_in]
            else:
                bases = [TUYA_ENDPOINTS["eu"], TUYA_ENDPOINTS["us"], TUYA_ENDPOINTS["in"], TUYA_ENDPOINTS["cn"]]

        last_error: dict[str, Any] | None = None

        for base in bases:
            # Try with current knowledge of nonce, or both if unknown
            nonce_modes = [self._use_nonce] if self._use_nonce is not None else [True, False]
            for use_nonce in nonce_modes:
                payload = await self._request_token_once(base, use_nonce)
                if payload.get("success"):
                    result = payload["result"]
                    self._token = result["access_token"]
                    expires_in = int(result.get("expire_time", 7200))
                    self._token_expire_ts = now + expires_in - 30
                    self._base = base
                    self._use_nonce = bool(use_nonce)
                    _LOGGER.debug(
                        "tuya_s6_qt: token ok (base=%s, nonce=%s), valid ~%s s", base, self._use_nonce, expires_in
                    )
                    return

                _LOGGER.error("tuya_s6_qt: token failed (base=%s, nonce=%s): %s", base, use_nonce, payload)
                last_error = payload

        raise TuyaS6ApiError("token failed", last_error or {})

    # ---------------- Signed business requests ----------------

    def _signed_headers(self, method: str, path_with_query: str, body_s: str) -> dict[str, str]:
        """
        Business request signature (Tuya 2025):
          sign = HMAC-SHA256(client_id + access_token + t + [nonce] + stringToSign, secret)
        """
        assert self._token is not None and self._base is not None

        t_ms = int(time.time() * 1000)
        t = str(t_ms)
        sts = _string_to_sign(method, path_with_query, body_s)

        if self._use_nonce:
            nonce = _rand_nonce()
            sign_str = self._access_id + self._token + t + nonce + sts
        else:
            nonce = None
            sign_str = self._access_id + self._token + t + sts

        sign = _hmac_upper(sign_str, self._access_secret)

        headers = {
            "client_id": self._access_id,
            "access_token": self._token,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "sign": sign,
            "mode": "cors",
            "Content-Type": "application/json",
        }
        if nonce:
            headers["nonce"] = nonce
        return headers

    async def _request(self, method: str, path_with_query: str, *, body: dict[str, Any] | None = None) -> Any:
        await self._ensure_token()
        assert self._base is not None

        body_s = json.dumps(body) if body else ""
        url = f"{self._base}{path_with_query}"

        async def one_try() -> tuple[bool, dict[str, Any] | None, int, str]:
            headers = self._signed_headers(method, path_with_query, body_s)
            _LOGGER.debug(
                "tuya_s6_qt: %s %s (base=%s, nonce=%s)", method, url, self._base, self._use_nonce
            )
            try:
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    data=body_s or None,
                    raise_for_status=False,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    text = await resp.text()
                    status = resp.status
            except Exception as err:
                _LOGGER.error("tuya_s6_qt: network error on %s %s: %s", method, path_with_query, err)
                raise TuyaS6ApiError(f"network error on {path_with_query}: {err}") from err

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                _LOGGER.error("tuya_s6_qt: non-JSON reply from %s (status %s): %s", path_with_query, status, text)
                raise TuyaS6ApiError("non-JSON reply", {"raw": text})

            return payload.get("success", False), payload, status, text

        ok, payload, status, _ = await one_try()
        if not ok:
            code = payload.get("code") if isinstance(payload, dict) else None
            _LOGGER.error(
                "tuya_s6_qt: API error on %s (base=%s, nonce=%s, status=%s): %s",
                path_with_query,
                self._base,
                self._use_nonce,
                status,
                payload,
            )

            # If signature error, flip nonce usage once, refresh token, retry.
            if code == 1004:
                self._use_nonce = not bool(self._use_nonce)
                _LOGGER.warning("tuya_s6_qt: flipping nonce mode to %s and retrying once", self._use_nonce)
                self._token = None
                await self._ensure_token()
                ok2, payload2, status2, _ = await one_try()
                if ok2:
                    return payload2["result"]
                raise TuyaS6ApiError("api error", payload2 if isinstance(payload2, dict) else {})
            raise TuyaS6ApiError("api error", payload if isinstance(payload, dict) else {})

        return payload["result"]

    # ---------------- Public helpers ----------------

    async def get_functions(self, device_id: str) -> list[dict[str, Any]]:
        res = await self._request("GET", f"/v1.0/iot-03/devices/{device_id}/functions")
        return res.get("functions", [])

    async def get_status(self, device_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/v1.0/iot-03/devices/{device_id}/status")

    async def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> Any:
        body = {"commands": commands}
        return await self._request("POST", f"/v1.0/iot-03/devices/{device_id}/commands", body=body)
