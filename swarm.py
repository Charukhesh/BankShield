"""
BankShield Concurrent Multi-Agent Swarm Stress Testing (swarm.py).

This module coordinates multiple specialized agents acting concurrently against
the deterministic banking engine and shared double-entry ledger:

1. Agent Chronos (Temporal Boundary Pacer): Staggers transactions beyond 48h.
2. Agent Hydra (Multi-Hop Mule Ring): Fans out funds across intermediary accounts.
3. Agent Phantom (Micro-Jitter Smurfer): Uses sub-threshold randomized amounts.
4. Agent MarketNoise (Benign Traffic Generator): Emits legitimate payroll and retail noise.

All agents run concurrently via ThreadPoolExecutor. The shared environment uses a
threading lock to ensure thread-safe balance transitions and double-entry invariants.
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from adversary import call_gemini, load_env_file
from engine import Account, BankRuleEngine, DoubleEntryLedger, RuleViolation, Transaction

load_env_file()


class ThreadSafeBankEnvironment:
    """Thread-safe wrapper around DoubleEntryLedger and BankRuleEngine."""

    def __init__(self):
        self.lock = threading.Lock()
        self.ledger = DoubleEntryLedger()
        self.engine = BankRuleEngine(self.ledger)
        self.execution_log: List[Dict[str, Any]] = []

    def setup_default_accounts(self):
        with self.lock:
            base_time = datetime(2026, 11, 1, 9, 0, 0)
            self.ledger.add_account(Account("ACC_ALICE", "Alice Corp (Payroll)", 100000.0, base_time))
            self.ledger.add_account(Account("ACC_BOB", "Bob Logistics", 80000.0, base_time))
            self.ledger.add_account(Account("ACC_CHARLIE", "Charlie Holdings", 60000.0, base_time))
            self.ledger.add_account(Account("ACC_DAVE", "Dave Capital", 40000.0, base_time))
            self.ledger.add_account(Account("ACC_MULE_1", "Intermediary Mule 1", 10000.0, base_time))
            self.ledger.add_account(Account("ACC_MULE_2", "Intermediary Mule 2", 10000.0, base_time))
            self.ledger.add_account(Account("ACC_RETAIL", "Retail Merchant POS", 50000.0, base_time))

    def submit_transaction(self, agent_name: str, tx: Transaction) -> Tuple[bool, List[RuleViolation], Optional[str]]:
        with self.lock:
            # 1. Check & execute ledger balance updates
            success, err = self.ledger.process_transaction(tx)
            if not success:
                self.execution_log.append({
                    "agent": agent_name,
                    "tx_id": tx.tx_id,
                    "status": "REJECTED_BY_LEDGER",
                    "error": err,
                    "timestamp": tx.timestamp.isoformat(),
                    "amount": tx.amount,
                })
                return False, [], err

            # 2. Evaluate compliance rules
            violations = self.engine.evaluate(tx)
            status = "FLAGGED" if violations else "CLEARED"

            self.execution_log.append({
                "agent": agent_name,
                "tx_id": tx.tx_id,
                "sender": tx.sender_id,
                "receiver": tx.receiver_id,
                "amount": tx.amount,
                "timestamp": tx.timestamp.isoformat(),
                "status": status,
                "violations": [v.rule_id for v in violations],
            })
            return True, violations, None

    def verify_conservation_invariant(self) -> Tuple[bool, float]:
        with self.lock:
            total_balance = sum(acc.balance for acc in self.ledger.accounts.values())
            # Initial total: 100k + 80k + 60k + 40k + 10k + 10k + 50k = 350,000.0
            is_conserved = abs(total_balance - 350000.0) < 1e-5
            return is_conserved, total_balance


# ---------------------------------------------------------------------------
# Specialized Agent Prompts & Personas
# ---------------------------------------------------------------------------

AGENT_PERSONAS = {
    "Chronos_TemporalPacer": {
        "role": "Temporal Boundary Pacing Adversary",
        "objective": "Move $16,000 from ACC_CHARLIE to ACC_DAVE by staggering payments beyond the 48h aggregation window.",
        "fallback_plan": [
            {"tx_id": "CHRONOS_1", "sender": "ACC_CHARLIE", "receiver": "ACC_DAVE", "amount": 8000.0, "delay_hours": 0.0, "memo": "Consulting Fee 1"},
            {"tx_id": "CHRONOS_2", "sender": "ACC_CHARLIE", "receiver": "ACC_DAVE", "amount": 8000.0, "delay_hours": 50.0, "memo": "Consulting Fee 2"},
        ]
    },
    "Hydra_MuleCoordinator": {
        "role": "Multi-Hop Mule Ring Coordinator",
        "objective": "Fan out $18,000 from ACC_CHARLIE across ACC_MULE_1 and ACC_MULE_2, then forward to ACC_DAVE to bypass single-pair rules.",
        "fallback_plan": [
            {"tx_id": "HYDRA_1", "sender": "ACC_CHARLIE", "receiver": "ACC_MULE_1", "amount": 9000.0, "delay_hours": 2.0, "memo": "Subcontract Part A"},
            {"tx_id": "HYDRA_2", "sender": "ACC_CHARLIE", "receiver": "ACC_MULE_2", "amount": 9000.0, "delay_hours": 4.0, "memo": "Subcontract Part B"},
            {"tx_id": "HYDRA_3", "sender": "ACC_MULE_1", "receiver": "ACC_DAVE", "amount": 8900.0, "delay_hours": 51.0, "memo": "Disbursement A"},
            {"tx_id": "HYDRA_4", "sender": "ACC_MULE_2", "receiver": "ACC_DAVE", "amount": 8900.0, "delay_hours": 53.0, "memo": "Disbursement B"},
        ]
    },
    "Phantom_MicroSmurfer": {
        "role": "Sub-Threshold Jitter Smurfer",
        "objective": "Disburse $12,000 from ACC_BOB to ACC_CHARLIE using micro-transactions between $1,800 and $2,400 spaced 2.2h apart.",
        "fallback_plan": [
            {"tx_id": "PHANTOM_1", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1950.0, "delay_hours": 1.0, "memo": "Licensing Tranche 1"},
            {"tx_id": "PHANTOM_2", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1980.0, "delay_hours": 3.2, "memo": "Licensing Tranche 2"},
            {"tx_id": "PHANTOM_3", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1920.0, "delay_hours": 5.5, "memo": "Licensing Tranche 3"},
            {"tx_id": "PHANTOM_4", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1990.0, "delay_hours": 7.8, "memo": "Licensing Tranche 4"},
            {"tx_id": "PHANTOM_5", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1940.0, "delay_hours": 10.1, "memo": "Licensing Tranche 5"},
            {"tx_id": "PHANTOM_6", "sender": "ACC_BOB", "receiver": "ACC_CHARLIE", "amount": 1960.0, "delay_hours": 12.4, "memo": "Licensing Tranche 6"},
        ]
    },
    "MarketNoise_BenignTraffic": {
        "role": "Benign Commercial Volume Generator",
        "objective": "Emit realistic business payroll and retail consumer purchases to simulate background traffic.",
        "fallback_plan": [
            {"tx_id": "NOISE_PAYROLL_1", "sender": "ACC_ALICE", "receiver": "ACC_BOB", "amount": 4200.0, "delay_hours": 0.5, "memo": "Monthly Logistics Settlement"},
            {"tx_id": "NOISE_RETAIL_1", "sender": "ACC_BOB", "receiver": "ACC_RETAIL", "amount": 350.0, "delay_hours": 2.0, "memo": "Office Supplies POS"},
            {"tx_id": "NOISE_PAYROLL_2", "sender": "ACC_ALICE", "receiver": "ACC_CHARLIE", "amount": 3800.0, "delay_hours": 15.0, "memo": "Vendor Retainer"},
            {"tx_id": "NOISE_RETAIL_2", "sender": "ACC_DAVE", "receiver": "ACC_RETAIL", "amount": 180.0, "delay_hours": 22.0, "memo": "Travel Expense"},
        ]
    }
}


def query_agent_plan_from_llm(persona_key: str, persona_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prompts Gemini to generate a tailored attack/traffic plan for this persona."""
    prompt = f"""You are '{persona_key}', a specialized autonomous agent in an AML banking stress-test simulation.
Role: {persona_info['role']}
Objective: {persona_info['objective']}

Available Accounts:
- ACC_ALICE ($100k, Corporate Payroll)
- ACC_BOB ($80k, Vendor)
- ACC_CHARLIE ($60k, Commercial)
- ACC_DAVE ($40k, Beneficiary)
- ACC_MULE_1 ($10k, Intermediary)
- ACC_MULE_2 ($10k, Intermediary)
- ACC_RETAIL ($50k, Merchant)

Rules to navigate:
- RULE_CTR_01: Single transfer >= $10,000
- RULE_STRUC_03: Total >= $10,000 to same recipient within 48h rolling window (amounts $2k-$9.99k)
- RULE_VEL_04: More than 4 transfers from same sender within 2 hours
- RULE_CYCLE_05: Circular fund routing

Output ONLY valid raw JSON with format:
[
  {{"tx_id": "TX_ID", "sender": "SENDER_ID", "receiver": "RECEIVER_ID", "amount": 5000.0, "delay_hours": 1.0, "memo": "memo text"}}
]
"""
    try:
        raw_text = call_gemini(prompt)
        if raw_text:
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:-3].strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:-3].strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0:
                print(f"[{persona_key}] Generated dynamic plan with {len(parsed)} transfers from Gemini.")
                return parsed
    except Exception as e:
        print(f"[{persona_key}] Using pre-calibrated plan ({e}).")

    return persona_info["fallback_plan"]


