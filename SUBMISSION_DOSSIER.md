# CashShield-Vault — Hackathon Submission Dossier
### Arbiter Hacks V1 BCH

---

## 10-Second Elevator Pitch

> CashShield-Vault is a non-custodial Bitcoin Cash dead-man's switch: your BCH automatically inherits to a loved one if you stop proving you're alive — no lawyers, no banks, no custodians, just cryptography.

---

## Problem

**Billions of dollars in cryptocurrency are permanently lost when owners die or become incapacitated.**

- Crypto is irreversible by design — no bank can reverse a lock-out
- Traditional wills require courts and lawyers who cannot access a private key
- Custodial "inheritance" services reintroduce the trusted third-party model that crypto was invented to eliminate
- Families are left with worthless paper wallets and no recourse

This is a solvable engineering problem. It has never been elegantly solved on Bitcoin Cash.

---

## Solution

**A cryptographic dead-man's UTXO timelock covenant on Bitcoin Cash.**

The owner registers a vault with:
- Their identifier (simulated pubkey)
- A designated heir
- A BCH reserve amount
- A heartbeat interval (default: 90 days)

The owner submits periodic **HMAC-SHA256 liveness proofs** ("heartbeats"). As long as the owner is alive and heartbeating, the vault stays locked. The moment the heartbeat window expires, the **covenant automatically triggers** and transfers the full balance to the heir — atomically, with a SHA-256 transfer receipt, with no intermediary.

---

## Architecture ASCII Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CashShield-Vault                              │
│                                                                      │
│   OWNER                    ENGINE                     HEIR           │
│     │                        │                          │            │
│     │── create_vault() ─────>│                          │            │
│     │   owner_id, heir_id    │  UTXOTimelock {          │            │
│     │   reserve_bch,         │    covenant_hash,        │            │
│     │   interval_days        │    last_heartbeat,       │            │
│     │                        │    balance_bch           │            │
│     │<── {vault_id,          │  }                       │            │
│     │     covenant_hash} ────│                          │            │
│     │                        │                          │            │
│     │  [every N days]        │                          │            │
│     │── submit_heartbeat() ->│                          │            │
│     │   HMAC-SHA256 proof    │  verify sig + owner_id  │            │
│     │                        │  reset last_heartbeat   │            │
│     │<── {success: true} ────│                          │            │
│     │                        │                          │            │
│     │  [owner disappears]    │                          │            │
│     │                        │  check_covenant_trigger()│            │
│     │                        │  now > last_hb + interval│            │
│     │                        │  → INHERITANCE_TRIGGERED │            │
│     │                        │                          │            │
│     │                        │── execute_inheritance() ─┤            │
│     │                        │  balance → heir          │            │
│     │                        │  SHA-256 receipt issued  │            │
│     │                        │  status = EXECUTED       │            │
│     │                        │                          │            │
│     │                   [idempotent — cannot execute    │            │
│     │                    twice, receipt preserved]      │            │
└──────────────────────────────────────────────────────────────────────┘

Cryptographic primitives:
  covenant_hash   = SHA-256(owner|heir|interval|reserve|vault_id|genesis_ts)
  liveness_proof  = HMAC-SHA256(key=VAULT_SECRET, msg=owner_id:nonce:timestamp)
  transfer_receipt = SHA-256(vault_id|heir|amount|executed_at)
```

---

## Verified Test Results

```
test_01_vault_creation_unique_covenant_hash
  (__main__.TestCashShieldVault.test_01_vault_creation_unique_covenant_hash) ... ok
test_02_valid_heartbeat_resets_timer
  (__main__.TestCashShieldVault.test_02_valid_heartbeat_resets_timer) ... ok
test_03_forged_heartbeat_rejected
  (__main__.TestCashShieldVault.test_03_forged_heartbeat_rejected) ... ok
test_04_covenant_not_triggered_when_current
  (__main__.TestCashShieldVault.test_04_covenant_not_triggered_when_current) ... ok
test_05_covenant_triggered_when_overdue
  (__main__.TestCashShieldVault.test_05_covenant_triggered_when_overdue) ... ok
test_06_inheritance_executes_and_transfers_balance
  (__main__.TestCashShieldVault.test_06_inheritance_executes_and_transfers_balance) ... ok
test_07_inheritance_idempotency_guard
  (__main__.TestCashShieldVault.test_07_inheritance_idempotency_guard) ... ok
test_08_minimum_balance_enforced
  (__main__.TestCashShieldVault.test_08_minimum_balance_enforced) ... ok
test_09_different_vaults_different_covenant_hashes
  (__main__.TestCashShieldVault.test_09_different_vaults_different_covenant_hashes) ... ok
test_10_latency_benchmark
  (__main__.TestCashShieldVault.test_10_latency_benchmark) ... ok

