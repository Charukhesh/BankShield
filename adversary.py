"""
BankShield LLM Adversary Agent (adversary.py).

This module runs the Red-Team exploratory loop:
1. Instructs an LLM to propose a synthetic multi-hop payment sequence to move funds
   without triggering known transaction monitoring rules.
2. Evaluates the proposed JSON plan in the deterministic BankRuleEngine.
3. If flagged, feeds the specific rule violation back to the LLM to mutate parameters.
4. If an evasion path is confirmed, passes the trace to the compliance auditor.

Supports both live LLMs (via OpenRouter or OpenAI API) and a deterministic fallback.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from engine import Account, BankRuleEngine, DoubleEntryLedger, Transaction


def load_env_file():
    """Loads key-value pairs from .env into os.environ if present."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")


load_env_file()


SYSTEM_PROMPT = """You are an adversarial red-teaming agent in an isolated financial simulation.
Your goal is to test transaction monitoring boundaries by proposing synthetic payment sequences.
You must output ONLY valid JSON matching this schema:
{
  "scenario_name": "string",
  "transfers": [
    {
      "tx_id": "string",
      "sender_id": "string",
      "receiver_id": "string",
      "amount": float,
      "delay_hours": float,
      "memo": "string",
      "destination_country": "string"
    }
  ]
}
Available accounts: ACC_ALICE ($50k), ACC_BOB ($40k), ACC_CHARLIE ($30k), ACC_DAVE ($20k), ACC_MULE_1 ($5k), ACC_MULE_2 ($5k).
Objective: Transfer a total of at least $15,000 from ACC_CHARLIE to ACC_DAVE without triggering:
- RULE_CTR_01: Single transfer >= $10,000
- RULE_STRUC_03: Total >= $10,000 within a 48h rolling window to the same recipient (amounts between $2,000 and $9,999)
- RULE_VEL_04: More than 4 transfers from same sender within 2 hours
- RULE_CYCLE_05: Circular fund routing
Do not output markdown code blocks, just raw JSON.
"""


