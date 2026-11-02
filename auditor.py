"""
BankShield Compliance Auditor Agent (auditor.py).

This module represents the Blue-Team compliance auditor:
1. Receives an unflagged transaction sequence that successfully evaded rules.
2. Analyzes the failure root causes (e.g. fixed 48h window boundary, 1-hop limit).
3. Produces a structured audit finding matching the FATF/FinCEN regulatory mapping.
4. Generates a recommended rule patch diff for human compliance officer review.
"""

import json
from typing import Any, Dict


def generate_audit_finding(evasion_scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the structured audit record for compliance committee review."""
    transfers = evasion_scenario.get("transfers", [])
    total_moved = sum(t["amount"] for t in transfers)
    delays = [t.get("delay_hours", 0.0) for t in transfers]
    max_delay = max(delays) if delays else 0.0

    finding = {
        "finding_id": "AUDIT-2026-BS-001",
        "severity": "HIGH",
        "title": "Multi-Hop Fan-Out and Window Boundary Evasion",
        "blind_spot": (
            f"The transaction monitoring engine failed to flag a coordinated transfer of "
            f"${total_moved:,.2f} because transfers were split across intermediary mule accounts "
            f"and delayed beyond the standard 48-hour rolling aggregation window (elapsed: {max_delay:.1f}h)."
        ),
        "evidence": {
            "scenario_name": evasion_scenario.get("scenario_name"),
            "total_transferred": total_moved,
            "transfer_count": len(transfers),
            "executed_transfers": transfers,
        },
        "regulatory_mapping": {
            "statute": "31 U.S.C. 5318(g) / 31 CFR 1010.100(xx) (Anti-Structuring)",
            "fincen_guidance": "FinCEN Advisory FIN-2021-A003 (Layering and Structured Payments)",
            "fatf_recommendation": "FATF Recommendation 20 (Suspicious Transaction Reporting) and Recommendation 1 (Risk-Based Approach)",
        },
        "impact": "Laundering syndicates can move high-value amounts by staging intermediate transfers across multiple accounts over several days without tripping single-institution 48-hour rules.",
        "proposed_remediation": {
            "control_type": "Rule Modification",
            "affected_rule": "RULE_STRUC_03",
            "proposed_changes": [
                "1. Extend the rolling aggregation window from 48 hours to 72 hours for multi-transfer volumes exceeding $10,000.",
                "2. Implement 2-hop beneficiary graph aggregation to detect common terminal receivers across linked accounts.",
                "3. Introduce an exponential-decay velocity score to weight burst transactions over extended intervals."
            ],
            "estimated_false_positive_impact": "Moderate increase in low-risk commercial wire reviews; mitigate by adding whitelists for verified corporate payroll accounts.",
        },
        "governance": {
            "approval_required": "BSA/AML Compliance Officer and Model Risk Committee (SR 11-7 validation)",
            "action": "PENDING_HUMAN_APPROVAL",
            "deployment_status": "STAGED_IN_TEST_ENVIRONMENT",
        }
    }
    return finding


def print_audit_report(finding: Dict[str, Any]):
    print("\n" + "=" * 80)
    print(f"BANKSHIELD COMPLIANCE AUDIT REPORT: [{finding['finding_id']}] - {finding['severity']}")
    print("=" * 80)
    print(f"Title:       {finding['title']}")
    print(f"Blind Spot:  {finding['blind_spot']}")
    print("-" * 80)
    print("Regulatory Mapping:")
    print(f"  * Statute:  {finding['regulatory_mapping']['statute']}")
    print(f"  * FinCEN:   {finding['regulatory_mapping']['fincen_guidance']}")
    print(f"  * FATF:     {finding['regulatory_mapping']['fatf_recommendation']}")
    print("-" * 80)
    print("Proposed Rule Remediation Diff:")
    for change in finding['proposed_remediation']['proposed_changes']:
        print(f"  {change}")
    print(f"\nTrade-off Analysis: {finding['proposed_remediation']['estimated_false_positive_impact']}")
    print("-" * 80)
    print(f"Governance Action: {finding['governance']['action']} ({finding['governance']['approval_required']})")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    from adversary import fallback_adversary_mutation
    evasion_trace = fallback_adversary_mutation(2)
    finding = generate_audit_finding(evasion_trace)
    print_audit_report(finding)