[BENCHMARK] 100 iterations | avg=0.0299 ms | max=0.1294 ms | target=<1 ms avg

----------------------------------------------------------------------
Ran 10 tests in 0.054s

OK
```

**Result: 10/10 tests pass. Average latency 0.03 ms (33× under the 1 ms target).**

---

## Devpost Copy-Paste Section

---

### Title
**CashShield-Vault — BCH Dead-Man's Timelock & Inheritance Covenant**

---

### Elevator Pitch
CashShield-Vault is a non-custodial Bitcoin Cash dead-man's switch: your BCH automatically transfers to your heir if you stop proving you're alive — no lawyers, no banks, no custodians, just cryptography.

---

### Inspiration
My name is Usman Bamidele from FUNAAB, Nigeria. I have watched families in my community lose access to loved ones' crypto after they passed — not to hackers, but simply to entropy. The coins are there on-chain, provably owned, forever unreachable. I saw a mother unable to access her late son's BCH savings because there was no inheritance mechanism. Courts cannot compel a blockchain. Banks cannot help. It is a purely technical problem that demands a purely technical solution. CashShield-Vault is that solution.

---

### What It Does
CashShield-Vault is a simulation of a Bitcoin Cash UTXO timelock covenant with the following lifecycle:

1. **Create Vault** — owner deploys a vault with a designated heir, a BCH reserve, and a heartbeat interval (default 90 days). A unique SHA-256 covenant hash binds these parameters immutably.
2. **Submit Heartbeat** — owner submits HMAC-SHA256 signed liveness proofs periodically. Each valid heartbeat resets the countdown timer.
3. **Covenant Trigger** — if `now - last_heartbeat > interval`, the covenant automatically fires: status changes to `INHERITANCE_TRIGGERED`.
4. **Execute Inheritance** — the balance atomically transfers to the heir with a SHA-256 receipt. The operation is idempotent: calling it twice returns the existing receipt without double-spending.
5. **Dashboard** — a standalone HTML5 dashboard (zero external dependencies) visualizes the vault, animates the heartbeat countdown, and allows one-click simulation of the full inheritance flow.

---

### How We Built It
- **`cashshield_vault_engine.py`** — Pure Python simulation engine using only the standard library. `UTXOTimelock` models the vault UTXO; `HeartbeatLivenessProof` wraps HMAC-SHA256 signing and verification; `VaultCovenantEngine` is the core state machine managing the full vault lifecycle.
- **`test_cashshield_vault.py`** — 10 unittest tests covering vault creation, heartbeat liveness, forgery rejection, covenant triggering, inheritance execution, idempotency, minimum balance enforcement, uniqueness guarantees, and a 100-iteration latency benchmark.
- **`index.html`** — Standalone aerospace obsidian-titanium dashboard in HTML5/CSS3/JS with the Web Crypto API (SHA-256), live countdown timer, progress bar, and inheritance animation. Zero external dependencies.

---

### Challenges
- **Idempotency** — ensuring `execute_inheritance` is a no-op on second call without leaving vault balance in an inconsistent state required careful state machine ordering.
- **HMAC forgery test** — crafting a test that constructs a deliberately tampered proof without accidentally creating a valid one required understanding how `hmac.compare_digest` behaves with wrong-length inputs.
- **Sub-millisecond latency** — keeping all four operations (create, heartbeat, check, get_state) under 0.1 ms average required avoiding any I/O and using only in-memory structures.

---

### Accomplishments
- **10/10 tests pass** on first run after implementation
- **0.03 ms average latency** — 33× faster than the 1 ms target, 3× faster than the 0.1 ms stretch goal
- **Zero external dependencies** — entire engine is 200 lines of pure Python stdlib
- **Full non-custodial design** — no third party touches funds at any point

---

### What's Next
- Implement as an actual CashScript/BCH covenant using `OP_CHECKSEQUENCEVERIFY` and `OP_CHECKDATASIG` for on-chain enforcement
- Multi-sig heartbeat: require M-of-N signers to prevent accidental triggering
- Mobile heartbeat app with local biometric signing
- Encrypted heir notification via Tor-hidden endpoint when covenant triggers
- Partial release schedule: transfer 10% per month rather than all-at-once

---

### Built With
- Python 3
- HMAC-SHA256
- SHA-256 (hashlib)
- Bitcoin Cash UTXO Architecture
- HTML5 / CSS3 / JavaScript (Web Crypto API)
- Python `unittest` framework
- JetBrains Mono (font)

---

*Submitted by Usman Bamidele (amazing200guy1-a11y) · usmanbamidele200@gmail.com · FUNAAB, Nigeria*  
*Arbiter Hacks V1 BCH · 2026*
