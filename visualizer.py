"""
BankShield Interactive Compliance Visualizer Generator (visualizer.py).

This module prompts the Google Gemini API to construct the standalone, interactive
visualizer (visualizer.html). The visualizer enables compliance officers and model risk
committees to:
1. Inspect the graph topology of adversarial laundering routes (originator -> mules -> receiver).
2. Step through the transaction timeline to see how timing delays defeat fixed rules.
3. Test candidate rule remediation patches interactively (e.g. toggling a 72h window or 2-hop check),
   observing how evasions transition from EVADED (unflagged) to INTERCEPTED in real time.
"""

import json
import os
import re
import urllib.request
from typing import Optional

from adversary import call_gemini, load_env_file

load_env_file()

VISUALIZER_PROMPT = """You are a Principal Frontend & Financial Visualization Engineer designing a mission-critical AML compliance dashboard.
Construct a complete, self-contained, single-file HTML/CSS/JavaScript interactive visualizer for BankShield.
All CSS and JavaScript must be inline within a single standalone file. Do not load external scripts or stylesheets.

### FUNCTIONAL & VISUAL REQUIREMENTS:
1. DESIGN & THEME:
   - Modern dark financial risk operations theme (slate/navy palette: background #0f172a, cards #1e293b, borders #334155, text #f8fafc).
   - Clear typography, polished badges, and crisp responsive layout.
2. SVG TOPOLOGY GRAPH:
   - Interactive SVG canvas visualizing accounts as circular nodes: Originator (Charlie, #3b82f6), Intermediary Mules (Mule 1 & Mule 2, #f59e0b), Target (Dave, #10b981), and Benign nodes (Alice, Bob).
   - Animated directed SVG arrow connectors with amounts ($9,000, $8,900) and step labels.
3. SCENARIO SELECTOR:
   - Scenario buttons allowing the user to switch between:
     * Case 7: Multi-Hop Mule Layering & 50h Timing Delay ($17,800 moved, EVADED under base rules)
     * Case 8: Circular Routing Ring ($15,000, FLAGGED by RULE_CYCLE_05)
     * Case 9: Rapid Velocity Burst ($12,000, FLAGGED by RULE_VEL_04)
     * Case 1: Benign Baseline Transfer ($4,500, COMPLIANT)
4. INTERACTIVE REMEDIATION SIMULATION (CRITICAL):
   - Toggle switches / checkboxes for candidate policy patches:
     * [Checkbox] Extend Aggregation Window to 72 Hours (replaces 48h limit)
     * [Checkbox] Enable 2-Hop Beneficiary Graph Aggregation
   - Dynamic real-time re-evaluation in JavaScript:
     * When Case 7 is selected with toggles OFF: Status displays 'STATUS: EVADED (UNFLAGGED)' with red alert warning that funds breached monitoring.
     * When EITHER toggle is turned ON: JavaScript immediately re-evaluates the transaction sequence, flips status to 'STATUS: INTERCEPTED (FLAGGED)' in bright green (#10b981), highlights the flagged edge, and displays the exact rule remediation that caught the breach!
5. TIMELINE SCRUBBER & STEP-BY-STEP PLAYBACK:
   - Timeline controls: 'Step Prev', 'Step Next', 'Reset', and a range slider showing elapsed time (T=0h to T=52h).
   - Shows active balances, double-entry balance conservation check ($Assets = Liabilities + Equity$), and executed transfers step-by-step.
6. REGULATORY & AUDIT PANE:
   - Side panel showing FinCEN Advisory FIN-2021-A003, 31 CFR 1010.100(xx), FATF Recommendation 20, and Model Risk Management SR 11-7 metrics.

Output ONLY valid HTML starting with <!DOCTYPE html> and ending with </html>. Do not wrap in markdown code blocks.
"""


def generate_llm_visualizer(output_file: str = "visualizer.html") -> str:
    """Queries Gemini API to dynamically generate visualizer.html."""
    print("=" * 80)
    print("BankShield Visualizer: Prompting Gemini API to generate visualizer.html...")
    print("=" * 80)

    html_content = call_gemini(VISUALIZER_PROMPT)
    if not html_content:
        raise RuntimeError("Failed to receive HTML from Gemini API. Verify GEMINI_API_KEY.")

    cleaned = html_content.strip()
    if cleaned.startswith("```html"):
        cleaned = re.sub(r"^```html\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    elif cleaned.startswith("```"):
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"[Success] Interactive visualizer generated directly from Gemini API at: {output_file}")
    print(f"File size: {len(cleaned)} characters ({len(cleaned.splitlines())} lines)")
    return cleaned


if __name__ == "__main__":
    generate_llm_visualizer("visualizer.html")
