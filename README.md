# BankShield

BankShield is an adversarial stress-testing environment for bank transaction monitoring systems. It measures where rule-based and supervised compliance systems fail when tested against multi-step evasion techniques.

The repository accompanies the technical brief submitted for the engineering assessment.

## Repository contents

- `engine.py`: A deterministic Python engine implementing Bank Secrecy Act and anti-money laundering rule checks alongside a double-entry balance ledger.
- `adversary.py`: An exploratory red-team agent that generates synthetic transaction sequences and mutates them in response to rule engine feedback until it finds an unflagged route.
- `auditor.py`: A blue-team compliance auditor that maps confirmed gaps to FinCEN and FATF guidelines, generating structured remediation proposals for human review.
- `test_scenarios.py`: A test suite running ten concrete scenarios (benign transactions, standard triggers, ledger invariant checks, and three multi-step evasion tests).
- `report.tex`: The submission brief, formatted to four pages with citations and architecture diagrams.

## How to run the system

This project runs on standard Python 3.8+ with no required third-party dependencies.

### 1. Run the benchmark test suite (10 scenarios)
```bash
python test_scenarios.py
```

### 2. Run the adversarial red-team search loop
```bash
python adversary.py
```
*Note on LLM API keys:* To run `adversary.py` against a live language model, set your API key:
```bash
# Optional: Uses OpenRouter free models or OpenAI
export OPENROUTER_API_KEY="your-key-here"
# or
export OPENAI_API_KEY="your-key-here"
```
If no API key is provided, the script runs with a built-in adversarial mutation generator, demonstrating the exact feedback loop without external network dependencies.

### 3. Generate a compliance audit finding
```bash
python auditor.py
```

## How the architecture works

Bank compliance systems require deterministic, auditable decisions. BankShield separates probabilistic scenario generation from mathematical rule verification:

```
LLM Adversary Agent (adversary.py)
        │
        │ Proposed transaction plan (JSON)
        ▼
Double-Entry Ledger (engine.py)
        │ Balance invariant checks
        ▼
Bank Rule Engine (engine.py)
        ├── 31 CFR 1010.311 CTR threshold ($10,000)
        ├── Anti-structuring rolling window check (48 hours)
        ├── High-frequency velocity burst check
        └── Circular graph route detection
        │
        ▼
Evaluation Outcome
        ├── FLAGGED → Return feedback to adversary to mutate
        └── EVADED  → Send trace to Compliance Auditor (auditor.py)
```

1. **Adversarial generation**: Language model agents suggest transaction routes, timing intervals, and amount distributions.
2. **Double-entry ledger**: Verifies that transactions preserve basic accounting laws ($Assets = Liabilities + Equity$) and prevents accounts from spending balances they do not hold.
3. **Deterministic rule evaluation**: Runs hard-coded checks for Currency Transaction Report limits ($10,000 threshold), multi-transfer structuring heuristics, velocity bursts, and circular payments.
4. **Audit reporting**: Confirmed gaps are recorded in structured format with references to relevant statutory rules and regulatory advisories.

## The 10 test scenarios

The test suite in `test_scenarios.py` evaluates ten cases:

| Case ID | Scenario | Expected Behavior | Observed Result |
| :--- | :--- | :--- | :--- |
| CASE_01 | Routine personal expense ($124.50) | Not flagged | Cleared |
| CASE_02 | Large vendor payment ($15,000) | Flagged by CTR rule | Flagged (RULE_CTR_01) |
| CASE_03 | Structuring ($3,400 x 3 within 24h) | Flagged by structuring rule | Flagged (RULE_STRUC_03) |
| CASE_04 | Sanctioned destination wire | Flagged by jurisdiction rule | Flagged (RULE_SANCT_02) |
| CASE_05 | Outbound velocity burst (5 transfers in 20m) | Flagged by velocity rule | Flagged (RULE_VEL_04) |
| CASE_06 | Circular payment routing (A -> B -> C -> A) | Flagged by cycle detector | Flagged (RULE_CYCLE_05) |
| CASE_07 | Window boundary evasion (spaced across 52h) | Escapes 48-hour window | Evaded (Blind spot confirmed) |
| CASE_08 | Multi-beneficiary fan-out layering | Escapes single-pair check | Evaded (Blind spot confirmed) |
| CASE_09 | Sub-threshold micro-smurfing (14 x $800) | Escapes $2,000 minimum | Evaded (Blind spot confirmed) |
| CASE_10 | Transfer with insufficient balance | Rejected before rules run | Rejected by ledger invariant |

## Key findings and limitations

1. **Window rigidity**: Rules that look back across fixed periods (like 48 hours) are easily defeated by delaying subsequent transfers past the window cutoff.
2. **Topology blindness**: Pairwise transaction monitoring misses coordinated layering where funds pass through multiple intermediate accounts before consolidating.
3. **Threshold cliffs**: Fixed floor filters (such as only evaluating transfers over $2,000) leave a blind spot for automated micro-transfers that aggregate to large sums over several days.
