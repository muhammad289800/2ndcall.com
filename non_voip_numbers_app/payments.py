"""Custom crypto payment system.

Accepts USDT payments on TRC20, ERC20, and BEP20 networks.
Scans blockchain APIs to automatically verify incoming transactions.

Required environment variables:
    CRYPTO_WALLET_TRC20 — your TRON wallet address for receiving TRC20 USDT

Optional:
    CRYPTO_WALLET_ERC20  — Ethereum wallet address for ERC20 USDT
    CRYPTO_WALLET_BEP20  — BSC wallet address for BEP20 USDT
    TRONGRID_API_KEY     — TronGrid API key (optional, increases rate limits)
"""

import os
import time
from typing import Any

import requests

# Wallet addresses
WALLET_TRC20 = os.environ.get("CRYPTO_WALLET_TRC20", "").strip()
WALLET_ERC20 = os.environ.get("CRYPTO_WALLET_ERC20", "").strip()
WALLET_BEP20 = os.environ.get("CRYPTO_WALLET_BEP20", "").strip()
TRONGRID_API_KEY = os.environ.get("TRONGRID_API_KEY", "").strip()

# USDT contract addresses
USDT_CONTRACTS = {
    "TRC20": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
    "ERC20": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "BEP20": "0x55d398326f99059fF775485246999027B3197955",
}


def is_configured() -> bool:
    return bool(WALLET_TRC20 or WALLET_ERC20 or WALLET_BEP20)


def get_supported_networks() -> list[dict[str, str]]:
    networks = []
    if WALLET_TRC20:
        networks.append({"id": "TRC20", "name": "TRON (TRC20)", "address": WALLET_TRC20, "token": "USDT", "fee_est": "~$1"})
    if WALLET_ERC20:
        networks.append({"id": "ERC20", "name": "Ethereum (ERC20)", "address": WALLET_ERC20, "token": "USDT", "fee_est": "~$5-15"})
    if WALLET_BEP20:
        networks.append({"id": "BEP20", "name": "BSC (BEP20)", "address": WALLET_BEP20, "token": "USDT", "fee_est": "~$0.10"})
    return networks


def get_wallet_address(network: str) -> str | None:
    return {"TRC20": WALLET_TRC20, "ERC20": WALLET_ERC20, "BEP20": WALLET_BEP20}.get(network.upper())


def scan_trc20_transactions(
    address: str,
    min_timestamp_ms: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch recent TRC20 USDT transfers TO this address from TronGrid."""
    url = f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"
    headers = {"Accept": "application/json"}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    params: dict[str, Any] = {
        "only_to": "true",
        "limit": limit,
        "contract_address": USDT_CONTRACTS["TRC20"],
        "order_by": "block_timestamp,desc",
    }
    if min_timestamp_ms > 0:
        params["min_timestamp"] = min_timestamp_ms

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for tx in data.get("data", []):
            value_raw = tx.get("value", "0")
            # USDT has 6 decimals on TRC20
            try:
                amount = int(value_raw) / 1_000_000
            except (ValueError, TypeError):
                amount = 0.0
            results.append({
                "tx_hash": tx.get("transaction_id", ""),
                "from_address": tx.get("from", ""),
                "to_address": tx.get("to", ""),
                "amount": amount,
                "token": tx.get("token_info", {}).get("symbol", "USDT"),
                "timestamp_ms": tx.get("block_timestamp", 0),
                "network": "TRC20",
            })
        return results
    except requests.RequestException:
        return []


def verify_trc20_tx(tx_hash: str) -> dict[str, Any] | None:
    """Look up a specific TRC20 transaction by hash."""
    url = f"https://api.trongrid.io/v1/transactions/{tx_hash}/events"
    headers = {"Accept": "application/json"}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("success"):
            return None

        for event in data.get("data", []):
            if event.get("event_name") != "Transfer":
                continue
            result = event.get("result", {})
            contract = event.get("contract_address", "")
            # Check if this is a USDT transfer
            if contract.lower() in (USDT_CONTRACTS["TRC20"].lower(), "41" + USDT_CONTRACTS["TRC20"][1:].lower()):
                value = int(result.get("value", "0"))
                amount = value / 1_000_000
                to_addr = result.get("to", "")
                from_addr = result.get("from", "")
                # Convert hex addresses to base58 if needed
                return {
                    "tx_hash": tx_hash,
                    "from_address": from_addr,
                    "to_address": to_addr,
                    "amount": amount,
                    "token": "USDT",
                    "network": "TRC20",
                    "confirmed": True,
                    "timestamp_ms": event.get("block_timestamp", 0),
                }
        # Fallback: check transaction info directly
        info_url = f"https://api.trongrid.io/wallet/gettransactionbyid"
        resp2 = requests.post(info_url, json={"value": tx_hash}, headers=headers, timeout=15)
        if resp2.status_code == 200:
            tx_data = resp2.json()
            if tx_data.get("txID"):
                return {
                    "tx_hash": tx_hash,
                    "from_address": "",
                    "to_address": "",
                    "amount": 0,
                    "token": "USDT",
                    "network": "TRC20",
                    "confirmed": True,
                    "timestamp_ms": tx_data.get("raw_data", {}).get("timestamp", 0),
                    "raw": tx_data,
                }
        return None
    except requests.RequestException:
        return None


def match_payment_to_orders(
    transactions: list[dict[str, Any]],
    pending_orders: list[dict[str, Any]],
    wallet_address: str,
    tolerance: float = 0.01,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Match incoming transactions to pending payment orders by amount.

    Returns list of (transaction, order) pairs that match.
    """
    matched = []
    used_order_ids: set[str] = set()
    used_tx_hashes: set[str] = set()

    for tx in transactions:
        if tx["tx_hash"] in used_tx_hashes:
            continue
        tx_amount = tx.get("amount", 0)
        if tx_amount <= 0:
            continue

        for order in pending_orders:
            if order["order_id"] in used_order_ids:
                continue
            if order.get("status") != "pending":
                continue

            order_amount = float(order.get("amount_usd", 0))
            # Check for tx_hash match first (user submitted hash)
            if order.get("submitted_tx_hash") and order["submitted_tx_hash"] == tx["tx_hash"]:
                matched.append((tx, order))
                used_order_ids.add(order["order_id"])
                used_tx_hashes.add(tx["tx_hash"])
                break

            # Amount match within tolerance
            if abs(tx_amount - order_amount) <= tolerance:
                # Check order was created before the transaction
                order_created_ms = _iso_to_ms(order.get("created_at", ""))
                tx_ts = tx.get("timestamp_ms", 0)
                if order_created_ms > 0 and tx_ts > 0 and tx_ts < order_created_ms - 60000:
                    continue  # Transaction is older than the order
                matched.append((tx, order))
                used_order_ids.add(order["order_id"])
                used_tx_hashes.add(tx["tx_hash"])
                break

    return matched


def _iso_to_ms(iso_str: str) -> int:
    if not iso_str:
        return 0
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso_str)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0
