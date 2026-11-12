"""
CashShield-Vault — Test Suite
==============================
Exactly 10 unittest tests covering vault lifecycle, security, and performance.
Run with:  python test_cashshield_vault.py
"""

import time
import unittest

from cashshield_vault_engine import (
    CovenantStatus,
    HeartbeatLivenessProof,
    VaultCovenantEngine,
)


class TestCashShieldVault(unittest.TestCase):

    def setUp(self):
        """Fresh engine instance for every test."""
        self.engine = VaultCovenantEngine()

    # ------------------------------------------------------------------ #
    # test_01: vault creation produces unique covenant_hash
    # ------------------------------------------------------------------ #
    def test_01_vault_creation_unique_covenant_hash(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.5
        )
        self.assertIn("vault_id", result)
        self.assertIn("covenant_hash", result)
        # covenant_hash is a valid 64-char hex SHA-256 digest
        ch = result["covenant_hash"]
        self.assertEqual(len(ch), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in ch))

    # ------------------------------------------------------------------ #
    # test_02: valid heartbeat resets the liveness timer
    # ------------------------------------------------------------------ #
    def test_02_valid_heartbeat_resets_timer(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=1.0
        )
        vault_id = result["vault_id"]

        # Record old timestamp, sleep a tiny bit, then heartbeat
        state_before = self.engine.get_vault_state(vault_id)
        old_hb = state_before["last_heartbeat"]

        time.sleep(0.05)  # 50 ms gap — measurable but fast
        hb_result = self.engine.submit_heartbeat(vault_id, "alice")
        self.assertTrue(hb_result["success"])

        state_after = self.engine.get_vault_state(vault_id)
        self.assertGreater(state_after["last_heartbeat"], old_hb)

    # ------------------------------------------------------------------ #
    # test_03: forge/tampered heartbeat is rejected
    # ------------------------------------------------------------------ #
    def test_03_forged_heartbeat_rejected(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.25
        )
        vault_id = result["vault_id"]

        # Create a valid proof then tamper with the signature
        proof = HeartbeatLivenessProof.create("alice")
        tampered = HeartbeatLivenessProof(
            owner_id=proof.owner_id,
            nonce=proof.nonce,
            timestamp=proof.timestamp,
            signature="deadbeef" * 8,  # 64 hex chars but wrong
        )
        hb_result = self.engine.submit_heartbeat_with_proof(vault_id, tampered)
        self.assertFalse(hb_result["success"])
        self.assertIn("Signature verification failed", hb_result["reason"])

    # ------------------------------------------------------------------ #
    # test_04: covenant NOT triggered when heartbeat is current
    # ------------------------------------------------------------------ #
    def test_04_covenant_not_triggered_when_current(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.1
        )
        vault_id = result["vault_id"]

        # Fresh vault — heartbeat was just set at creation
        status = self.engine.check_covenant_trigger(vault_id)
        self.assertEqual(status, CovenantStatus.ACTIVE)

    # ------------------------------------------------------------------ #
    # test_05: covenant IS triggered when heartbeat is overdue
    # ------------------------------------------------------------------ #
    def test_05_covenant_triggered_when_overdue(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.1
        )
        vault_id = result["vault_id"]

        # Simulate overdue by pushing last_heartbeat far into the past
        vault = self.engine._vaults[vault_id]
        vault.last_heartbeat = time.time() - (91 * 86_400)  # 91 days ago

        status = self.engine.check_covenant_trigger(vault_id)
        self.assertEqual(status, CovenantStatus.INHERITANCE_TRIGGERED)

    # ------------------------------------------------------------------ #
    # test_06: inheritance executes and transfers balance from owner to heir
    # ------------------------------------------------------------------ #
    def test_06_inheritance_executes_and_transfers_balance(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=2.0
        )
        vault_id = result["vault_id"]

        # Make overdue
        vault = self.engine._vaults[vault_id]
        vault.last_heartbeat = time.time() - (200 * 86_400)

        exec_result = self.engine.execute_inheritance(vault_id)
        self.assertTrue(exec_result["success"])
        self.assertAlmostEqual(exec_result["transferred_bch"], 2.0, places=8)
        self.assertEqual(exec_result["heir_id"], "bob")
        self.assertIsNotNone(exec_result["transfer_receipt"])

        state = self.engine.get_vault_state(vault_id)
        self.assertEqual(state["balance_bch"], 0.0)
        self.assertAlmostEqual(state["heir_balance_bch"], 2.0, places=8)
        self.assertEqual(state["status"], CovenantStatus.INHERITANCE_EXECUTED)

    # ------------------------------------------------------------------ #
    # test_07: inheritance cannot be executed twice (idempotency guard)
    # ------------------------------------------------------------------ #
    def test_07_inheritance_idempotency_guard(self):
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.5
        )
        vault_id = result["vault_id"]

        vault = self.engine._vaults[vault_id]
        vault.last_heartbeat = time.time() - (200 * 86_400)

        first = self.engine.execute_inheritance(vault_id)
        self.assertTrue(first["success"])

        second = self.engine.execute_inheritance(vault_id)
        self.assertFalse(second["success"])
        self.assertIn("idempotency guard", second["reason"])

    # ------------------------------------------------------------------ #
    # test_08: vault with 0 BCH balance cannot be created (min 0.001 BCH)
    # ------------------------------------------------------------------ #
    def test_08_minimum_balance_enforced(self):
        with self.assertRaises(ValueError) as ctx:
            self.engine.create_vault(
                owner_id="alice", heir_id="bob", reserve_bch=0.0
            )
        self.assertIn("Minimum vault balance", str(ctx.exception))

        # Also test below the minimum
        with self.assertRaises(ValueError):
            self.engine.create_vault(
                owner_id="alice", heir_id="bob", reserve_bch=0.0005
            )

        # Exactly at minimum should succeed
        result = self.engine.create_vault(
            owner_id="alice", heir_id="bob", reserve_bch=0.001
        )
        self.assertIn("vault_id", result)

    # ------------------------------------------------------------------ #
    # test_09: different vaults get different covenant_hash values
    # ------------------------------------------------------------------ #
    def test_09_different_vaults_different_covenant_hashes(self):
        r1 = self.engine.create_vault(owner_id="alice", heir_id="bob", reserve_bch=1.0)
        r2 = self.engine.create_vault(owner_id="alice", heir_id="bob", reserve_bch=1.0)
        r3 = self.engine.create_vault(owner_id="carol", heir_id="dave", reserve_bch=5.0)

        hashes = {r1["covenant_hash"], r2["covenant_hash"], r3["covenant_hash"]}
        self.assertEqual(len(hashes), 3, "All covenant hashes must be unique")

    # ------------------------------------------------------------------ #
    # test_10: 100-iteration latency benchmark, assert avg < 1 ms
    # ------------------------------------------------------------------ #
    def test_10_latency_benchmark(self):
        ITERATIONS = 100
        times = []

        for i in range(ITERATIONS):
            t0 = time.perf_counter()
            result = self.engine.create_vault(
                owner_id=f"owner_{i}", heir_id=f"heir_{i}", reserve_bch=0.01 * (i + 1)
            )
            vault_id = result["vault_id"]
            self.engine.submit_heartbeat(vault_id, f"owner_{i}")
            self.engine.check_covenant_trigger(vault_id)
            self.engine.get_vault_state(vault_id)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)  # ms

        avg_ms = sum(times) / len(times)
        max_ms = max(times)
        print(
            f"\n[BENCHMARK] {ITERATIONS} iterations | "
            f"avg={avg_ms:.4f} ms | max={max_ms:.4f} ms | "
            f"target=<1 ms avg"
        )
        self.assertLess(avg_ms, 1.0, f"Average latency {avg_ms:.4f} ms exceeds 1 ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)
