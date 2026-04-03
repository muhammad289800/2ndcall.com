import os
import random
import uuid
from typing import Any
from urllib.parse import quote

import requests


class ProviderError(RuntimeError):
    pass


class BaseProvider:
    provider_id = "base"
    label = "Base"

    def is_configured(self) -> bool:
        return True

    def search_available_numbers(
        self,
        country: str,
        area_code: str | None,
        limit: int,
        require_sms: bool,
        require_voice: bool,
        non_voip_only: bool,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def purchase_number(self, phone_number: str) -> dict[str, Any]:
        raise NotImplementedError

    def list_owned_numbers(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def release_number(self, provider_number_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def send_message(self, from_number: str, to_number: str, body: str) -> dict[str, Any]:
        raise NotImplementedError

    def start_call(self, from_number: str, to_number: str, say_text: str) -> dict[str, Any]:
        raise NotImplementedError

    def lookup_line_type(self, phone_number: str) -> str:
        return "unknown"

    def provider_status(self) -> dict[str, Any]:
        return {
            "provider": self.provider_id,
            "label": self.label,
            "configured": self.is_configured(),
        }

    def pricing_profile(self) -> dict[str, Any]:
        return {
            "number_monthly_usd": 1.0,
            "sms_outbound_usd": 0.01,
            "call_per_min_usd": 0.02,
        }

    def account_balance(self) -> dict[str, Any]:
        return {"balance": None, "currency": "USD", "source": "not_available"}


class MockProvider(BaseProvider):
    provider_id = "mock"
    label = "Mock Provider (Local Testing)"

    def _generate_number(self, area_code: str | None) -> str:
        ac = area_code if area_code and area_code.isdigit() else "415"
        tail = f"{random.randint(1000000, 9999999)}"
        return f"+1{ac}{tail[: 10 - len(ac)]}"

    def search_available_numbers(
        self,
        country: str,
        area_code: str | None,
        limit: int,
        require_sms: bool,
        require_voice: bool,
        non_voip_only: bool,
    ) -> list[dict[str, Any]]:
        offers: list[dict[str, Any]] = []
        line_cycle = ["mobile", "landline", "voip"]
        for index in range(limit):
            line_type = line_cycle[index % len(line_cycle)]
            if non_voip_only and line_type == "voip":
                continue
            offers.append(
                {
                    "phone_number": self._generate_number(area_code),
                    "provider_number_id": f"mock-{uuid.uuid4()}",
                    "capabilities": {"sms": require_sms, "voice": require_voice},
                    "locality": "San Francisco",
                    "region": "CA",
                    "line_type": line_type,
                    "monthly_cost_estimate": 0.75,
                }
            )
        return offers

    def purchase_number(self, phone_number: str) -> dict[str, Any]:
        return {
            "phone_number": phone_number,
            "provider_number_id": f"mock-{uuid.uuid4()}",
            "line_type": "mobile",
            "raw": {"mock": True},
        }

    def list_owned_numbers(self) -> list[dict[str, Any]]:
        return []

    def release_number(self, provider_number_id: str) -> dict[str, Any]:
        return {"released": True, "provider_number_id": provider_number_id}

    def send_message(self, from_number: str, to_number: str, body: str) -> dict[str, Any]:
        return {
            "id": f"mock-msg-{uuid.uuid4()}",
            "status": "queued",
            "raw": {"from": from_number, "to": to_number, "body": body},
        }

    def start_call(self, from_number: str, to_number: str, say_text: str) -> dict[str, Any]:
        return {
            "id": f"mock-call-{uuid.uuid4()}",
            "status": "queued",
            "raw": {"from": from_number, "to": to_number, "say_text": say_text},
        }

    def pricing_profile(self) -> dict[str, Any]:
        return {
            "number_monthly_usd": 0.75,
            "sms_outbound_usd": 0.005,
            "call_per_min_usd": 0.01,
        }

    def account_balance(self) -> dict[str, Any]:
        return {"balance": 1000.0, "currency": "USD", "source": "mock"}


class TwilioProvider(BaseProvider):
    provider_id = "twilio"
    label = "Twilio"
    base_url = "https://api.twilio.com/2010-04-01"

    def __init__(self) -> None:
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ProviderError("Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                data=data,
                auth=(self.account_sid, self.auth_token),
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Twilio request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"Twilio API error {response.status_code}: {response.text}")
        payload = response.json() if response.text else {}
        return payload

    def lookup_line_type(self, phone_number: str) -> str:
        if not self.is_configured():
            return "unknown"
        url = f"https://lookups.twilio.com/v2/PhoneNumbers/{quote(phone_number, safe='')}"
        try:
            response = requests.get(
                url,
                params={"Fields": "line_type_intelligence"},
                auth=(self.account_sid, self.auth_token),
                timeout=20,
            )
            if response.status_code >= 400:
                return "unknown"
            data = response.json()
            return data.get("line_type_intelligence", {}).get("type", "unknown")
        except requests.RequestException:
            return "unknown"

    def search_available_numbers(
        self,
        country: str,
        area_code: str | None,
        limit: int,
        require_sms: bool,
        require_voice: bool,
        non_voip_only: bool,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "PageSize": limit,
            "SmsEnabled": str(require_sms).lower(),
            "VoiceEnabled": str(require_voice).lower(),
        }
        if area_code:
            params["AreaCode"] = area_code
        payload = self._request(
            "GET",
            f"/Accounts/{self.account_sid}/AvailablePhoneNumbers/{country.upper()}/Local.json",
            params=params,
        )
        offers: list[dict[str, Any]] = []
        for item in payload.get("available_phone_numbers", []):
            line_type = "unknown"
            if non_voip_only:
                line_type = self.lookup_line_type(item.get("phone_number", ""))
            if non_voip_only and line_type == "voip":
                continue
            capabilities = item.get("capabilities", {})
            offers.append(
                {
                    "phone_number": item.get("phone_number"),
                    "provider_number_id": None,
                    "capabilities": {
                        "sms": bool(capabilities.get("SMS") or capabilities.get("sms")),
                        "voice": bool(capabilities.get("voice") or capabilities.get("Voice")),
                    },
                    "locality": item.get("locality"),
                    "region": item.get("region"),
                    "line_type": line_type,
                    "monthly_cost_estimate": 1.15,
                }
            )
        return offers

    def purchase_number(self, phone_number: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            f"/Accounts/{self.account_sid}/IncomingPhoneNumbers.json",
            data={"PhoneNumber": phone_number},
        )
        return {
            "phone_number": payload.get("phone_number", phone_number),
            "provider_number_id": payload.get("sid"),
            "line_type": self.lookup_line_type(phone_number),
            "raw": payload,
        }

    def list_owned_numbers(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/Accounts/{self.account_sid}/IncomingPhoneNumbers.json",
            params={"PageSize": 200},
        )
        numbers: list[dict[str, Any]] = []
        for item in payload.get("incoming_phone_numbers", []):
            numbers.append(
                {
                    "provider_number_id": item.get("sid"),
                    "phone_number": item.get("phone_number"),
                    "status": item.get("status", "active"),
                }
            )
        return numbers

    def release_number(self, provider_number_id: str) -> dict[str, Any]:
        self._request(
            "DELETE",
            f"/Accounts/{self.account_sid}/IncomingPhoneNumbers/{provider_number_id}.json",
        )
        return {"released": True, "provider_number_id": provider_number_id}

    def send_message(self, from_number: str, to_number: str, body: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            f"/Accounts/{self.account_sid}/Messages.json",
            data={"From": from_number, "To": to_number, "Body": body},
        )
        return {"id": payload.get("sid"), "status": payload.get("status"), "raw": payload}

    def start_call(self, from_number: str, to_number: str, say_text: str) -> dict[str, Any]:
        twiml = f"<Response><Say>{say_text or 'This is a test call from your number management app.'}</Say></Response>"
        payload = self._request(
            "POST",
            f"/Accounts/{self.account_sid}/Calls.json",
            data={"From": from_number, "To": to_number, "Twiml": twiml},
        )
        return {"id": payload.get("sid"), "status": payload.get("status"), "raw": payload}

    def pricing_profile(self) -> dict[str, Any]:
        return {
            "number_monthly_usd": 1.15,
            "sms_outbound_usd": 0.0085,
            "call_per_min_usd": 0.014,
        }

    def account_balance(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"balance": None, "currency": "USD", "source": "not_configured"}
        payload = self._request("GET", f"/Accounts/{self.account_sid}/Balance.json")
        try:
            amount = float(payload.get("balance", "0"))
        except (TypeError, ValueError):
            amount = 0.0
        return {"balance": amount, "currency": payload.get("currency", "USD"), "source": "twilio"}


class TelnyxProvider(BaseProvider):
    provider_id = "telnyx"
    label = "Telnyx"
    base_url = "https://api.telnyx.com/v2"

    def __init__(self) -> None:
        self.api_key = os.environ.get("TELNYX_API_KEY", "")
        self.connection_id = os.environ.get("TELNYX_CONNECTION_ID", "")
        self.sip_connection_id = os.environ.get("TELNYX_SIP_CONNECTION_ID", "")
        self.messaging_profile_id = os.environ.get("TELNYX_MESSAGING_PROFILE_ID", "")
        self.call_webhook_url = os.environ.get("TELNYX_CALL_WEBHOOK_URL", "")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | list[tuple[str, str]] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ProviderError("Telnyx is not configured. Set TELNYX_API_KEY.")
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_payload,
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Telnyx request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"Telnyx API error {response.status_code}: {response.text}")
        return response.json() if response.text else {}

    def lookup_line_type(self, phone_number: str) -> str:
        if not self.is_configured():
            return "unknown"
        try:
            payload = self._request(
                "GET",
                f"/number_lookup/{quote(phone_number, safe='')}",
                params={"type": "carrier"},
            )
        except ProviderError:
            return "unknown"
        data = payload.get("data", {})
        portability = data.get("portability", {})
        carrier = data.get("carrier", {})
        return portability.get("line_type") or carrier.get("type") or "unknown"

    def search_available_numbers(
        self,
        country: str,
        area_code: str | None,
        limit: int,
        require_sms: bool,
        require_voice: bool,
        non_voip_only: bool,
    ) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = [
            ("filter[country_code]", country.upper()),
            ("page[size]", str(limit)),
        ]
        if require_sms:
            params.append(("filter[features][]", "sms"))
        if require_voice:
            params.append(("filter[features][]", "voice"))
        if area_code:
            params.append(("filter[national_destination_code]", area_code))

        payload = self._request("GET", "/available_phone_numbers", params=params)
        offers: list[dict[str, Any]] = []
        for item in payload.get("data", []):
            phone_number = item.get("phone_number")
            if not phone_number:
                continue
            line_type = self.lookup_line_type(phone_number)
            if non_voip_only and line_type == "voip":
                continue
            features_raw = item.get("features", [])
            if isinstance(features_raw, list):
                features = {str(x).lower() for x in features_raw if x is not None}
            elif isinstance(features_raw, dict):
                features = {str(k).lower() for k, v in features_raw.items() if v}
            else:
                features = set()
            offers.append(
                {
                    "phone_number": phone_number,
                    "provider_number_id": None,
                    "capabilities": {"sms": "sms" in features, "voice": "voice" in features},
                    "locality": item.get("locality"),
                    "region": item.get("administrative_area"),
                    "line_type": line_type,
                    "monthly_cost_estimate": 1.00,
                }
            )
        return offers

    def _resolve_phone_number_id(self, phone_number: str) -> str | None:
        for item in self.list_owned_numbers():
            if item.get("phone_number") == phone_number:
                return item.get("provider_number_id")
        return None

    @staticmethod
    def _extract_order_phone_number_id(order_payload: dict[str, Any], phone_number: str) -> str | None:
        data = order_payload.get("data", {}) if isinstance(order_payload, dict) else {}
        phone_rows = data.get("phone_numbers", [])
        if not isinstance(phone_rows, list):
            return None
        for row in phone_rows:
            if not isinstance(row, dict):
                continue
            if row.get("phone_number") == phone_number and row.get("id"):
                return str(row["id"])
        return None

    def _assign_messaging_profile(self, phone_number_id: str) -> dict[str, Any]:
        if not self.messaging_profile_id:
            raise ProviderError(
                "TELNYX_MESSAGING_PROFILE_ID is not set. "
                "Telnyx SMS requires your number to be attached to a Messaging Profile."
            )
        return self._request(
            "PATCH",
            f"/phone_numbers/{phone_number_id}/messaging",
            json_payload={"messaging_profile_id": self.messaging_profile_id},
        )

    def _auto_sync_from_number_to_messaging_profile(
        self,
        from_number: str,
        *,
        strict: bool,
    ) -> dict[str, Any]:
        if not self.messaging_profile_id:
            message = (
                "TELNYX_MESSAGING_PROFILE_ID is not configured. "
                "Auto-sync to messaging profile is disabled."
            )
            if strict:
                raise ProviderError(message)
            return {"skipped": True, "warning": message}

        number_id = self._resolve_phone_number_id(from_number)
        if not number_id:
            message = (
                f"Could not resolve Telnyx phone number ID for {from_number}. "
                "Order/sync the number first so it can be auto-linked to messaging profile."
            )
            if strict:
                raise ProviderError(message)
            return {"skipped": True, "warning": message}

        try:
            assignment = self._assign_messaging_profile(number_id)
            return {"synced": True, "phone_number_id": number_id, "assignment": assignment}
        except ProviderError as exc:
            message = f"Auto-sync to Telnyx messaging profile failed: {exc}"
            if strict:
                raise ProviderError(message) from exc
            return {"skipped": True, "phone_number_id": number_id, "warning": message}

    def purchase_number(self, phone_number: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/number_orders",
            json_payload={"phone_numbers": [{"phone_number": phone_number}]},
        )
        # Prefer explicit number ID from order response, then fallback to listing owned numbers.
        number_id = self._extract_order_phone_number_id(payload, phone_number) or self._resolve_phone_number_id(
            phone_number
        )
        order = payload.get("data", {})
        warnings: list[str] = []
        messaging_assignment: dict[str, Any] | None = None
        voice_assignment: dict[str, Any] | None = None

        if self.messaging_profile_id:
            if number_id:
                try:
                    messaging_assignment = self._assign_messaging_profile(number_id)
                except ProviderError as exc:
                    warnings.append(f"Failed to attach number to messaging profile: {exc}")
            else:
                warnings.append(
                    "Could not resolve Telnyx phone number ID immediately after order; "
                    "auto-attach to messaging profile skipped. Attach manually in Telnyx console if SMS fails."
                )
        else:
            warnings.append(
                "TELNYX_MESSAGING_PROFILE_ID is not configured. "
                "SMS may fail with 40305 until the number is linked to a messaging profile."
            )

        # Assign to SIP Connection (for WebRTC + webhooks) or Voice API App
        assign_conn = self.sip_connection_id or self.connection_id
        if assign_conn and number_id:
            try:
                voice_assignment = self._request(
                    "PATCH",
                    f"/phone_numbers/{number_id}/voice",
                    json_payload={"connection_id": assign_conn},
                )
            except ProviderError:
                try:
                    voice_assignment = self._request(
                        "PATCH",
                        f"/phone_numbers/{number_id}",
                        json_payload={"connection_id": assign_conn},
                    )
                except ProviderError as exc:
                    warnings.append(f"Failed to assign number to connection: {exc}")
        elif not self.connection_id:
            warnings.append(
                "TELNYX_CONNECTION_ID is not configured. "
                "Inbound/outbound calls will not work until the number is linked to a connection."
            )

        return {
            "phone_number": phone_number,
            "provider_number_id": number_id or order.get("id"),
            "line_type": self.lookup_line_type(phone_number),
            "raw": {
                "order": payload,
                "messaging_assignment": messaging_assignment,
                "voice_assignment": voice_assignment,
            },
            "warnings": warnings,
        }

    def list_owned_numbers(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/phone_numbers", params={"page[size]": 200})
        numbers: list[dict[str, Any]] = []
        for item in payload.get("data", []):
            numbers.append(
                {
                    "provider_number_id": item.get("id"),
                    "phone_number": item.get("phone_number"),
                    "status": item.get("status", "active"),
                }
            )
        return numbers

    def release_number(self, provider_number_id: str) -> dict[str, Any]:
        self._request("DELETE", f"/phone_numbers/{provider_number_id}")
        return {"released": True, "provider_number_id": provider_number_id}

    def send_message(self, from_number: str, to_number: str, body: str) -> dict[str, Any]:
        profile_sync = self._auto_sync_from_number_to_messaging_profile(from_number, strict=True)
        try:
            payload = self._request(
                "POST",
                "/messages",
                json_payload={"from": from_number, "to": to_number, "text": body},
            )
        except ProviderError as exc:
            error_text = str(exc)
            if "40305" in error_text or "Invalid 'from' address" in error_text:
                raise ProviderError(
                    f"{error_text} "
                    "The app already attempted to auto-sync this number to TELNYX_MESSAGING_PROFILE_ID. "
                    "Confirm the number is approved inside that messaging profile and retry."
                ) from exc
            raise
        data = payload.get("data", {})
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "raw": payload,
            "auto_profile_sync": profile_sync,
        }

    def start_call(self, from_number: str, to_number: str, say_text: str) -> dict[str, Any]:
        if not self.connection_id:
            raise ProviderError("TELNYX_CONNECTION_ID is required for outbound calls.")
        call_payload: dict[str, Any] = {
            "connection_id": self.connection_id,
            "from": from_number,
            "to": to_number,
        }
        if self.call_webhook_url:
            call_payload["webhook_url"] = self.call_webhook_url
        payload = self._request("POST", "/calls", json_payload=call_payload)
        data = payload.get("data", {})
        return {
            "id": data.get("call_control_id") or data.get("call_leg_id"),
            "status": data.get("state", "initiated"),
            "raw": payload,
        }

    def pricing_profile(self) -> dict[str, Any]:
        return {
            "number_monthly_usd": 1.0,
            "sms_outbound_usd": 0.004,
            "call_per_min_usd": 0.01,
        }

    def account_balance(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"balance": None, "currency": "USD", "source": "not_configured"}
        payload = self._request("GET", "/balance")
        data = payload.get("data", payload)
        try:
            amount = float(data.get("balance", "0"))
        except (TypeError, ValueError):
            amount = 0.0
        return {
            "balance": amount,
            "currency": data.get("currency", "USD"),
            "source": "telnyx",
            "pending": data.get("pending"),
            "available_credit": data.get("available_credit"),
        }


class SignalWireProvider(BaseProvider):
    provider_id = "signalwire"
    label = "SignalWire"

    def __init__(self) -> None:
        self.space_url = os.environ.get("SIGNALWIRE_SPACE_URL", "").strip()
        self.project_id = os.environ.get("SIGNALWIRE_PROJECT_ID", "").strip()
        self.api_token = os.environ.get("SIGNALWIRE_API_TOKEN", "").strip()

    def is_configured(self) -> bool:
        return bool(self.space_url and self.project_id and self.api_token)

    @property
    def base_url(self) -> str:
        return f"https://{self.space_url}/api/laml/2010-04-01"

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise ProviderError("SignalWire is not configured. Set SIGNALWIRE_SPACE_URL, SIGNALWIRE_PROJECT_ID, and SIGNALWIRE_API_TOKEN.")
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_payload,
                auth=(self.project_id, self.api_token),
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"SignalWire request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"SignalWire API error {response.status_code}: {response.text}")
        return response.json() if response.text else {}

    def _rest_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """REST API request (non-LAML endpoints)."""
        if not self.is_configured():
            raise ProviderError("SignalWire is not configured.")
        url = f"https://{self.space_url}/api/relay/rest{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_payload,
                auth=(self.project_id, self.api_token),
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"SignalWire request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"SignalWire API error {response.status_code}: {response.text}")
        return response.json() if response.text else {}

    def search_available_numbers(
        self,
        country: str,
        area_code: str | None,
        limit: int,
        require_sms: bool,
        require_voice: bool,
        non_voip_only: bool,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"PageSize": limit}
        if area_code:
            params["AreaCode"] = area_code
        if require_sms:
            params["SmsEnabled"] = "true"
        if require_voice:
            params["VoiceEnabled"] = "true"
        payload = self._request(
            "GET",
            f"/Accounts/{self.project_id}/AvailablePhoneNumbers/{country.upper()}/Local.json",
            params=params,
        )
        offers: list[dict[str, Any]] = []
        for item in payload.get("available_phone_numbers", []):
            capabilities = item.get("capabilities", {})
            offers.append({
                "phone_number": item.get("phone_number"),
                "provider_number_id": None,
                "capabilities": {
                    "sms": bool(capabilities.get("SMS") or capabilities.get("sms")),
                    "voice": bool(capabilities.get("voice") or capabilities.get("Voice")),
                },
                "locality": item.get("locality"),
                "region": item.get("region"),
                "line_type": "local",
                "monthly_cost_estimate": 0.50,
            })
        return offers

    def purchase_number(self, phone_number: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            f"/Accounts/{self.project_id}/IncomingPhoneNumbers.json",
            data={"PhoneNumber": phone_number},
        )
        return {
            "phone_number": payload.get("phone_number", phone_number),
            "provider_number_id": payload.get("sid"),
            "line_type": "local",
            "raw": payload,
        }

    def list_owned_numbers(self) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/Accounts/{self.project_id}/IncomingPhoneNumbers.json",
            params={"PageSize": 200},
        )
        numbers: list[dict[str, Any]] = []
        for item in payload.get("incoming_phone_numbers", []):
            numbers.append({
                "provider_number_id": item.get("sid"),
                "phone_number": item.get("phone_number"),
                "status": item.get("status", "active"),
            })
        return numbers

    def release_number(self, provider_number_id: str) -> dict[str, Any]:
        self._request(
            "DELETE",
            f"/Accounts/{self.project_id}/IncomingPhoneNumbers/{provider_number_id}.json",
        )
        return {"released": True, "provider_number_id": provider_number_id}

    def send_message(self, from_number: str, to_number: str, body: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            f"/Accounts/{self.project_id}/Messages.json",
            data={"From": from_number, "To": to_number, "Body": body},
        )
        return {"id": payload.get("sid"), "status": payload.get("status"), "raw": payload}

    def start_call(self, from_number: str, to_number: str, say_text: str) -> dict[str, Any]:
        twiml = f"<Response><Say>{say_text or 'Connected through 2nd Call.'}</Say></Response>"
        payload = self._request(
            "POST",
            f"/Accounts/{self.project_id}/Calls.json",
            data={"From": from_number, "To": to_number, "Twiml": twiml},
        )
        return {"id": payload.get("sid"), "status": payload.get("status"), "raw": payload}

    def pricing_profile(self) -> dict[str, Any]:
        return {
            "number_monthly_usd": 0.50,
            "sms_outbound_usd": 0.004,
            "call_per_min_usd": 0.01,
        }

    def account_balance(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"balance": None, "currency": "USD", "source": "not_configured"}
        try:
            payload = self._request("GET", f"/Accounts/{self.project_id}/Balance.json")
            amount = float(payload.get("balance", "0"))
            return {"balance": amount, "currency": payload.get("currency", "USD"), "source": "signalwire"}
        except Exception:
            return {"balance": None, "currency": "USD", "source": "signalwire"}


def build_providers() -> dict[str, BaseProvider]:
    providers: dict[str, BaseProvider] = {
        "telnyx": TelnyxProvider(),
        "signalwire": SignalWireProvider(),
    }
    return providers

