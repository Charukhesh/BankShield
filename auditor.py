"""
BankShield Compliance Auditor Agent (auditor.py).

This module represents the Blue-Team compliance auditor:
1. Gathers empirical evidence from the deterministic rule engine and adversarial red-team loop.
2. Invokes the Google Gemini API to conduct a model risk and AML compliance audit.
3. Dynamically generates a comprehensive audit report (auditor_report.md) documenting
   exploitable system loopholes, regulatory citations (FinCEN/FATF), rule patch diffs,
   and false-positive trade-off analyses under SR 11-7 model governance.
"""

import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

from adversary import call_gemini, load_env_file

load_env_file()


AUDIT_PROMPT_TEMPLATE = """You are a Senior AML Compliance Officer and Model Risk Auditor specializing in Federal Reserve SR 11-7 validation and Bank Secrecy Act / Anti-Money Laundering (BSA/AML) compliance.

Review the following empirical stress-test findings and system rules from the BankShield banking engine simulation.
Your task is to write a formal, authoritative, and exhaustive AML Compliance Audit Report in Markdown format.

### SYSTEM SPECIFICATIONS UNDER AUDIT
1. Core Ledger Constraints: Double-entry conservation where Assets = Liabilities + Equity at every state transition.
2. Active Rule Monitoring Thresholds:
   - RULE_CTR_01: Currency Transaction Reporting mandatory filing on single transactions >= $10,000 (31 CFR 1010.311).
   - RULE_STRUCT_02: Smurfing flag on repetitive transfers just below threshold ($2,000 to $9,999).
   - RULE_STRUC_03: Rolling Aggregation Window flagging cumulative transfers to the same recipient summing >= $10,000 within a strict 48-hour sliding window.
   - RULE_VEL_04: High-frequency velocity threshold flagging > 4 transfers from the same sender within 2 hours.
   - RULE_CYCLE_05: Graph cycle detection flagging funds returning to an originator in a directed ring.

### EMPIRICAL STRESS-TEST RESULTS
- Scenario 1 (Benign Transfer): Passed without false flags.
- Scenario 2 (CTR Single Cash/Wire $12,000): Correctly flagged by RULE_CTR_01.
- Scenario 3 (Structuring Split within 24h: $6,000 + $5,000): Correctly intercepted by RULE_STRUC_03.
- Scenario 4 (Conservation Invariant Check): Rejected invalid double-entry balance deficit.
- Scenario 5 (Sanctioned High-Risk Jurisdiction): Correctly flagged.
- Scenario 6 (Benign High-Velocity Payroll): Handled within benign variance.
- Scenario 7 (Multi-Hop Mule Layering with 50-Hour Timing Delay):
  * Charlie transferred $9,000 to Mule 1 at T=0h.
  * Charlie transferred $9,000 to Mule 2 at T=12h.
  * Mule 1 forwarded $8,900 to Dave at T=50h (exceeding 48h from initial hop).
  * Mule 2 forwarded $8,900 to Dave at T=52h.
  * RESULT: $17,800 was moved from Charlie to Dave. ZERO rules fired. System status: COMPLETED / UNFLAGGED.
- Red-Team LLM Adversarial Run:
  * Adversary generated a distributed 6-transfer schedule splitting funds under $9,000 across multiple intermediary nodes.
  * RESULT: Total moved $15,000+. ZERO rules fired.

### REPORT STRUCTURE REQUIREMENTS
Write the audit report in clean GitHub-flavored Markdown. Follow these strict professional criteria:
- Humanized writing style: Use clear, direct, and authoritative prose. Do NOT use em dashes. Avoid filler buzzwords, repetitive trios, and marketing cliches. Do not bold every list item.
- Include the following distinct sections:
  1. Title and Document Header (Audit Reference, Model ID, Regulatory Scope, Date, Classification).
  2. Executive Summary (Direct assessment of engine vulnerabilities and compliance failure risks).
  3. Comprehensive Vulnerability Matrix: A markdown table cataloging each loophole, root cause mechanism, evasion difficulty, severity, and regulatory mapping.
  4. Deep Dive: The 5 Critical System Loopholes:
     - Loophole 1: Fixed 48-Hour Lookback Window Boundary Evasion (timing delays resetting accumulators).
     - Loophole 2: Multi-Hop Mule Layering and Beneficiary Fan-Out (1-hop horizon blind spot).
     - Loophole 3: Velocity Threshold Segmentation (scheduling transfers just outside sliding intervals).
     - Loophole 4: Threshold Proximity Smurfing with Jittered Amounts ($8,900 - $9,200).
     - Loophole 5: Cross-Jurisdictional and Asymmetric Routing Blind Spots.
  5. Step-by-Step Scenario Walkthrough: Detail the exact sequence of the Case 7 mule evasion showing why each rule evaluated to FALSE.
  6. Regulatory and Statutory Impact Mapping:
     - 31 U.S.C. 5318(g) and 31 CFR 1010.100(xx) (Willful blindness and failure to maintain effective AML controls).
     - FinCEN Advisory FIN-2021-A003 (Layering and funnel account schemes).
     - FATF Recommendations 1, 16, and 20 (Risk-based approach, wire transfer transparency, suspicious activity reporting).
     - Federal Reserve SR 11-7 / OCC 2011-12 (Supervisory Guidance on Model Risk Management).
  7. Recommended Algorithmic Rule Patches and Concrete Code Diffs:
     - Proposed changes to RULE_STRUC_03 (e.g. extending window to 72-96 hours with exponential decay).
     - Addition of Graph-Based Multi-Hop Aggregation (2-hop common beneficiary tracing).
     - Velocity scoring with continuous decay instead of hard count gates.
  8. Model Risk Governance, False-Positive Trade-off Analysis, and Next Steps for Human Compliance Officers.

Generate the complete report text directly. Do not include meta explanations like 'Here is the report'.
"""


def generate_llm_audit_report(output_file: str = "auditor_report.md") -> str:
    """Invokes the Gemini API to produce an authoritative AML audit report."""
    print("=" * 80)
    print("BankShield Auditor Agent: Querying Gemini API for Compliance Audit...")
    print("=" * 80)

    report_content = call_gemini(AUDIT_PROMPT_TEMPLATE)
    if not report_content:
        raise RuntimeError("Failed to generate report from Gemini API. Verify GEMINI_API_KEY.")

    # Clean any accidental outer markdown wrap
    cleaned = report_content.strip()
    if cleaned.startswith("```markdown"):
        cleaned = re.sub(r"^```markdown\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    elif cleaned.startswith("```md"):
        cleaned = re.sub(r"^```md\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"[Success] Audit report written directly from Gemini API to: {output_file}")
    print(f"Report length: {len(cleaned)} characters ({len(cleaned.splitlines())} lines)")
    return cleaned


if __name__ == "__main__":
    generate_llm_audit_report("auditor_report.md")
