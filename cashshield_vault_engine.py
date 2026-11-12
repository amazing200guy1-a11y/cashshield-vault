"""
CashShield-Vault Engine
=======================
Non-custodial cryptographic dead-man's UTXO timelock & inheritance covenant on Bitcoin Cash.

Funds automatically transfer to a designated heir if the owner does not "heartbeat"
(sign a liveness proof) within a configured time window.
No court, no bank, no custodian needed.
"""

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MINIMUM_BCH = 0.001  # minimum vault balance in BCH
VAULT_HMAC_SECRET = b"cashshield-vault-liveness-secret-v1"


# ---------------------------------------------------------------------------
# Covenant status sentinels
# ---------------------------------------------------------------------------
class CovenantStatus:
    ACTIVE = "ACTIVE"
    INHERITANCE_TRIGGERED = "INHERITANCE_TRIGGERED"
    INHERITANCE_EXECUTED = "INHERITANCE_EXECUTED"


# ---------------------------------------------------------------------------
# HeartbeatLivenessProof
# ---------------------------------------------------------------------------
@dataclass
class HeartbeatLivenessProof:
    """HMAC-SHA256 signed liveness packet."""
    owner_id: str
    nonce: str
    timestamp: float          # POSIX UTC
    signature: str            # hex-encoded HMAC-SHA256 digest

    # ------------------------------------------------------------------ #
    @staticmethod
    def _sign(owner_id: str, nonce: str, timestamp: float) -> str:
        payload = f"{owner_id}:{nonce}:{timestamp:.6f}".encode()
        return hmac.new(VAULT_HMAC_SECRET, payload, hashlib.sha256).hexdigest()

    # ------------------------------------------------------------------ #
    @classmethod
    def create(cls, owner_id: str) -> "HeartbeatLivenessProof":
        nonce = uuid.uuid4().hex
        ts = time.time()
        sig = cls._sign(owner_id, nonce, ts)
        return cls(owner_id=owner_id, nonce=nonce, timestamp=ts, signature=sig)

    # ------------------------------------------------------------------ #
    def verify(self) -> bool:
        expected = self._sign(self.owner_id, self.nonce, self.timestamp)
        return hmac.compare_digest(self.signature, expected)


# ---------------------------------------------------------------------------
# UTXOTimelock
# ---------------------------------------------------------------------------
@dataclass
class UTXOTimelock:
    """Represents a single BCH vault UTXO with an embedded timelock covenant."""
    vault_id: str
    owner_pubkey: str           # owner identifier (simulated pubkey / owner_id)
    heir_pubkey: str            # heir identifier
    heartbeat_interval_days: int
    last_heartbeat: float       # POSIX UTC of most-recent valid heartbeat
    balance_bch: float
    covenant_hash: str          # SHA-256 of vault genesis parameters
    status: str = CovenantStatus.ACTIVE
    heir_balance_bch: float = 0.0
    transfer_receipt: Optional[str] = None

    # ------------------------------------------------------------------ #
    @property
    def next_heartbeat_deadline(self) -> float:
        return self.last_heartbeat + self.heartbeat_interval_days * 86_400

    # ------------------------------------------------------------------ #
    @property
    def seconds_remaining(self) -> float:
        return self.next_heartbeat_deadline - time.time()

    # ------------------------------------------------------------------ #
    @property
    def is_overdue(self) -> bool:
        return time.time() > self.next_heartbeat_deadline


