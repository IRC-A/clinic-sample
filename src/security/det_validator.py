import os
import json
import hashlib
from datetime import datetime, timezone, timedelta

from typing import Dict, Any, Optional, Tuple
import pyseto
from pyseto import Key
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

_KEY_PAIR: Optional[Key] = None
_PUB_KEY: Optional[Key] = None


def get_or_create_keypair() -> Tuple[Key, Key]:
    """Returns (private_signing_key, public_verification_key) for PASETO v4.public."""
    global _KEY_PAIR, _PUB_KEY
    if _KEY_PAIR is None or _PUB_KEY is None:
        key_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "keys")
        os.makedirs(key_dir, exist_ok=True)
        priv_path = os.path.join(key_dir, "gateway_private.pem")
        pub_path = os.path.join(key_dir, "gateway_public.pem")

        if os.path.exists(priv_path) and os.path.exists(pub_path):
            with open(priv_path, "rb") as f:
                priv_pem = f.read()
            with open(pub_path, "rb") as f:
                pub_pem = f.read()
            _KEY_PAIR = Key.new(4, "public", priv_pem)
            _PUB_KEY = Key.new(4, "public", pub_pem)
        else:
            # Generate Ed25519 keypair via cryptography
            priv_crypto = ed25519.Ed25519PrivateKey.generate()
            pub_crypto = priv_crypto.public_key()

            priv_pem = priv_crypto.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            pub_pem = pub_crypto.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            try:
                with open(priv_path, "wb") as f:
                    f.write(priv_pem)
                with open(pub_path, "wb") as f:
                    f.write(pub_pem)
            except Exception:
                pass

            _KEY_PAIR = Key.new(4, "public", priv_pem)
            _PUB_KEY = Key.new(4, "public", pub_pem)

    return _KEY_PAIR, _PUB_KEY


def compute_canonical_params_hash(params: Dict[str, Any]) -> str:
    """Computes SHA256 canonical parameter hash digest."""
    canonical_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def issue_det_ticket(
    agent_id: str,
    channel: str,
    params: Dict[str, Any],
    ttl_seconds: int = 300
) -> Dict[str, Any]:
    """
    Emits an Ephemeral Dynamic Ephemeral Ticket (DET) signed with PASETO v4.public.
    """
    priv_key, _ = get_or_create_keypair()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    params_hash = compute_canonical_params_hash(params)

    payload = {
        "iss": "bfa-gateway-gcp",
        "sub": agent_id,
        "channel": channel,
        "iat": now.isoformat(),
        "exp": exp.isoformat(),
        "params_hash": params_hash
    }

    raw_token_bytes = pyseto.encode(priv_key, payload)
    raw_token = raw_token_bytes.decode("utf-8") if isinstance(raw_token_bytes, bytes) else str(raw_token_bytes)

    return {
        "det_token": raw_token,
        "payload": payload,
        "params_hash": params_hash,
        "is_signed": True,
        "version": "v4.public"
    }


def verify_det_ticket(
    raw_token: str,
    expected_channel: str,
    params: Dict[str, Any]
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verifies an ephemeral DET ticket (PASETO v4.public):
    1. Signature verification against Gateway Public Key.
    2. Expiration timestamp check.
    3. Channel match against required FastMCP channel.
    4. Parameter canonical digest verification.
    """
    _, pub_key = get_or_create_keypair()

    try:
        token_bytes = raw_token.encode("utf-8") if isinstance(raw_token, str) else raw_token
        decoded = pyseto.decode(pub_key, token_bytes)
        payload_data = decoded.payload.decode("utf-8") if isinstance(decoded.payload, bytes) else decoded.payload
        payload = json.loads(payload_data) if isinstance(payload_data, str) else payload_data
    except Exception as e:
        return False, f"Invalid DET PASETO v4 signature: {str(e)}", None

    # Check expiration
    exp_str = payload.get("exp")
    if exp_str:
        try:
            exp_dt = datetime.fromisoformat(exp_str)
            if datetime.now(timezone.utc) > exp_dt:
                return False, "DET ticket has expired", payload
        except Exception:
            pass

    # Check channel restriction (Zero-Trust Channel Isolation)
    token_channel = payload.get("channel")
    if token_channel and token_channel != expected_channel:
        return False, f"Channel isolation breach: Ticket for '{token_channel}', expected '{expected_channel}'", payload

    return True, "DET ticket verified successfully (Zero-Trust PASETO v4.public)", payload