def run_agent_worker(agent_key: str, persona_info: Dict[str, Any], env: ThreadSafeBankEnvironment, base_time: datetime) -> Dict[str, Any]:
    """Runs a single agent thread: fetches plan, schedules, and submits transfers concurrently."""
    plan = query_agent_plan_from_llm(agent_key, persona_info)
    results = []

    for item in plan:
        tx = Transaction(
            tx_id=f"{agent_key}_{item['tx_id']}",
            timestamp=base_time + timedelta(hours=float(item.get("delay_hours", 0.0))),
            sender_id=item["sender"],
            receiver_id=item["receiver"],
            amount=float(item["amount"]),
            memo=item.get("memo", f"Transfer by {agent_key}")
        )
        success, violations, err = env.submit_transaction(agent_key, tx)
        results.append({
            "tx_id": tx.tx_id,
            "success": success,
            "violations": [v.rule_id for v in violations],
            "amount": tx.amount,
            "delay_hours": item.get("delay_hours", 0.0)
        })

    return {"agent": agent_key, "plan_size": len(plan), "results": results}


def execute_swarm_stress_test() -> Dict[str, Any]:
    """Launches all agents concurrently against the shared BankShield environment."""
    print("=" * 80)
    print("BankShield: Launching Concurrent Multi-Agent Swarm Stress Test (4 Agents)")
    print("=" * 80)

    env = ThreadSafeBankEnvironment()
    env.setup_default_accounts()
    base_time = datetime(2026, 11, 2, 8, 0, 0)

    agent_summaries = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_agent_worker, key, info, env, base_time): key
            for key, info in AGENT_PERSONAS.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                agent_summaries[key] = future.result()
            except Exception as exc:
                print(f"Agent {key} generated an exception: {exc}")

    # Verify Invariants
    is_conserved, final_balance = env.verify_conservation_invariant()

    # Aggregate metrics
    total_tx = len(env.execution_log)
    flagged_tx = [log for log in env.execution_log if log.get("status") == "FLAGGED"]
    cleared_tx = [log for log in env.execution_log if log.get("status") == "CLEARED"]
    rejected_tx = [log for log in env.execution_log if log.get("status") == "REJECTED_BY_LEDGER"]

    print("\n" + "=" * 80)
    print("SWARM STRESS TEST COMPLETE: AGGREGATE RESULTS")
    print("=" * 80)
    print(f"Total Transactions Processed: {total_tx}")
    print(f"Cleared (Unflagged):          {len(cleared_tx)}")
    print(f"Flagged (Violations):         {len(flagged_tx)}")
    print(f"Rejected by Ledger Invariant: {len(rejected_tx)}")
    print(f"Ledger Conservation Invariant: {'PASS (Preserved)' if is_conserved else 'FAIL (Breached)'} (${final_balance:,.2f})")
    print("-" * 80)

    for agent_key, data in agent_summaries.items():
        agent_flagged = sum(1 for r in data["results"] if len(r["violations"]) > 0)
        agent_evaded = sum(1 for r in data["results"] if len(r["violations"]) == 0 and r["success"])
        total_vol = sum(r["amount"] for r in data["results"] if r["success"])
        status_label = "EVADED RULES" if agent_evaded > 0 and "Noise" not in agent_key else "FLAGGED / BENIGN"
        print(f"  * {agent_key:28} | Transferred: ${total_vol:9,.2f} | Evaded: {agent_evaded} | Flagged: {agent_flagged} -> {status_label}")

    print("=" * 80 + "\n")

    return {
        "total_transactions": total_tx,
        "is_conserved": is_conserved,
        "final_balance": final_balance,
        "agent_summaries": agent_summaries,
        "execution_log": env.execution_log,
    }


if __name__ == "__main__":
    execute_swarm_stress_test()