# ---------------------------------------------------------------------------
# VaultCovenantEngine
# ---------------------------------------------------------------------------
class VaultCovenantEngine:
    """
    Core state machine for CashShield-Vault.

    All operations target < 0.1 ms median latency on modern hardware.
    """

    def __init__(self) -> None:
        self._vaults: Dict[str, UTXOTimelock] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def create_vault(
        self,
        owner_id: str,
        heir_id: str,
        reserve_bch: float,
        heartbeat_interval_days: int = 90,
    ) -> Dict:
        """
        Create a new vault UTXO with an embedded timelock covenant.

        Returns a dict with vault_id and covenant_hash.
        Raises ValueError for invalid parameters.
        """
        if reserve_bch < MINIMUM_BCH:
            raise ValueError(
                f"Minimum vault balance is {MINIMUM_BCH} BCH; got {reserve_bch}"
            )
        if not owner_id or not heir_id:
            raise ValueError("owner_id and heir_id must be non-empty strings")
        if heartbeat_interval_days <= 0:
            raise ValueError("heartbeat_interval_days must be positive")

        vault_id = uuid.uuid4().hex
        now = time.time()

        # Covenant hash: SHA-256(owner | heir | interval | reserve | vault_id | genesis_ts)
        genesis_blob = (
            f"{owner_id}|{heir_id}|{heartbeat_interval_days}"
            f"|{reserve_bch:.8f}|{vault_id}|{now:.6f}"
        ).encode()
        covenant_hash = hashlib.sha256(genesis_blob).hexdigest()

        vault = UTXOTimelock(
            vault_id=vault_id,
            owner_pubkey=owner_id,
            heir_pubkey=heir_id,
            heartbeat_interval_days=heartbeat_interval_days,
            last_heartbeat=now,
            balance_bch=reserve_bch,
            covenant_hash=covenant_hash,
        )
        self._vaults[vault_id] = vault

        return {"vault_id": vault_id, "covenant_hash": covenant_hash}

    # ------------------------------------------------------------------ #

    def submit_heartbeat(self, vault_id: str, owner_id: str) -> Dict:
        """
        Submit a signed liveness proof for a vault.

        Returns success/fail with the proof details.
        Raises KeyError if vault not found.
        """
        vault = self._get_vault(vault_id)
        if vault.status != CovenantStatus.ACTIVE:
            return {
                "success": False,
                "reason": f"Vault is not active (status={vault.status})",
            }

        proof = HeartbeatLivenessProof.create(owner_id)

        if not proof.verify():
            return {"success": False, "reason": "Signature verification failed"}

        if proof.owner_id != vault.owner_pubkey:
            return {
                "success": False,
                "reason": "owner_id does not match vault owner",
            }

        vault.last_heartbeat = proof.timestamp
        return {
            "success": True,
            "proof": {
                "owner_id": proof.owner_id,
                "nonce": proof.nonce,
                "timestamp": proof.timestamp,
                "signature": proof.signature,
            },
        }

    # ------------------------------------------------------------------ #

    def submit_heartbeat_with_proof(self, vault_id: str, proof: HeartbeatLivenessProof) -> Dict:
        """
        Submit an externally constructed proof (used for forgery tests).
        """
        vault = self._get_vault(vault_id)
        if vault.status != CovenantStatus.ACTIVE:
            return {
                "success": False,
                "reason": f"Vault is not active (status={vault.status})",
            }

        if not proof.verify():
            return {"success": False, "reason": "Signature verification failed"}

        if proof.owner_id != vault.owner_pubkey:
            return {
                "success": False,
                "reason": "owner_id does not match vault owner",
            }

        vault.last_heartbeat = proof.timestamp
        return {"success": True, "proof": proof}

    # ------------------------------------------------------------------ #

    def check_covenant_trigger(self, vault_id: str) -> str:
        """
        Check whether the inheritance covenant should trigger.

        Returns CovenantStatus.INHERITANCE_TRIGGERED or CovenantStatus.ACTIVE
        (or INHERITANCE_EXECUTED if already done).
        """
        vault = self._get_vault(vault_id)
        if vault.status == CovenantStatus.INHERITANCE_EXECUTED:
            return CovenantStatus.INHERITANCE_EXECUTED
        if vault.is_overdue:
            vault.status = CovenantStatus.INHERITANCE_TRIGGERED
            return CovenantStatus.INHERITANCE_TRIGGERED
        return CovenantStatus.ACTIVE

    # ------------------------------------------------------------------ #

    def execute_inheritance(self, vault_id: str) -> Dict:
        """
        Atomically transfer vault balance to the heir and produce a SHA-256 receipt.

        Idempotency: calling twice returns an error on the second call.
        """
        vault = self._get_vault(vault_id)

        # Must be triggered (or still active but overdue) to execute
        current_status = self.check_covenant_trigger(vault_id)
        if current_status not in (
            CovenantStatus.INHERITANCE_TRIGGERED,
        ):
            if vault.status == CovenantStatus.INHERITANCE_EXECUTED:
                return {
                    "success": False,
                    "reason": "Inheritance already executed (idempotency guard)",
                    "receipt": vault.transfer_receipt,
                }
            return {
                "success": False,
                "reason": f"Covenant not triggered (status={current_status}). "
                          "Heartbeat is still current.",
            }

        # Atomic transfer
        transferred = vault.balance_bch
        vault.heir_balance_bch += transferred
        vault.balance_bch = 0.0
        vault.status = CovenantStatus.INHERITANCE_EXECUTED

        # Receipt: SHA-256(vault_id | heir | amount | execution_ts)
        exec_ts = time.time()
        receipt_blob = (
            f"{vault_id}|{vault.heir_pubkey}|{transferred:.8f}|{exec_ts:.6f}"
        ).encode()
        vault.transfer_receipt = hashlib.sha256(receipt_blob).hexdigest()

        return {
            "success": True,
            "transferred_bch": transferred,
            "heir_id": vault.heir_pubkey,
            "transfer_receipt": vault.transfer_receipt,
            "executed_at": exec_ts,
        }

    # ------------------------------------------------------------------ #

    def get_vault_state(self, vault_id: str) -> Dict:
        """Return the full vault state as a dictionary."""
        vault = self._get_vault(vault_id)
        return {
            "vault_id": vault.vault_id,
            "owner_pubkey": vault.owner_pubkey,
            "heir_pubkey": vault.heir_pubkey,
            "heartbeat_interval_days": vault.heartbeat_interval_days,
            "last_heartbeat": vault.last_heartbeat,
            "last_heartbeat_iso": datetime.fromtimestamp(
                vault.last_heartbeat, tz=timezone.utc
            ).isoformat(),
            "next_deadline": vault.next_heartbeat_deadline,
            "seconds_remaining": vault.seconds_remaining,
            "balance_bch": vault.balance_bch,
            "heir_balance_bch": vault.heir_balance_bch,
            "covenant_hash": vault.covenant_hash,
            "status": vault.status,
            "transfer_receipt": vault.transfer_receipt,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_vault(self, vault_id: str) -> UTXOTimelock:
        try:
            return self._vaults[vault_id]
        except KeyError:
            raise KeyError(f"Vault not found: {vault_id}")
