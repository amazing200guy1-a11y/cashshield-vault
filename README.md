# CashShield-Vault

[![Tests](https://img.shields.io/badge/Tests-10%2F10-00FF66?style=flat-square&logo=python&logoColor=white)](./test_cashshield_vault.py)
[![Latency](https://img.shields.io/badge/Latency-%3C0.1ms%20avg-00E5FF?style=flat-square)](./cashshield_vault_engine.py)
[![License](https://img.shields.io/badge/License-MIT-1C2538?style=flat-square)](./LICENSE)
[![Bitcoin Cash](https://img.shields.io/badge/Bitcoin%20Cash-BCH-0AC18E?style=flat-square&logo=bitcoin-cash)](https://bitcoincash.org)
[![Hackathon](https://img.shields.io/badge/Arbiter%20Hacks-V1%20BCH-FF3366?style=flat-square)](https://arbiter.gg)

> **Non-custodial cryptographic dead-man's UTXO timelock & inheritance covenant on Bitcoin Cash.**  
> Funds automatically transfer to a designated heir if the owner does not "heartbeat" (sign a liveness proof) within a configured time window. No court, no bank, no custodian needed.

---

## The Problem

Billions of dollars in cryptocurrency are permanently stranded every year when owners die or become incapacitated without leaving access instructions. Existing solutions require custodians, legal systems, or trusting a third party — all of which contradict the self-sovereign promise of Bitcoin Cash.

## The Solution

CashShield-Vault implements a **cryptographic dead-man's switch** using:

- **UTXO Timelock Covenant** — a vault contract embedding a heartbeat deadline directly into the coin's spending conditions
- **HMAC-SHA256 Liveness Proofs** — the owner signs periodic "I'm alive" packets; any third party can verify without learning the private key
- **Automatic Inheritance Execution** — if the heartbeat window expires, the covenant atomically transfers the full balance to the pre-registered heir

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/amazing200guy1-a11y/cashshield-vault.git
cd cashshield-vault

# Run the full test suite (Python 3.8+, no extra dependencies)
python test_cashshield_vault.py

# Open the dashboard
# Just open index.html in any modern browser
```

Expected output:
```
test_01_vault_creation_unique_covenant_hash ... ok
test_02_valid_heartbeat_resets_timer ... ok
...
[BENCHMARK] 100 iterations | avg=0.0386 ms | max=0.1598 ms | target=<1 ms avg
----------------------------------------------------------------------
Ran 10 tests in 0.057s
OK
```

---

## Repository Structure

```
cashshield-vault/
├── cashshield_vault_engine.py   # Core simulation engine (pure Python, stdlib only)
├── test_cashshield_vault.py     # 10-test unittest suite with latency benchmark
├── index.html                   # Standalone aerospace-theme dashboard (no deps)
├── README.md                    # This file
└── SUBMISSION_DOSSIER.md        # Full hackathon submission dossier
```

---

## Architecture

```
Owner                    CashShield-Vault Engine              Heir
  │                              │                              │
  │── create_vault() ───────────>│  UTXOTimelock + covenant_hash│
  │                              │  stored in UTXO set          │
  │── submit_heartbeat() ───────>│  HMAC-SHA256 liveness proof  │
  │   (every < 90 days)         │  resets countdown timer      │
  │                              │                              │
  │  [owner stops heartbeating]  │                              │
  │                              │── check_covenant_trigger() ─>│
  │                              │   "INHERITANCE_TRIGGERED"    │
  │                              │── execute_inheritance() ────>│
  │                              │   SHA-256 transfer receipt   │
```

---

## Key Properties

| Property | Detail |
|---|---|
| Custodian | None — fully non-custodial |
| Cryptography | HMAC-SHA256 liveness proofs, SHA-256 covenant & receipt hashes |
| Minimum vault | 0.001 BCH |
| Default heartbeat window | 90 days (configurable) |
| Engine latency | < 0.1 ms avg per operation |
| Dependencies | Python 3.8+ stdlib only |

---

## License

MIT License — see [LICENSE](./LICENSE) for details.

Built with ❤️ for **Arbiter Hacks V1 BCH** by Usman Bamidele (amazing200guy1-a11y).