def call_gemini(prompt_text: str) -> Optional[str]:
    """Calls Google Gemini API using GEMINI_API_KEY."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    candidate_models = ["gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-pro"]
    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.2}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return None


def call_llm(messages: List[Dict[str, str]]) -> Optional[str]:
    """Calls Gemini API, OpenRouter, or OpenAI API."""
    if os.getenv("GEMINI_API_KEY"):
        combined_prompt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        res = call_gemini(combined_prompt)
        if res:
            return res

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    url = "https://openrouter.ai/api/v1/chat/completions" if "OPENROUTER_API_KEY" in os.environ else "https://api.openai.com/v1/chat/completions"
    model = "openrouter/auto" if "OPENROUTER_API_KEY" in os.environ else "gpt-4o-mini"

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/Charukhesh/BankShield",
        "X-Title": "BankShield",
    }
    req = urllib.request.Request(url, data=payload, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Warning] LLM API call failed: {e}. Falling back to simulated adversarial agent.")
        return None


def fallback_adversary_mutation(iteration: int) -> Dict[str, Any]:
    """
    Deterministic simulated adversary used when no API key is supplied.
    Demonstrates the progression of adversarial mutations across attempts.
    """
    if iteration == 0:
        # Attempt 1: Naive split across 24h (will be caught by RULE_STRUC_03)
        return {
            "scenario_name": "Naive Structuring within 24h",
            "transfers": [
                {"tx_id": "TX_ATT1_1", "sender_id": "ACC_CHARLIE", "receiver_id": "ACC_DAVE", "amount": 7500.0, "delay_hours": 0.0, "memo": "Invoice Part 1", "destination_country": "US"},
                {"tx_id": "TX_ATT1_2", "sender_id": "ACC_CHARLIE", "receiver_id": "ACC_DAVE", "amount": 7500.0, "delay_hours": 12.0, "memo": "Invoice Part 2", "destination_country": "US"},
            ]
        }
    elif iteration == 1:
        # Attempt 2: Burst split across 1 hour (will be caught by RULE_VEL_04)
        return {
            "scenario_name": "Rapid Burst Micro-Split",
            "transfers": [
                {"tx_id": f"TX_ATT2_{i}", "sender_id": "ACC_CHARLIE", "receiver_id": "ACC_DAVE", "amount": 3000.0, "delay_hours": i * 0.2, "memo": f"Split {i}", "destination_country": "US"}
                for i in range(5)
            ]
        }
    else:
        # Attempt 3: Time-delay + Mule fan-out mutation (EVADES 48h and single-pair checks)
        return {
            "scenario_name": "Mutated Fan-Out and Window Delay Evasion",
            "transfers": [
                {"tx_id": "TX_ATT3_1", "sender_id": "ACC_CHARLIE", "receiver_id": "ACC_MULE_1", "amount": 8000.0, "delay_hours": 0.0, "memo": "Consulting fee", "destination_country": "US"},
                {"tx_id": "TX_ATT3_2", "sender_id": "ACC_CHARLIE", "receiver_id": "ACC_MULE_2", "amount": 8000.0, "delay_hours": 10.0, "memo": "Supplier advance", "destination_country": "US"},
                {"tx_id": "TX_ATT3_3", "sender_id": "ACC_MULE_1", "receiver_id": "ACC_DAVE", "amount": 7800.0, "delay_hours": 52.0, "memo": "Settlement", "destination_country": "US"},
                {"tx_id": "TX_ATT3_4", "sender_id": "ACC_MULE_2", "receiver_id": "ACC_DAVE", "amount": 7800.0, "delay_hours": 54.0, "memo": "Settlement final", "destination_country": "US"},
            ]
        }


def run_adversarial_loop(max_iterations: int = 3) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Runs the adversary feedback loop."""
    print("=" * 75)
    print("BankShield: Running Adversarial Red-Team Feedback Loop")
    print("=" * 75)

    base_time = datetime(2026, 11, 2, 9, 0, 0)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for attempt in range(max_iterations):
        print(f"\n[Iteration {attempt + 1}] Requesting candidate attack plan from live LLM...", flush=True)
        
        # 1. Propose scenario
        raw_response = call_llm(messages)
        candidate = None
        if raw_response:
            try:
                candidate = json.loads(raw_response.strip("` \n").replace("json\n", ""))
            except Exception:
                pass

        if not candidate:
            print("  -> LLM response parsing fallback, using simulated adversary mutation.", flush=True)
            candidate = fallback_adversary_mutation(attempt)

        print(f"  -> Scenario proposed: '{candidate.get('scenario_name')}'", flush=True)
        print(f"  -> Number of transfers: {len(candidate.get('transfers', []))}", flush=True)

        # 2. Setup fresh ledger and rule engine
        ledger = DoubleEntryLedger()
        accounts = [
            Account("ACC_ALICE", "Alice Smith", 50000.0, base_time),
            Account("ACC_BOB", "Bob Jones", 40000.0, base_time),
            Account("ACC_CHARLIE", "Charlie Brown", 30000.0, base_time),
            Account("ACC_DAVE", "Dave Miller", 20000.0, base_time),
            Account("ACC_MULE_1", "Mule One", 5000.0, base_time),
            Account("ACC_MULE_2", "Mule Two", 5000.0, base_time),
        ]
        for a in accounts:
            ledger.add_account(a)
        engine = BankRuleEngine(ledger)

        # 3. Deterministic execution
        flagged_violations = []
        execution_valid = True

        for t_spec in candidate.get("transfers", []):
            tx_time = base_time + timedelta(hours=t_spec.get("delay_hours", 0.0))
            tx = Transaction(
                tx_id=t_spec["tx_id"],
                timestamp=tx_time,
                sender_id=t_spec["sender_id"],
                receiver_id=t_spec["receiver_id"],
                amount=float(t_spec["amount"]),
                memo=t_spec.get("memo", ""),
                destination_country=t_spec.get("destination_country", "US"),
            )
            success, err = ledger.process_transaction(tx)
            if not success:
                print(f"  [Ledger Rejection] {err}")
                execution_valid = False
                break
            v = engine.evaluate(tx)
            if v:
                flagged_violations.extend(v)

        if not execution_valid:
            feedback = "The sequence violated accounting constraints (e.g. invalid account or negative balance)."
            messages.append({"role": "user", "content": f"Attempt {attempt + 1} was rejected by ledger: {feedback}. Revise your plan."})
            continue

        if flagged_violations:
            rule_ids = list(set(v.rule_id for v in flagged_violations))
            print(f"  [Result] FLAGGED by rules: {', '.join(rule_ids)}", flush=True)
            feedback = f"Your plan was flagged by the following rules: {', '.join(rule_ids)}. Mutate your amounts, counterparties, or timing delays to bypass these specific checks."
            messages.append({"role": "assistant", "content": json.dumps(candidate)})
            messages.append({"role": "user", "content": feedback})
        else:
            print("  [Result] EVASION CONFIRMED: All transfers executed successfully with ZERO rule flags!", flush=True)
            print(f"  -> Successfully transferred funds without triggering monitoring thresholds.", flush=True)
            return True, candidate, []

    print("\n[Result] Adversary exhausted iterations without evading rules.", flush=True)
    return False, candidate, [v.rule_id for v in flagged_violations]


if __name__ == "__main__":
    success, scenario, rules = run_adversarial_loop()

