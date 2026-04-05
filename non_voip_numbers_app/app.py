import functools
import os
import uuid
from pathlib import Path
from typing import Any

import requests as http_requests
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session

from .payments import (
    get_supported_networks,
    get_wallet_address,
    is_configured as crypto_configured,
    match_payment_to_orders,
    scan_trc20_transactions,
    verify_trc20_tx,
)
from .providers import ProviderError, build_providers
from .storage import Storage


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_local_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def create_app() -> Flask:
    load_local_env()
    app = Flask(__name__)
    app.json.sort_keys = False
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())

    # Prevent caching of HTML pages so updates are always served fresh
    @app.after_request
    def add_no_cache_headers(response):
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    storage = Storage()
    providers = build_providers()

    # ── Auth helpers ─────────────────────────────────────────────────────────

    _admin_token = os.environ.get("ADMIN_TOKEN", "").strip()

    def _token_ok(token: str) -> bool:
        if not _admin_token:
            return True
        import hmac
        return hmac.compare_digest(_admin_token, token)

    def _get_session_user() -> dict[str, Any] | None:
        uid = session.get("user_id")
        return storage.get_user_by_id(uid) if uid else None

    def _auth_ok() -> bool:
        if session.get("authed"):
            return True
        if session.get("user_id"):
            return True
        token = (
            request.headers.get("X-Admin-Token")
            or request.args.get("token")
            or ""
        )
        return _token_ok(token)

    def _is_admin() -> bool:
        """True if authenticated via admin token OR user has role=admin."""
        token = (
            request.headers.get("X-Admin-Token")
            or request.args.get("token")
            or ""
        )
        if _token_ok(token) and token:
            return True
        u = _get_session_user()
        return bool(u and u.get("role") == "admin")

    def require_auth(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not _auth_ok():
                return jsonify({"error": "Login required."}), 401
            return fn(*args, **kwargs)
        return wrapper

    def require_admin(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not _is_admin():
                return jsonify({"error": "Admin access required."}), 403
            return fn(*args, **kwargs)
        return wrapper

    # Fixed pricing for all users — independent of provider cost
    NUMBER_PRICE_MONTHLY = 2.00
    NUMBER_PRICE_YEARLY = 20.00  # save $4/yr

    provider_pricing = {
        "telnyx": {
            "rank": 1,
            "label": "Telnyx",
            "estimated_local_number_monthly_usd": f"${NUMBER_PRICE_MONTHLY:.2f}",
            "notes": "Non-VoIP numbers for SMS and voice.",
            "integrated_in_app": True,
        },
        "signalwire": {
            "rank": 2,
            "label": "SignalWire",
            "estimated_local_number_monthly_usd": f"${NUMBER_PRICE_MONTHLY:.2f}",
            "notes": "Low-cost numbers for SMS and voice. No setup fee.",
            "integrated_in_app": True,
        },
    }

    def payload() -> dict[str, Any]:
        if request.is_json:
            return request.get_json(silent=True) or {}
        return request.form.to_dict()

    def parse_int(value: Any, default: int, minimum: int = 0, maximum: int = 500) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(parsed, maximum))

    def parse_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def provider_or_400(provider_id: str):
        provider = providers.get(provider_id.lower())
        if not provider:
            raise ValueError(f"Unsupported provider '{provider_id}'.")
        if not provider.is_configured():
            raise ValueError(f"Provider '{provider_id}' is not configured. Set TELNYX_API_KEY.")
        return provider

    def ensure_wallet_can_cover(amount: float, provider_id: str = "", user_id: int | None = None) -> None:
        """Enforce wallet balance check.
        - Admin token sessions: always skip (admin funds Telnyx directly).
        - User sessions: always check their personal wallet balance.
        - No user context + non-Telnyx provider: check global wallet.
        """
        if _is_admin() and not session.get("user_id"):
            return  # Admin token — no wallet check
        if amount <= 0:
            return
        balance = storage.get_wallet_balance(user_id=user_id)
        if balance < amount:
            raise ValueError(
                f"Insufficient wallet balance. Need ${amount:.2f} but only have ${balance:.2f}. "
                "Add funds in the Wallet tab first."
            )

    def estimate_action_cost(provider_id: str, action: str, minutes: float = 1.0, plan: str = "monthly") -> float:
        provider = providers[provider_id]
        profile = provider.pricing_profile()
        if action == "number_order":
            return NUMBER_PRICE_YEARLY if plan == "yearly" else NUMBER_PRICE_MONTHLY
        if action == "sms":
            return parse_float(profile.get("sms_outbound_usd"), 0.01)
        if action == "call":
            return parse_float(profile.get("call_per_min_usd"), 0.02) * max(1.0, minutes)
        return 0.0

    def resolve_provider_number_id(provider: Any, number_record: dict[str, Any]) -> str | None:
        if number_record.get("provider_number_id"):
            return str(number_record["provider_number_id"])
        for item in provider.list_owned_numbers():
            if item.get("phone_number") == number_record["phone_number"]:
                return item.get("provider_number_id")
        return None

    # ── Error handlers ───────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/") or request.path.startswith("/webhooks/"):
            return jsonify({"error": "Endpoint not found."}), 404
        return render_template("index.html", providers=providers,
                               pricing_rows=sorted(provider_pricing.values(), key=lambda x: x["rank"])), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error.", "detail": str(e)}), 500

    # ── Auth / User routes ───────────────────────────────────────────────────

    @app.post("/api/auth/register")
    def api_register():
        body = payload()
        email = str(body.get("email", "")).strip().lower()
        name = str(body.get("name", "")).strip()
        password = str(body.get("password", "")).strip()
        if not email or not password:
            return jsonify({"error": "email and password are required."}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters."}), 400
        if storage.get_user_by_email(email):
            return jsonify({"error": "An account with this email already exists."}), 409
        # First user gets admin role automatically
        role = "admin" if storage.user_count() == 0 else "user"
        user = storage.create_user(email, name or email.split("@")[0], password, role)
        session["user_id"] = user["id"]
        session.permanent = True
        return jsonify({"ok": True, "user": user}), 201

    @app.post("/api/auth/login")
    def api_login():
        body = payload()
        # Admin token login
        token = str(body.get("token", "")).strip()
        if token:
            if not _token_ok(token):
                return jsonify({"error": "Invalid admin token."}), 401
            session["authed"] = True
            session.permanent = True
            return jsonify({"ok": True, "mode": "admin_token"})
        # Email + password login
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", "")).strip()
        if not email or not password:
            return jsonify({"error": "email and password are required."}), 400
        pw_hash = storage.get_user_password_hash(email)
        if not pw_hash or not Storage.verify_password(password, pw_hash):
            return jsonify({"error": "Incorrect email or password."}), 401
        user = storage.get_user_by_email(email)
        session["user_id"] = user["id"]
        session.permanent = True
        storage.touch_user_login(user["id"])
        return jsonify({"ok": True, "user": user, "mode": "email"})

    @app.post("/api/auth/logout")
    def api_logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/auth/status")
    def api_auth_status():
        token_configured = bool(_admin_token)
        u = _get_session_user()
        if u:
            storage.touch_user_seen(u["id"])
        return jsonify({
            "authed": _auth_ok(),
            "token_required": token_configured,
            "user": u,
            "is_admin": _is_admin(),
        })

    @app.get("/api/auth/me")
    @require_auth
    def api_me():
        u = _get_session_user()
        if not u:
            return jsonify({"error": "Not a user session (admin token only)."}), 400
        return jsonify({"user": u})

    @app.patch("/api/auth/profile")
    @require_auth
    def api_update_profile():
        u = _get_session_user()
        if not u:
            return jsonify({"error": "Not a user session."}), 400
        body = payload()
        name = str(body.get("name", "")).strip()
        if not name:
            return jsonify({"error": "name is required."}), 400
        updated = storage.update_user_profile(u["id"], name)
        return jsonify({"ok": True, "user": updated})

    @app.post("/api/auth/change-password")
    @require_auth
    def api_change_password():
        u = _get_session_user()
        if not u:
            return jsonify({"error": "Not a user session."}), 400
        body = payload()
        current = str(body.get("current_password", "")).strip()
        new_pw = str(body.get("new_password", "")).strip()
        if not current or not new_pw:
            return jsonify({"error": "current_password and new_password are required."}), 400
        pw_hash = storage.get_user_password_hash(u["email"])
        if not Storage.verify_password(current, pw_hash or ""):
            return jsonify({"error": "Current password is incorrect."}), 401
        if len(new_pw) < 6:
            return jsonify({"error": "New password must be at least 6 characters."}), 400
        storage.change_user_password(u["id"], new_pw)
        return jsonify({"ok": True})

    @app.get("/api/admin/users")
    @require_admin
    def api_admin_users():
        users = storage.list_users()
        # Strip password hashes
        for u in users:
            u.pop("password_hash", None)
        return jsonify({"users": users, "total": len(users)})

    # ── Main routes ──────────────────────────────────────────────────────────

    @app.get("/")
    def home():
        # If user is logged in, show the app
        if _auth_ok() and (session.get("user_id") or session.get("authed")):
            pricing_rows = sorted(provider_pricing.values(), key=lambda item: item["rank"])
            return render_template(
                "index.html",
                providers=providers,
                pricing_rows=pricing_rows,
            )
        # Otherwise show the landing page
        return render_template("landing.html")

    @app.get("/app")
    def app_dashboard():
        """Always show the app (with login screen if not authenticated)."""
        pricing_rows = sorted(provider_pricing.values(), key=lambda item: item["rank"])
        return render_template(
            "index.html",
            providers=providers,
            pricing_rows=pricing_rows,
        )

    # ── WebRTC calling ────────────────────────────────────────────────────

    # Auto-created or set via env
    # WebRTC uses SIP credentials for authentication (more reliable than JWT tokens)
    _webrtc_cred = {
        "id": os.environ.get("TELNYX_CREDENTIAL_ID", "").strip(),
        "sip_username": os.environ.get("TELNYX_SIP_USERNAME", "").strip(),
        "sip_password": os.environ.get("TELNYX_SIP_PASSWORD", "").strip(),
    }

    def _get_telnyx_headers() -> dict[str, str]:
        tp = providers.get("telnyx")
        if not tp or not tp.api_key:
            return {}
        return {"Authorization": f"Bearer {tp.api_key}", "Content-Type": "application/json"}

    @app.post("/api/webrtc/setup")
    @require_admin
    def webrtc_setup():
        """Auto-create a Telnyx Telephony Credential for WebRTC."""
        tp = providers.get("telnyx")
        if not tp or not tp.is_configured():
            return jsonify({"error": "Telnyx not configured. Set TELNYX_API_KEY."}), 503
        if _webrtc_cred["sip_username"] and _webrtc_cred["sip_password"]:
            return jsonify({"ok": True, "message": "Already configured.", "sip_username": _webrtc_cred["sip_username"]})

        # Get outbound voice profile ID (needed for making calls)
        ovp_id = None
        try:
            r = http_requests.get("https://api.telnyx.com/v2/outbound_voice_profiles", headers=_get_telnyx_headers(), timeout=15)
            profiles = r.json().get("data", []) if r.status_code < 400 else []
            for p in profiles:
                if p.get("enabled", True):
                    ovp_id = p.get("id", "")
                    break
        except Exception:
            pass

        # Create a NEW credential_connection for WebRTC
        conn_id = None
        try:
            conn_payload = {
                "connection_name": "2ndCall-WebRTC-Live",
                "active": True,
            }
            if ovp_id:
                conn_payload["outbound_voice_profile_id"] = ovp_id
            r = http_requests.post(
                "https://api.telnyx.com/v2/credential_connections",
                headers=_get_telnyx_headers(),
                json=conn_payload,
                timeout=15,
            )
            if r.status_code < 400:
                conn_id = r.json().get("data", r.json()).get("id", "")
            else:
                # Fallback: use existing credential connection
                r2 = http_requests.get("https://api.telnyx.com/v2/credential_connections", headers=_get_telnyx_headers(), timeout=15)
                conns = r2.json().get("data", []) if r2.status_code < 400 else []
                for c in conns:
                    if c.get("active", True):
                        conn_id = c.get("id", "")
                        break
        except Exception:
            pass

        if not conn_id:
            return jsonify({"error": "Could not create or find a Credential Connection. Check Telnyx account permissions."}), 503

        # Create credential with SIP username/password
        import secrets as _secrets
        sip_user = f"2ndcall_{_secrets.token_hex(6)}"
        sip_pass = _secrets.token_urlsafe(20)
        try:
            resp = http_requests.post(
                "https://api.telnyx.com/v2/telephony_credentials",
                headers=_get_telnyx_headers(),
                json={"connection_id": conn_id, "name": "2ndCall-WebRTC", "sip_username": sip_user, "sip_password": sip_pass},
                timeout=15,
            )
            if resp.status_code >= 400:
                return jsonify({"error": f"Failed to create credential: {resp.text}"}), 502
            data = resp.json().get("data", resp.json())
            _webrtc_cred["id"] = data.get("id", "")
            _webrtc_cred["sip_username"] = sip_user
            _webrtc_cred["sip_password"] = sip_pass
            return jsonify({
                "ok": True,
                "sip_username": sip_user,
                "message": f"WebRTC configured! Set these on Railway for persistence: TELNYX_SIP_USERNAME={sip_user}  TELNYX_SIP_PASSWORD={sip_pass}",
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/webrtc/status")
    @require_auth
    def webrtc_status():
        tp = providers.get("telnyx")
        return jsonify({
            "configured": bool(_webrtc_cred["sip_username"] and _webrtc_cred["sip_password"]),
            "telnyx_configured": bool(tp and tp.is_configured()),
        })

    @app.get("/api/webrtc/token")
    @require_auth
    def webrtc_token():
        """Return SIP credentials or JWT token for WebRTC client login."""
        tp = providers.get("telnyx")
        if not tp or not tp.is_configured():
            return jsonify({"error": "Telnyx not configured."}), 503

        # Try JWT token first (more reliable for WebRTC)
        cred_id = _webrtc_cred.get("id", "")
        if cred_id:
            try:
                resp = http_requests.post(
                    f"https://api.telnyx.com/v2/telephony_credentials/{cred_id}/token",
                    headers=_get_telnyx_headers(), json={}, timeout=10,
                )
                if resp.status_code < 400:
                    token = resp.text.strip().strip('"')
                    if token and len(token) > 20:
                        return jsonify({"login_token": token})
            except Exception:
                pass

        # Try to create a telephony credential and get JWT token
        # Use the new SIP connection ID if available
        new_conn_id = os.environ.get("TELNYX_SIP_CONNECTION_ID", "").strip()
        if not new_conn_id:
            # Try to find it by listing credential connections
            try:
                r = http_requests.get("https://api.telnyx.com/v2/credential_connections",
                    headers=_get_telnyx_headers(), timeout=10)
                for c in r.json().get("data", []):
                    if "webrtc" in str(c.get("connection_name", "")).lower() or "2ndcall" in str(c.get("connection_name", "")).lower():
                        new_conn_id = c.get("id", "")
                        break
                    if c.get("active"):
                        new_conn_id = new_conn_id or c.get("id", "")
            except Exception:
                pass

        if new_conn_id and not cred_id:
            try:
                import secrets as _s
                resp = http_requests.post(
                    "https://api.telnyx.com/v2/telephony_credentials",
                    headers=_get_telnyx_headers(),
                    json={"connection_id": new_conn_id, "name": "2ndCall-WebRTC-Token"},
                    timeout=10,
                )
                if resp.status_code < 400:
                    data = resp.json().get("data", resp.json())
                    new_cred_id = data.get("id", "")
                    if new_cred_id:
                        _webrtc_cred["id"] = new_cred_id
                        # Try to get token
                        resp2 = http_requests.post(
                            f"https://api.telnyx.com/v2/telephony_credentials/{new_cred_id}/token",
                            headers=_get_telnyx_headers(), json={}, timeout=10,
                        )
                        if resp2.status_code < 400:
                            token = resp2.text.strip().strip('"')
                            if token and len(token) > 20:
                                return jsonify({"login_token": token})
            except Exception:
                pass

        # Fallback: SIP credentials
        if _webrtc_cred["sip_username"] and _webrtc_cred["sip_password"]:
            return jsonify({
                "sip_username": _webrtc_cred["sip_username"],
                "sip_password": _webrtc_cred["sip_password"],
            })

        return jsonify({"error": "WebRTC not set up. Go to Settings > Setup WebRTC."}), 503

    @app.get("/sw.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript"), 200, {"Service-Worker-Allowed": "/"}

    @app.get("/health")
    def health():
        import os as _os
        db_path = storage.db_path
        on_volume = db_path.startswith("/data")
        return jsonify({
            "ok": True,
            "db_path": db_path,
            "persistent": on_volume,
            "storage_warning": None if on_volume else "No persistent volume — data lost on redeploy",
        })

    @app.get("/api/providers")
    @require_auth
    def list_providers():
        live = []
        for provider in providers.values():
            row = provider.provider_status()
            if provider.provider_id in provider_pricing:
                row.update(provider_pricing[provider.provider_id])
            row["pricing_profile"] = provider.pricing_profile()
            live.append(row)
        return jsonify({"providers": live})

    @app.get("/api/providers/balances")
    @require_auth
    def provider_balances():
        balances: list[dict[str, Any]] = []
        for provider in providers.values():
            if not provider.is_configured():
                continue
            try:
                details = provider.account_balance()
            except Exception as exc:
                details = {"balance": None, "currency": "USD", "error": str(exc)}
            balances.append(
                {
                    "provider": provider.provider_id,
                    "label": provider.label,
                    "account_balance": details,
                }
            )
        return jsonify({"balances": balances})

    @app.get("/api/wallet")
    @require_auth
    def wallet_summary():
        u = _get_session_user()
        uid = u["id"] if u else None
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        return jsonify(
            {
                "balance": storage.get_wallet_balance(user_id=uid),
                "transactions": storage.list_wallet_transactions(limit=limit, user_id=uid),
                "payment_orders": storage.list_payment_orders(user_id=uid, limit=20),
                "crypto_configured": crypto_configured(),
                "networks": get_supported_networks() if crypto_configured() else [],
            }
        )

    @app.post("/api/wallet/topup")
    @require_auth
    def wallet_topup():
        """Legacy manual top-up — admin only."""
        if not _is_admin():
            return jsonify({"error": "Admin access required for manual top-up."}), 403
        body = payload()
        amount = parse_float(body.get("amount"), 0.0)
        method = str(body.get("method", "manual")).strip() or "manual"
        target_user_id_raw = body.get("user_id")
        if target_user_id_raw:
            target_uid: int | None = int(target_user_id_raw)
        else:
            current_user = _get_session_user()
            target_uid = current_user["id"] if current_user else None
        try:
            result = storage.top_up_wallet(amount, method=method, user_id=target_uid)
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/wallet/create-order")
    @require_auth
    def wallet_create_order():
        """Create a crypto payment order for wallet top-up."""
        u = _get_session_user()
        body = payload()
        amount = parse_float(body.get("amount"), 0.0)
        network = str(body.get("network", "TRC20")).upper()
        if amount < 1.0:
            return jsonify({"error": "Minimum top-up is $1.00 USD."}), 400
        if not crypto_configured():
            return jsonify({"error": "Crypto payments not configured. Set CRYPTO_WALLET_TRC20."}), 503

        wallet_address = get_wallet_address(network)
        if not wallet_address:
            return jsonify({"error": f"Network {network} is not configured."}), 400

        order_id = f"2C-{uuid.uuid4().hex[:12].upper()}"
        order = storage.create_payment_order(
            order_id=order_id,
            amount_usd=amount,
            currency="USDT",
            deeplink="",
            paydify_txn_id="",
            user_id=u["id"] if u else None,
        )
        return jsonify({
            "ok": True,
            "order": order,
            "wallet_address": wallet_address,
            "network": network,
            "amount": amount,
            "token": "USDT",
        })

    @app.get("/api/wallet/order/<order_id>")
    @require_auth
    def wallet_order_status(order_id: str):
        """Poll the status of a payment order. Also triggers blockchain scan."""
        order = storage.get_payment_order(order_id)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        u = _get_session_user()
        if u and order.get("user_id") and order["user_id"] != u["id"] and not _is_admin():
            return jsonify({"error": "Not your order."}), 403

        # If still pending, try to scan blockchain for matching transaction
        if order["status"] == "pending":
            _try_auto_verify_order(order, storage)
            order = storage.get_payment_order(order_id) or order

        uid = order.get("user_id")
        return jsonify({
            "order": order,
            "wallet_balance": storage.get_wallet_balance(user_id=uid),
        })

    @app.post("/api/wallet/verify-tx")
    @require_auth
    def wallet_verify_tx():
        """User submits a tx hash for manual verification."""
        body = payload()
        order_id = str(body.get("order_id", "")).strip()
        tx_hash = str(body.get("tx_hash", "")).strip()
        if not order_id or not tx_hash:
            return jsonify({"error": "order_id and tx_hash are required."}), 400

        order = storage.get_payment_order(order_id)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        if order["status"] == "paid":
            return jsonify({"ok": True, "order": order, "message": "Already paid."})

        u = _get_session_user()
        if u and order.get("user_id") and order["user_id"] != u["id"] and not _is_admin():
            return jsonify({"error": "Not your order."}), 403

        # Verify on blockchain
        tx_info = verify_trc20_tx(tx_hash)
        if not tx_info:
            return jsonify({"error": "Transaction not found on blockchain. It may still be confirming — try again in a minute."}), 404

        expected_address = get_wallet_address("TRC20") or ""
        order_amount = float(order.get("amount_usd", 0))
        tx_amount = tx_info.get("amount", 0)

        # Validate: amount should be close enough (within $0.50 tolerance for rounding)
        if tx_amount < order_amount - 0.50:
            return jsonify({
                "error": f"Transaction amount ${tx_amount:.2f} is less than order amount ${order_amount:.2f}."
            }), 400

        # Mark as paid
        storage.mark_payment_order_paid(
            order_id=order_id,
            paydify_txn_id="",
            tx_hash=tx_hash,
            from_address=tx_info.get("from_address", ""),
            paid_amount=tx_amount,
        )
        updated = storage.get_payment_order(order_id)
        uid = order.get("user_id")
        return jsonify({
            "ok": True,
            "order": updated,
            "wallet_balance": storage.get_wallet_balance(user_id=uid),
            "message": f"Payment verified! ${tx_amount:.2f} credited.",
        })

    @app.get("/api/numbers")
    @require_auth
    def list_numbers():
        current_user = _get_session_user()
        is_admin = _is_admin()
        uid = current_user["id"] if current_user else None
        numbers = storage.list_numbers(user_id=uid, admin=is_admin)
        return jsonify({"numbers": numbers})

    @app.post("/api/numbers/search")
    @require_auth
    def search_numbers():
        body = payload()
        provider_id = body.get("provider", "mock")
        try:
            provider = provider_or_400(provider_id)
            results = provider.search_available_numbers(
                country=body.get("country", "US"),
                area_code=body.get("area_code") or None,
                city=body.get("city") or None,
                state=body.get("state") or None,
                limit=parse_int(body.get("limit"), 15, 1, 50),
                require_sms=parse_bool(body.get("require_sms"), True),
                require_voice=parse_bool(body.get("require_voice"), True),
                non_voip_only=parse_bool(body.get("non_voip_only"), True),
            )
            return jsonify({"provider": provider_id, "results": results})
        except (ProviderError, ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/numbers/pricing")
    @require_auth
    def number_pricing():
        return jsonify({
            "monthly": NUMBER_PRICE_MONTHLY,
            "yearly": NUMBER_PRICE_YEARLY,
            "yearly_monthly_equiv": round(NUMBER_PRICE_YEARLY / 12, 2),
            "yearly_savings": round(NUMBER_PRICE_MONTHLY * 12 - NUMBER_PRICE_YEARLY, 2),
        })

    @app.post("/api/numbers/purchase")
    @require_auth
    def purchase_number():
        body = payload()
        provider_id = str(body.get("provider", "mock")).lower()
        phone_number = str(body.get("phone_number", "")).strip()
        plan = str(body.get("plan", "monthly")).lower()
        if plan not in ("monthly", "yearly"):
            plan = "monthly"
        if not phone_number:
            return jsonify({"error": "phone_number is required."}), 400
        non_voip_only = parse_bool(body.get("non_voip_only"), True)

        try:
            provider = provider_or_400(provider_id)
            estimated_cost = estimate_action_cost(provider_id, "number_order", plan=plan)
            current_user = _get_session_user()
            uid = current_user["id"] if current_user else None
            ensure_wallet_can_cover(estimated_cost, provider_id, user_id=uid)
            result = provider.purchase_number(phone_number)
            line_type = str(result.get("line_type", "unknown")).lower()
            if non_voip_only and line_type == "voip":
                return jsonify({"error": "Provider classified this number as VoIP. Purchase blocked."}), 400
            record = storage.upsert_number(
                provider=provider_id,
                phone_number=result.get("phone_number", phone_number),
                provider_number_id=result.get("provider_number_id"),
                line_type=line_type,
                status="active",
                metadata={"plan": plan, "price": estimated_cost},
                user_id=uid,
            )
            wallet_info = None
            if uid is not None and estimated_cost > 0:
                try:
                    period = "12 months" if plan == "yearly" else "1 month"
                    charged = storage.charge_wallet(
                        amount=estimated_cost,
                        tx_type="number_order",
                        provider=provider_id,
                        description=f"Number {record['phone_number']} — {plan} ({period})",
                        reference_id=str(record.get("provider_number_id") or ""),
                        user_id=uid,
                    )
                    wallet_info = charged
                except ValueError:
                    pass
            return jsonify(
                {
                    "number": record,
                    "wallet": wallet_info,
                    "charged_usd": estimated_cost if uid else 0,
                    "plan": plan,
                    "warnings": result.get("warnings", []),
                }
            )
        except (ProviderError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/numbers/order")
    @require_auth
    def order_number():
        return purchase_number()

    @app.post("/api/numbers/<int:number_id>/renew")
    @require_auth
    def renew_number(number_id: int):
        """Renew a number subscription (monthly or yearly)."""
        number = storage.get_number(number_id)
        if not number:
            return jsonify({"error": f"Number {number_id} not found."}), 404
        body = payload()
        plan = str(body.get("plan", "monthly")).lower()
        if plan not in ("monthly", "yearly"):
            plan = "monthly"
        cost = NUMBER_PRICE_YEARLY if plan == "yearly" else NUMBER_PRICE_MONTHLY
        current_user = _get_session_user()
        uid = current_user["id"] if current_user else None
        try:
            ensure_wallet_can_cover(cost, number.get("provider", ""), user_id=uid)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if uid is not None and cost > 0:
            try:
                period = "12 months" if plan == "yearly" else "1 month"
                charged = storage.charge_wallet(
                    amount=cost,
                    tx_type="number_renewal",
                    provider=number.get("provider", ""),
                    description=f"Renew {number['phone_number']} — {plan} ({period})",
                    reference_id=str(number.get("provider_number_id") or ""),
                    user_id=uid,
                )
                return jsonify({
                    "ok": True,
                    "number": number,
                    "wallet": charged,
                    "charged_usd": cost,
                    "plan": plan,
                })
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "number": number, "charged_usd": 0, "plan": plan})

    @app.post("/api/numbers/<int:number_id>/release")
    @require_auth
    def release_number(number_id: int):
        number = storage.get_number(number_id)
        if not number:
            return jsonify({"error": f"Managed number {number_id} not found."}), 404
        provider_id = number.get("provider")
        try:
            provider = provider_or_400(provider_id)
            provider_number_id = resolve_provider_number_id(provider, number)
            if not provider_number_id:
                return jsonify({"error": "Could not resolve provider number ID for release."}), 400
            response = provider.release_number(provider_number_id)
            storage.remove_number(number_id)
            return jsonify({"released": True, "response": response})
        except (ProviderError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/numbers/<int:number_id>/transfer")
    @require_auth
    def transfer_number(number_id: int):
        body = payload()
        to_email = str(body.get("to_email", "")).strip().lower()
        if not to_email:
            return jsonify({"error": "to_email is required."}), 400
        current_user = _get_session_user()
        if not current_user:
            return jsonify({"error": "User session required."}), 401
        target_user = storage.get_user_by_email(to_email)
        if not target_user:
            return jsonify({"error": f"No user found with email {to_email}"}), 404
        if target_user["id"] == current_user["id"]:
            return jsonify({"error": "Cannot transfer to yourself."}), 400
        try:
            result = storage.transfer_number(number_id, current_user["id"], target_user["id"])
            return jsonify({"ok": True, "number": result, "transferred_to": to_email})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/numbers/sync")
    @require_auth
    def sync_owned_numbers():
        body = payload()
        provider_id = body.get("provider", "mock")
        try:
            provider = provider_or_400(provider_id)
            imported = 0
            for item in provider.list_owned_numbers():
                phone_number = item.get("phone_number", "")
                if not phone_number:
                    continue
                storage.upsert_number(
                    provider=provider_id,
                    phone_number=phone_number,
                    provider_number_id=item.get("provider_number_id"),
                    line_type=provider.lookup_line_type(phone_number),
                    status=item.get("status", "active"),
                    metadata={"synced": True},
                )
                imported += 1
            return jsonify({"provider": provider_id, "imported": imported})
        except (ProviderError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/admin/assign-number")
    @require_admin
    def admin_assign_number():
        """Admin: assign an existing Telnyx number to a user by email."""
        body = payload()
        phone_number = str(body.get("phone_number", "")).strip()
        email = str(body.get("email", "")).strip().lower()
        if not phone_number or not email:
            return jsonify({"error": "phone_number and email are required."}), 400
        user = storage.get_user_by_email(email)
        if not user:
            return jsonify({"error": f"User {email} not found."}), 404
        record = storage.upsert_number(
            provider="telnyx",
            phone_number=phone_number,
            provider_number_id=None,
            line_type="unknown",
            status="active",
            metadata={"assigned_to": email, "user_id": user["id"]},
            user_id=user["id"],
        )
        return jsonify({"ok": True, "number": record, "user": user})

    @app.get("/api/messages")
    @require_auth
    def list_messages():
        direction = request.args.get("direction")
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        is_admin = _is_admin()
        user_numbers: list[str] | None = None
        if not is_admin:
            current_user = _get_session_user()
            uid = current_user["id"] if current_user else None
            nums = storage.list_numbers(user_id=uid, admin=False)
            user_numbers = [n["phone_number"] for n in nums]
        return jsonify({"messages": storage.list_message_logs(
            limit=limit, direction=direction, user_numbers=user_numbers
        )})

    @app.post("/api/messages/send")
    @require_auth
    def send_message():
        body = payload()
        provider_id = str(body.get("provider", "mock")).lower()
        from_number = str(body.get("from_number", "")).strip()
        to_number = str(body.get("to_number", "")).strip()
        message = str(body.get("message", "")).strip()
        if not from_number or not to_number or not message:
            return jsonify({"error": "provider, from_number, to_number, and message are required."}), 400
        try:
            provider = provider_or_400(provider_id)
            estimated_cost = estimate_action_cost(provider_id, "sms")
            current_user = _get_session_user()
            uid = current_user["id"] if current_user else None
            ensure_wallet_can_cover(estimated_cost, provider_id, user_id=uid)
            result = provider.send_message(from_number, to_number, message)
            safe_result = {"id": str(result.get("id", "")), "status": str(result.get("status", "sent"))}
            try:
                raw = result.get("raw")
                log_response = raw if isinstance(raw, dict) else {}
            except Exception:
                log_response = {}
            storage.log_message(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                body=message,
                status=safe_result["status"],
                provider_message_id=safe_result["id"] or None,
                event_type="outbound_message",
                response=log_response,
            )
            wallet_info = None
            if uid is not None and estimated_cost > 0:
                try:
                    wallet_info = storage.charge_wallet(
                        amount=estimated_cost,
                        tx_type="sms",
                        provider=provider_id,
                        description=f"SMS {from_number} -> {to_number}",
                        reference_id=safe_result["id"],
                        user_id=uid,
                    )
                except ValueError:
                    pass
            return jsonify({"message": safe_result, "charged_usd": estimated_cost if wallet_info else 0})
        except (ProviderError, ValueError) as exc:
            storage.log_message(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                body=message,
                status="failed",
                provider_message_id=None,
                event_type="outbound_message",
                response={"error": str(exc)},
            )
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/calls")
    @require_auth
    def list_calls():
        direction = request.args.get("direction")
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        return jsonify({"calls": storage.list_call_logs(limit=limit, direction=direction)})

    @app.post("/api/calls/start")
    @require_auth
    def start_call():
        body = payload()
        provider_id = str(body.get("provider", "mock")).lower()
        from_number = str(body.get("from_number", "")).strip()
        to_number = str(body.get("to_number", "")).strip()
        personal_number = str(body.get("personal_number", "")).strip()
        say_text = str(body.get("say_text", "")).strip()
        if not from_number or not to_number:
            return jsonify({"error": "from_number and to_number are required."}), 400
        try:
            provider = provider_or_400(provider_id)
            estimated_minutes = parse_float(body.get("estimated_minutes"), 1.0)
            estimated_cost = estimate_action_cost(provider_id, "call", minutes=max(estimated_minutes, 1.0))
            current_user = _get_session_user()
            uid = current_user["id"] if current_user else None
            ensure_wallet_can_cover(estimated_cost, provider_id, user_id=uid)
            # If personal number provided, use bridge mode for live audio
            if personal_number:
                # Always use SignalWire for bridge calls (supports international numbers)
                sw_provider = providers.get("signalwire")
                if sw_provider and sw_provider.is_configured() and hasattr(sw_provider, 'start_bridged_call'):
                    # Use a SignalWire-owned number as caller ID
                    sw_from = from_number
                    try:
                        sw_numbers = sw_provider.list_owned_numbers()
                        if sw_numbers:
                            sw_from = sw_numbers[0].get("phone_number", from_number)
                    except Exception:
                        pass
                    result = sw_provider.start_bridged_call(sw_from, personal_number, to_number)
                elif hasattr(provider, 'start_bridged_call'):
                    result = provider.start_bridged_call(from_number, personal_number, to_number)
                else:
                    result = provider.start_call(from_number, personal_number, say_text)
            else:
                # Direct call (no bridge)
                result = provider.start_call(from_number, to_number, say_text)
            # Track that we initiated this call
            if result.get("id"):
                _active_calls[result["id"]] = {
                    "call_control_id": result["id"],
                    "from": from_number, "to": to_number,
                    "direction": "outbound",
                    "status": "calling_you" if personal_number else "ringing",
                    "mode": "bridge" if personal_number else "direct",
                }
                _our_outbound_numbers.add(to_number)
                if personal_number:
                    _our_outbound_numbers.add(personal_number)
                    _pending_bridges[result["id"]] = {
                        "from_number": from_number,
                        "to_number": to_number,
                        "provider_id": provider_id,
                    }
            safe_result = {"id": result.get("id"), "status": result.get("status")}
            storage.log_call(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                say_text=say_text,
                status=result.get("status", "queued"),
                provider_call_id=result.get("id"),
                event_type="outbound_call",
                response=result.get("raw") if isinstance(result.get("raw"), dict) else {},
            )
            if uid is not None and estimated_cost > 0:
                try:
                    charged = storage.charge_wallet(
                        amount=estimated_cost,
                        tx_type="call",
                        provider=provider_id,
                        description=f"Call {from_number} -> {to_number}",
                        reference_id=str(result.get("id") or ""),
                        user_id=uid,
                    )
                    return jsonify({"call": safe_result, "wallet": charged, "charged_usd": estimated_cost})
                except ValueError:
                    pass
            return jsonify({"call": safe_result, "charged_usd": 0})
        except (ProviderError, ValueError) as exc:
            storage.log_call(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                say_text=say_text,
                status="failed",
                provider_call_id=None,
                event_type="outbound_call",
                response={"error": str(exc)},
            )
            return jsonify({"error": str(exc)}), 400

    @app.post("/webhooks/twilio/message")
    def twilio_message_webhook():
        form = request.form.to_dict()
        from_number = str(form.get("From", "")).strip()
        to_number = str(form.get("To", "")).strip()
        body_text = str(form.get("Body", "")).strip()
        message_sid = str(form.get("MessageSid", "")).strip() or None
        status = str(form.get("SmsStatus", form.get("MessageStatus", "received"))).strip() or "received"
        storage.record_webhook_event("twilio", "message", form)
        storage.log_message(
            provider="twilio",
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            body=body_text,
            status=status,
            provider_message_id=message_sid,
            event_type="inbound_message",
            response=form,
        )
        return jsonify({"ok": True})

    @app.post("/webhooks/twilio/voice")
    def twilio_voice_webhook():
        form = request.form.to_dict()
        from_number = str(form.get("From", "")).strip()
        to_number = str(form.get("To", "")).strip()
        call_sid = str(form.get("CallSid", "")).strip() or None
        status = str(form.get("CallStatus", "ringing")).strip() or "ringing"
        storage.record_webhook_event("twilio", "voice", form)
        storage.log_call(
            provider="twilio",
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            say_text="inbound",
            status=status,
            provider_call_id=call_sid,
            event_type="inbound_call",
            response=form,
        )
        say_text = os.environ.get(
            "TWILIO_INBOUND_SAY_TEXT",
            "Thanks for calling. Your call was received by 2ndCall.",
        )
        twiml = f"<Response><Say>{say_text}</Say></Response>"
        return Response(twiml, mimetype="text/xml")

    # In-memory store for active incoming calls (for polling by browser)
    _incoming_calls: list[dict[str, Any]] = []
    _active_calls: dict[str, dict[str, Any]] = {}
    _our_outbound_numbers: set[str] = set()
    _pending_bridges: dict[str, dict[str, Any]] = {}  # first_call_id -> bridge info

    @app.get("/api/calls/active")
    @require_auth
    def get_active_calls():
        """Poll for active outbound call status."""
        import time
        now = time.time()
        # Clean up old calls (> 5 minutes)
        stale = [k for k, v in _active_calls.items() if now - v.get("_ts", 0) > 300]
        for k in stale:
            _active_calls.pop(k, None)
        return jsonify({"calls": list(_active_calls.values())})

    @app.get("/api/calls/incoming")
    @require_auth
    def get_incoming_calls():
        """Poll for incoming calls waiting to be answered."""
        import time
        now = time.time()
        active = [c for c in _incoming_calls if now - c.get("_ts", 0) < 60]
        _incoming_calls[:] = active
        return jsonify({"calls": active})

    @app.post("/api/calls/answer")
    @require_auth
    def answer_incoming_call():
        """Answer an incoming call and speak a greeting."""
        body = payload()
        call_control_id = str(body.get("call_control_id", "")).strip()
        if not call_control_id:
            return jsonify({"error": "call_control_id is required."}), 400
        tp = providers.get("telnyx")
        if not tp or not tp.is_configured():
            return jsonify({"error": "Telnyx not configured."}), 503
        headers = {"Authorization": f"Bearer {tp.api_key}", "Content-Type": "application/json"}
        try:
            # Answer the call
            resp = http_requests.post(
                f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/answer",
                headers=headers, json={}, timeout=10,
            )
            if resp.status_code >= 400:
                return jsonify({"error": f"Failed to answer: {resp.text}"}), 502
            # Remove from incoming list
            _incoming_calls[:] = [c for c in _incoming_calls if c.get("call_control_id") != call_control_id]
            return jsonify({"ok": True, "call_control_id": call_control_id})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/calls/hangup")
    @require_auth
    def hangup_call():
        """Hang up a call by call_control_id."""
        body = payload()
        call_control_id = str(body.get("call_control_id", "")).strip()
        if not call_control_id:
            return jsonify({"error": "call_control_id is required."}), 400
        tp = providers.get("telnyx")
        if not tp or not tp.is_configured():
            return jsonify({"error": "Telnyx not configured."}), 503
        headers = {"Authorization": f"Bearer {tp.api_key}", "Content-Type": "application/json"}
        try:
            http_requests.post(
                f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/hangup",
                headers=headers, json={}, timeout=10,
            )
            _incoming_calls[:] = [c for c in _incoming_calls if c.get("call_control_id") != call_control_id]
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/webhooks/telnyx/events")
    def telnyx_events_webhook():
        body = request.get_json(silent=True) or {}
        data = body.get("data", {})
        event_type = str(data.get("event_type", body.get("event_type", "unknown"))).strip() or "unknown"
        payload_data = data.get("payload", {})
        storage.record_webhook_event("telnyx", event_type, body)

        if "message" in event_type:
            # Handle both nested and flat payload formats
            from_field = payload_data.get("from", {})
            to_field = payload_data.get("to", [{}])
            if isinstance(from_field, dict):
                from_number = str(from_field.get("phone_number", "")).strip()
            else:
                from_number = str(from_field).strip()
            if isinstance(to_field, list) and to_field:
                first_to = to_field[0]
                to_number = str(first_to.get("phone_number", "") if isinstance(first_to, dict) else first_to).strip()
            elif isinstance(to_field, dict):
                to_number = str(to_field.get("phone_number", "")).strip()
            else:
                to_number = str(to_field).strip()
            text = str(payload_data.get("text", payload_data.get("body", ""))).strip()
            direction = "inbound" if "received" in event_type or "inbound" in event_type else "outbound"
            storage.log_message(
                provider="telnyx",
                direction=direction,
                from_number=from_number,
                to_number=to_number,
                body=text,
                status=event_type,
                provider_message_id=str(payload_data.get("id", "")) or None,
                event_type=event_type,
                response=body,
            )

        if "call" in event_type:
            from_number = str(payload_data.get("from", "")).strip()
            to_number = str(payload_data.get("to", "")).strip()
            call_control_id = str(payload_data.get("call_control_id", "")).strip()
            call_leg_id = str(payload_data.get("call_leg_id", "")).strip()
            direction_raw = str(payload_data.get("direction", "")).strip()
            direction = "inbound" if direction_raw == "incoming" else "outbound"

            storage.log_call(
                provider="telnyx",
                direction=direction,
                from_number=from_number,
                to_number=to_number,
                say_text="webhook",
                status=event_type,
                provider_call_id=call_leg_id or None,
                event_type=event_type,
                response=body,
            )

            telnyx_provider = providers.get("telnyx")
            api_key = telnyx_provider.api_key if telnyx_provider else ""
            cc_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            # ── Determine if this is a truly external incoming call ──
            is_our_outbound = (
                from_number in _our_outbound_numbers
                or to_number in _our_outbound_numbers
                or call_control_id in _active_calls
            )

            # ── Incoming call: only show if it's truly from outside ──
            if event_type == "call.initiated" and direction_raw == "incoming" and call_control_id and not is_our_outbound:
                import time as _time
                _incoming_calls.append({
                    "call_control_id": call_control_id,
                    "call_leg_id": call_leg_id,
                    "from": from_number,
                    "to": to_number,
                    "event_type": event_type,
                    "_ts": _time.time(),
                })

            # ── Outgoing call initiated: track it ──
            if event_type == "call.initiated" and direction_raw != "incoming" and call_control_id:
                import time as _time
                _active_calls[call_control_id] = {
                    "call_control_id": call_control_id,
                    "from": from_number,
                    "to": to_number,
                    "direction": "outbound",
                    "status": "ringing",
                    "_ts": _time.time(),
                }

            # ── Call answered: bridge or speak TTS ──
            if event_type == "call.answered" and call_control_id:
                if call_control_id in _active_calls:
                    _active_calls[call_control_id]["status"] = "answered"

                # Check if this is part of a bridge (first leg answered)
                if call_control_id in _pending_bridges and api_key:
                    bridge = _pending_bridges[call_control_id]
                    # User answered their phone - now call the recipient
                    try:
                        # Tell the user we're connecting
                        http_requests.post(
                            f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/speak",
                            headers=cc_headers,
                            json={"payload": "Connecting you now. Please hold.", "voice": "female", "language": "en-US"},
                            timeout=10,
                        )
                        # Start the second call to the recipient
                        tp = providers.get(bridge.get("provider_id", "telnyx"))
                        if tp:
                            result2 = tp.start_call(bridge["from_number"], bridge["to_number"], "")
                            leg2_id = result2.get("id", "")
                            if leg2_id:
                                # Store bridge info on second leg too
                                _pending_bridges[leg2_id] = {
                                    "bridge_with": call_control_id,
                                    "leg": "second",
                                }
                                _pending_bridges[call_control_id]["leg2_id"] = leg2_id
                                _active_calls[call_control_id]["status"] = "connecting"
                                _our_outbound_numbers.add(bridge["to_number"])
                    except Exception:
                        pass

                # Check if this is the second leg being answered - bridge the calls
                elif call_control_id in _pending_bridges and _pending_bridges[call_control_id].get("leg") == "second" and api_key:
                    bridge = _pending_bridges[call_control_id]
                    first_call_id = bridge.get("bridge_with", "")
                    if first_call_id:
                        try:
                            # Bridge the two calls together
                            http_requests.post(
                                f"https://api.telnyx.com/v2/calls/{first_call_id}/actions/bridge",
                                headers=cc_headers,
                                json={"call_control_id": call_control_id},
                                timeout=10,
                            )
                            # Update status
                            if first_call_id in _active_calls:
                                _active_calls[first_call_id]["status"] = "bridged"
                        except Exception:
                            pass

                # Regular call (no bridge) - speak TTS to keep alive
                elif api_key and call_control_id in _active_calls and call_control_id not in _pending_bridges:
                    try:
                        http_requests.post(
                            f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/speak",
                            headers=cc_headers,
                            json={"payload": "Connected through 2nd Call.", "voice": "female", "language": "en-US"},
                            timeout=10,
                        )
                    except Exception:
                        pass

            # ── Call hangup: clean up ──
            if event_type == "call.hangup" and call_control_id:
                _incoming_calls[:] = [c for c in _incoming_calls if c.get("call_control_id") != call_control_id]
                _active_calls.pop(call_control_id, None)

        return jsonify({"received": True})

    @app.get("/api/conversations")
    @require_auth
    def list_conversations():
        """Return conversations grouped by contact number, most recent first."""
        current_user = _get_session_user()
        uid = current_user["id"] if current_user else None
        # Get user's numbers for filtering
        is_admin = _is_admin()
        user_numbers = set()
        if uid and not is_admin:
            for n in storage.list_numbers(user_id=uid):
                user_numbers.add(n["phone_number"])
        all_msgs = storage.list_message_logs(limit=1000)
        convos: dict[str, dict[str, Any]] = {}
        for msg in reversed(all_msgs):
            # Filter: non-admin users only see messages for their numbers
            if not is_admin:
                if not user_numbers:
                    break  # user has no numbers, no conversations to show
                if msg["from_number"] not in user_numbers and msg["to_number"] not in user_numbers:
                    continue
            contact = msg["from_number"] if msg["direction"] == "inbound" else msg["to_number"]
            my_num = msg["to_number"] if msg["direction"] == "inbound" else msg["from_number"]
            if contact not in convos:
                convos[contact] = {
                    "contact": contact,
                    "my_number": my_num,
                    "provider": msg["provider"],
                    "last_body": msg["body"],
                    "last_time": msg["created_at"],
                    "last_direction": msg["direction"],
                    "message_count": 0,
                }
            convos[contact]["last_body"] = msg["body"]
            convos[contact]["last_time"] = msg["created_at"]
            convos[contact]["last_direction"] = msg["direction"]
            convos[contact]["message_count"] += 1
        result = sorted(convos.values(), key=lambda x: x["last_time"], reverse=True)
        return jsonify({"conversations": result, "total": len(result)})

    @app.post("/api/conversations/thread")
    @require_auth
    def get_conversation_thread():
        """Return all messages with a specific contact number (POST avoids + encoding in URL)."""
        body = payload()
        contact_number = str(body.get("contact", "")).strip()
        if not contact_number:
            return jsonify({"error": "contact is required"}), 400
        current_user = _get_session_user()
        uid = current_user["id"] if current_user else None
        user_numbers = set()
        if uid and not _is_admin():
            for n in storage.list_numbers(user_id=uid):
                user_numbers.add(n["phone_number"])
        all_msgs = storage.list_message_logs(limit=500)
        thread = [
            m for m in all_msgs
            if ((m["direction"] == "inbound" and m["from_number"] == contact_number)
            or (m["direction"] == "outbound" and m["to_number"] == contact_number))
            and (_is_admin() or not user_numbers or m["from_number"] in user_numbers or m["to_number"] in user_numbers)
        ]
        thread.sort(key=lambda x: x["created_at"])
        return jsonify({"messages": thread, "contact": contact_number, "count": len(thread)})

    @app.get("/api/export")
    @require_auth
    def export_data():
        return jsonify(
            {
                "numbers": storage.list_numbers(),
                "wallet_balance": storage.get_wallet_balance(),
                "messages": storage.list_message_logs(limit=200),
                "calls": storage.list_call_logs(limit=200),
                "pricing": provider_pricing,
            }
        )

    @app.get("/api/debug/webhook-test")
    def webhook_test():
        """Simple GET endpoint to test if the webhook URL is reachable."""
        return jsonify({"ok": True, "message": "Webhook endpoint is reachable. Use POST for actual webhooks.", "path": "/webhooks/telnyx/events"})

    @app.get("/webhooks/telnyx/events")
    def telnyx_webhook_get():
        """GET handler so you can test the URL in a browser."""
        return jsonify({"ok": True, "message": "Telnyx webhook endpoint is active. Telnyx will POST events here."})

    @app.get("/api/debug/webhooks")
    @require_admin
    def debug_webhooks():
        """View recent webhook events for debugging."""
        with storage._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_webhook_events ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        events = []
        for r in rows:
            d = dict(r)
            try:
                import json as _json
                d["payload"] = _json.loads(d.get("payload_json", "{}"))
            except Exception:
                d["payload"] = d.get("payload_json", "")
            d.pop("payload_json", None)
            events.append(d)
        return jsonify({"events": events, "active_calls": list(_active_calls.values()), "incoming_calls": _incoming_calls})

    def _try_auto_verify_order(order: dict[str, Any], store: Storage) -> bool:
        """Scan blockchain for transactions matching a pending order."""
        from .payments import WALLET_TRC20, _iso_to_ms
        if not WALLET_TRC20 or order["status"] != "pending":
            return False

        order_created_ms = _iso_to_ms(order.get("created_at", ""))
        # Scan from 1 minute before order creation
        min_ts = max(0, order_created_ms - 60000)
        txns = scan_trc20_transactions(WALLET_TRC20, min_timestamp_ms=min_ts, limit=20)
        if not txns:
            return False

        matches = match_payment_to_orders(txns, [order], WALLET_TRC20)
        if not matches:
            return False

        tx, matched_order = matches[0]
        store.mark_payment_order_paid(
            order_id=matched_order["order_id"],
            paydify_txn_id="",
            tx_hash=tx["tx_hash"],
            from_address=tx.get("from_address", ""),
            paid_amount=tx["amount"],
        )
        return True

    @app.get("/api/wallet/scan")
    @require_admin
    def wallet_scan_blockchain():
        """Admin: manually trigger blockchain scan for all pending orders."""
        from .payments import WALLET_TRC20
        if not WALLET_TRC20:
            return jsonify({"error": "No TRC20 wallet configured."}), 503

        pending = [o for o in storage.list_payment_orders(limit=50) if o["status"] == "pending"]
        if not pending:
            return jsonify({"scanned": 0, "matched": 0, "message": "No pending orders."})

        txns = scan_trc20_transactions(WALLET_TRC20, limit=50)
        matches = match_payment_to_orders(txns, pending, WALLET_TRC20)

        for tx, order in matches:
            storage.mark_payment_order_paid(
                order_id=order["order_id"],
                paydify_txn_id="",
                tx_hash=tx["tx_hash"],
                from_address=tx.get("from_address", ""),
                paid_amount=tx["amount"],
            )

        return jsonify({
            "scanned": len(txns),
            "pending_orders": len(pending),
            "matched": len(matches),
        })

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("NUMBER_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("NUMBER_APP_PORT", "5050")))
    debug = parse_bool(os.environ.get("NUMBER_APP_DEBUG"), False)
    app.run(host=host, port=port, debug=debug)
