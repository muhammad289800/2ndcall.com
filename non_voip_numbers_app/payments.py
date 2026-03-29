"""Paydify (Bitget Pay) payment integration.

Required environment variables:
    BITGET_APP_ID     — your Paydify / Bitget Pay appId
    BITGET_API_SECRET — your Paydify / Bitget Pay apiSecret

Optional:
    BITGET_CURRENCY   — payment currency, default USDT
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

PAYDIFY_BASE_URL = "https://api.paydify.com"

BITGET_APP_ID = os.environ.get("BITGET_APP_ID", "").strip()
BITGET_API_SECRET = os.environ.get("BITGET_API_SECRET", "").strip()
BITGET_CURRENCY = os.environ.get("BITGET_CURRENCY", "USDT").strip()


def is_configured() -> bool:
    return bool(BITGET_APP_ID and BITGET_API_SECRET)


def gen_sign(app_id: str, api_secret: str, path_url: str, body_str: str, timestamp_ms: int) -> str:
    """HMAC-SHA256 + Base64 signature per Paydify algorithm."""
    parsed = urlparse(path_url)
    api_path = parsed.path
    query_params = parse_qs(parsed.query)

    content_map: dict[str, Any] = {
        "apiPath": api_path,
        "body": body_str,
        "x-api-key": app_id,
        "x-api-timestamp": str(timestamp_ms),
    }
    for k, v_list in query_params.items():
        if v_list:
            content_map[k] = v_list[0]

    ordered = {k: content_map[k] for k in sorted(content_map)}
    content = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False)
    raw = hmac.new(api_secret.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(raw).decode()


def _make_headers(path: str, body_str: str) -> dict[str, str]:
    ts = int(time.time() * 1000)
    sig = gen_sign(BITGET_APP_ID, BITGET_API_SECRET, path, body_str, ts)
    return {
        "Content-Type": "application/json",
        "x-api-key": BITGET_APP_ID,
        "x-api-timestamp": str(ts),
        "x-api-signature": sig,
    }


def create_payment_order(
    merchant_order_id: str,
    amount_usd: float,
    notify_url: str = "",
    redirect_url: str = "",
    currency: str = "",
) -> dict[str, Any]:
    """Create a Paydify payment order.

    Returns dict with at least:
        deeplink  — bitkeep:// deeplink to invoke Bitget Wallet Pay
        txnId     — Paydify's own order ID
    """
    if not is_configured():
        raise ValueError(
            "Bitget Pay is not configured. "
            "Set BITGET_APP_ID and BITGET_API_SECRET environment variables."
        )

    pay_currency = currency or BITGET_CURRENCY or "USDT"
    path = "/payment/payin/v1/createPayment"
    body: dict[str, Any] = {
        "appId": BITGET_APP_ID,
        "mchTxnId": merchant_order_id,
        "txnAmount": f"{amount_usd:.2f}",
        "currency": pay_currency,
        "checkoutMode": 1,
        "payMethod1": "BGW",
    }
    if notify_url:
        body["notifyUrl"] = notify_url
    if redirect_url:
        body["redirectUrl"] = redirect_url

    body_str = json.dumps(body, separators=(",", ":"))
    headers = _make_headers(path, body_str)

    resp = requests.post(
        PAYDIFY_BASE_URL + path,
        headers=headers,
        data=body_str,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 0:
        raise ValueError(
            f"Paydify error: {data.get('msg', 'unknown error')} (status={data.get('status')})"
        )

    return data.get("data", {})


def verify_webhook(request_headers: dict[str, str], body_str: str, webhook_path: str) -> bool:
    """Verify the signature of an incoming Paydify webhook.

    Args:
        request_headers: dict of HTTP headers from the webhook request.
        body_str: raw request body as string.
        webhook_path: the path of your webhook endpoint, e.g. '/webhooks/bitget/payment'.
    """
    if not BITGET_API_SECRET:
        return True  # Can't verify without secret — pass through in dev

    api_key = request_headers.get("x-api-key", "")
    timestamp_str = request_headers.get("x-api-timestamp", "")
    signature = request_headers.get("x-api-signature", "")

    if not all([api_key, timestamp_str, signature]):
        return False

    try:
        expected = gen_sign(api_key, BITGET_API_SECRET, webhook_path, body_str, int(timestamp_str))
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False
