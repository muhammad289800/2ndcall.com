import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

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
    app.config["JSON_SORT_KEYS"] = False

    storage = Storage()
    providers = build_providers()

    provider_pricing = {
        "telnyx": {
            "rank": 1,
            "label": "Telnyx",
            "estimated_local_number_monthly_usd": "from $1.00",
            "notes": "Strong low-cost API option for SMS/voice workloads.",
            "integrated_in_app": True,
        },
        "plivo": {
            "rank": 2,
            "label": "Plivo",
            "estimated_local_number_monthly_usd": "from $0.50",
            "notes": "Very low number rental cost; not wired in this build yet.",
            "integrated_in_app": False,
        },
        "twilio": {
            "rank": 3,
            "label": "Twilio",
            "estimated_local_number_monthly_usd": "about $1.15",
            "notes": "Broad ecosystem and reliability, usually higher unit cost.",
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
        if not provider.is_configured() and provider.provider_id != "mock":
            raise ValueError(f"Provider '{provider_id}' is not configured.")
        return provider

    def ensure_wallet_can_cover(amount: float) -> None:
        if amount <= 0:
            return
        balance = storage.get_wallet_balance()
        if balance < amount:
            raise ValueError(
                f"Insufficient wallet balance. Need ${amount:.2f} but only have ${balance:.2f}. "
                "Top up wallet first."
            )

    def estimate_action_cost(provider_id: str, action: str, minutes: float = 1.0) -> float:
        provider = providers[provider_id]
        profile = provider.pricing_profile()
        if action == "number_order":
            return parse_float(profile.get("number_monthly_usd"), 1.0)
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

    @app.get("/")
    def home():
        pricing_rows = sorted(provider_pricing.values(), key=lambda item: item["rank"])
        return render_template(
            "index.html",
            providers=providers,
            pricing_rows=pricing_rows,
        )

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/api/providers")
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
    def provider_balances():
        balances: list[dict[str, Any]] = []
        for provider in providers.values():
            if provider.provider_id != "mock" and not provider.is_configured():
                continue
            try:
                details = provider.account_balance()
            except Exception as exc:  # pragma: no cover - external APIs
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
    def wallet_summary():
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        return jsonify(
            {
                "balance": storage.get_wallet_balance(),
                "transactions": storage.list_wallet_transactions(limit=limit),
            }
        )

    @app.post("/api/wallet/topup")
    def wallet_topup():
        body = payload()
        amount = parse_float(body.get("amount"), 0.0)
        method = str(body.get("method", "manual")).strip() or "manual"
        try:
            result = storage.top_up_wallet(amount, method=method)
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/numbers")
    def list_numbers():
        return jsonify({"numbers": storage.list_numbers()})

    @app.post("/api/numbers/search")
    def search_numbers():
        body = payload()
        provider_id = body.get("provider", "mock")
        try:
            provider = provider_or_400(provider_id)
            results = provider.search_available_numbers(
                country=body.get("country", "US"),
                area_code=body.get("area_code") or None,
                limit=parse_int(body.get("limit"), 15, 1, 50),
                require_sms=parse_bool(body.get("require_sms"), True),
                require_voice=parse_bool(body.get("require_voice"), True),
                non_voip_only=parse_bool(body.get("non_voip_only"), True),
            )
            return jsonify({"provider": provider_id, "results": results})
        except (ProviderError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/numbers/purchase")
    def purchase_number():
        body = payload()
        provider_id = str(body.get("provider", "mock")).lower()
        phone_number = str(body.get("phone_number", "")).strip()
        if not phone_number:
            return jsonify({"error": "phone_number is required."}), 400
        non_voip_only = parse_bool(body.get("non_voip_only"), True)

        try:
            provider = provider_or_400(provider_id)
            estimated_cost = estimate_action_cost(provider_id, "number_order")
            ensure_wallet_can_cover(estimated_cost)
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
                metadata={"raw": result.get("raw", {})},
            )
            charged = storage.charge_wallet(
                amount=estimated_cost,
                tx_type="number_order",
                provider=provider_id,
                description=f"Ordered number {record['phone_number']}",
                reference_id=str(record.get("provider_number_id") or ""),
            )
            return jsonify({"number": record, "wallet": charged, "charged_usd": estimated_cost})
        except (ProviderError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/numbers/order")
    def order_number():
        # Alias for purchase to make "ordering numbers" explicit in API.
        return purchase_number()

    @app.post("/api/numbers/<int:number_id>/release")
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

    @app.post("/api/numbers/sync")
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

    @app.get("/api/messages")
    def list_messages():
        direction = request.args.get("direction")
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        return jsonify({"messages": storage.list_message_logs(limit=limit, direction=direction)})

    @app.post("/api/messages/send")
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
            ensure_wallet_can_cover(estimated_cost)
            result = provider.send_message(from_number, to_number, message)
            storage.log_message(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                body=message,
                status=result.get("status", "queued"),
                provider_message_id=result.get("id"),
                event_type="outbound_message",
                response=result.get("raw"),
            )
            charged = storage.charge_wallet(
                amount=estimated_cost,
                tx_type="sms",
                provider=provider_id,
                description=f"SMS {from_number} -> {to_number}",
                reference_id=str(result.get("id") or ""),
            )
            return jsonify({"message": result, "wallet": charged, "charged_usd": estimated_cost})
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
    def list_calls():
        direction = request.args.get("direction")
        limit = parse_int(request.args.get("limit"), 100, 1, 500)
        return jsonify({"calls": storage.list_call_logs(limit=limit, direction=direction)})

    @app.post("/api/calls/start")
    def start_call():
        body = payload()
        provider_id = str(body.get("provider", "mock")).lower()
        from_number = str(body.get("from_number", "")).strip()
        to_number = str(body.get("to_number", "")).strip()
        say_text = str(body.get("say_text", "")).strip()
        if not from_number or not to_number:
            return jsonify({"error": "provider, from_number, and to_number are required."}), 400
        try:
            provider = provider_or_400(provider_id)
            estimated_minutes = parse_float(body.get("estimated_minutes"), 1.0)
            estimated_cost = estimate_action_cost(provider_id, "call", minutes=max(estimated_minutes, 1.0))
            ensure_wallet_can_cover(estimated_cost)
            result = provider.start_call(from_number, to_number, say_text)
            storage.log_call(
                provider=provider_id,
                direction="outbound",
                from_number=from_number,
                to_number=to_number,
                say_text=say_text,
                status=result.get("status", "queued"),
                provider_call_id=result.get("id"),
                event_type="outbound_call",
                response=result.get("raw"),
            )
            charged = storage.charge_wallet(
                amount=estimated_cost,
                tx_type="call",
                provider=provider_id,
                description=f"Call {from_number} -> {to_number}",
                reference_id=str(result.get("id") or ""),
            )
            return jsonify({"call": result, "wallet": charged, "charged_usd": estimated_cost})
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
            "Thanks for calling. Your call was received by the 2ndCall app.",
        )
        twiml = f"<Response><Say>{say_text}</Say></Response>"
        return Response(twiml, mimetype="text/xml")

    @app.post("/webhooks/telnyx/events")
    def telnyx_events_webhook():
        body = request.get_json(silent=True) or {}
        data = body.get("data", {})
        event_type = str(data.get("event_type", body.get("event_type", "unknown"))).strip() or "unknown"
        payload_data = data.get("payload", {})
        storage.record_webhook_event("telnyx", event_type, body)

        if "message" in event_type:
            from_number = str(payload_data.get("from", {}).get("phone_number", "")).strip()
            to_number = str(payload_data.get("to", [{}])[0].get("phone_number", "")).strip()
            text = str(payload_data.get("text", "")).strip()
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
            direction = "inbound" if "answered" in event_type or "initiated" in event_type else "outbound"
            storage.log_call(
                provider="telnyx",
                direction=direction,
                from_number=from_number,
                to_number=to_number,
                say_text="webhook",
                status=event_type,
                provider_call_id=str(payload_data.get("call_leg_id", "")) or None,
                event_type=event_type,
                response=body,
            )

        return jsonify({"received": True})

    @app.get("/api/export")
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

    return app


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("NUMBER_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("NUMBER_APP_PORT", "5050")))
    debug = parse_bool(os.environ.get("NUMBER_APP_DEBUG"), False)
    app.run(host=host, port=port, debug=debug)

