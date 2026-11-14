"""Solana Devnet reads and transaction verification.

Uses the documented JSON-RPC HTTP API (getHealth, getBalance, getTransaction).
No Anchor program is deployed. A signature is confirmed only after Devnet returns
the transaction and the vault balance increased.
"""

from __future__ import annotations

import re

import httpx

from app.config import get_settings

_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{64,128}$")


class SolanaError(RuntimeError):
    pass


def assert_devnet(url: str | None = None) -> str:
    rpc = (url or get_settings().solana_rpc_url).strip()
    if "devnet" not in rpc.lower():
        raise SolanaError("Refusing a Solana RPC URL that is not Devnet.")
    return rpc


async def rpc(method: str, params: list):
    url = assert_devnet()
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(url, json=payload)
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SolanaError(f"Devnet RPC request failed: {exc.__class__.__name__}") from exc
    if data.get("error"):
        message = data["error"].get("message", "RPC error") if isinstance(data["error"], dict) else "RPC error"
        raise SolanaError(str(message)[:200])
    return data.get("result")


async def health() -> str:
    result = await rpc("getHealth", [])
    return str(result)


async def get_balance_lamports(address: str) -> int:
    result = await rpc("getBalance", [address, {"commitment": "confirmed"}])
    if not isinstance(result, dict) or "value" not in result:
        raise SolanaError("Devnet getBalance response was missing a value.")
    return int(result["value"])


def _account_keys(message: dict) -> list[str]:
    keys = []
    for key in message.get("accountKeys") or []:
        if isinstance(key, str):
            keys.append(key)
        elif isinstance(key, dict) and key.get("pubkey"):
            keys.append(key["pubkey"])
    return keys


async def verify_vault_deposit(signature: str, vault_address: str) -> dict:
    if not _SIGNATURE.match(signature or ""):
        raise SolanaError("That is not a Solana transaction signature.")
    if not vault_address:
        raise SolanaError("No Devnet vault address is configured.")
    tx = await rpc(
        "getTransaction",
        [signature, {"encoding": "json", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}],
    )
    if not tx:
        raise SolanaError("Devnet has no confirmed transaction with that signature.")
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        raise SolanaError("The transaction is confirmed as failed on Devnet.")
    message = ((tx.get("transaction") or {}).get("message") or {})
    keys = _account_keys(message)
    if vault_address not in keys:
        raise SolanaError("The confirmed transaction does not include the vault address.")
    index = keys.index(vault_address)
    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []
    if index >= len(pre) or index >= len(post) or post[index] <= pre[index]:
        raise SolanaError("The vault balance did not increase in that transaction.")
    return {"lamports": int(post[index] - pre[index]), "slot": tx.get("slot")}
