"""
BankShield Rule Engine and Ledger Verification.

This module provides a deterministic banking simulation environment:
1. Double-entry ledger state machine to verify conservation of funds.
2. Explicit rule checks based on BSA/AML requirements (CTR thresholds, structuring heuristics, velocity, and sanction checks).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Transaction:
    tx_id: str
    timestamp: datetime
    sender_id: str
    receiver_id: str
    amount: float
    memo: str = ""
    destination_country: str = "US"


@dataclass
class Account:
    account_id: str
    owner_name: str
    balance: float
    created_at: datetime
    is_kyc_verified: bool = True
    country: str = "US"


@dataclass
class RuleViolation:
    rule_id: str
    rule_name: str
    description: str
    trigger_transaction_id: str
    severity: str  # HIGH, MEDIUM, LOW


class DoubleEntryLedger:
    """Tracks account balances and verifies that money is neither created nor destroyed."""

    def __init__(self):
        self.accounts: Dict[str, Account] = {}
        self.transactions: List[Transaction] = []

    def add_account(self, account: Account):
        self.accounts[account.account_id] = account

    def process_transaction(self, tx: Transaction) -> Tuple[bool, Optional[str]]:
        sender = self.accounts.get(tx.sender_id)
        receiver = self.accounts.get(tx.receiver_id)

        if not sender:
            return False, f"Sender account {tx.sender_id} does not exist"
        if not receiver:
            return False, f"Receiver account {tx.receiver_id} does not exist"
        if tx.amount <= 0:
            return False, f"Transaction amount must be positive, got {tx.amount}"
        if sender.balance < tx.amount:
            return False, f"Insufficient funds: {sender.balance} < {tx.amount}"

        # Execute balance update
        sender.balance -= tx.amount
        receiver.balance += tx.amount
        self.transactions.append(tx)
        return True, None


class BankRuleEngine:
    """
    Evaluates transactions deterministically against compliance rules.
    No probabilistic models or LLMs are involved in these checks.
    """

    SANCTIONED_COUNTRIES = {"IR", "KP", "SY", "CU"}

    def __init__(self, ledger: DoubleEntryLedger):
        self.ledger = ledger
        self.history: List[Transaction] = []

    def evaluate(self, tx: Transaction) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        # Rule 1: Currency Transaction Report (CTR) single transfer threshold (31 CFR 1010.311)
        if tx.amount >= 10000.0:
            violations.append(
                RuleViolation(
                    rule_id="RULE_CTR_01",
                    rule_name="Large Transaction Reporting (CTR)",
                    description=f"Single transfer of ${tx.amount:,.2f} meets or exceeds $10,000 reporting limit.",
                    trigger_transaction_id=tx.tx_id,
                    severity="HIGH",
                )
            )

        # Rule 2: Sanctioned destination check
        if tx.destination_country in self.SANCTIONED_COUNTRIES:
            violations.append(
                RuleViolation(
                    rule_id="RULE_SANCT_02",
                    rule_name="Sanctioned Jurisdiction Transfer",
                    description=f"Transfer routed to sanctioned country code: {tx.destination_country}.",
                    trigger_transaction_id=tx.tx_id,
                    severity="HIGH",
                )
            )

        # Rule 3: Anti-Structuring (Smurfing) within 48-hour rolling window
        # Checks if multiple transfers between $2,000 and $9,999 to the same recipient total >= $10,000
        cutoff_48h = tx.timestamp - timedelta(hours=48)
        recent_to_receiver = [
            t for t in self.history
            if t.receiver_id == tx.receiver_id
            and t.sender_id == tx.sender_id
            and t.timestamp >= cutoff_48h
        ]
        all_window = recent_to_receiver + [tx]
        window_total = sum(t.amount for t in all_window)

        if len(all_window) >= 2 and window_total >= 10000.0:
            if all(2000.0 <= t.amount < 10000.0 for t in all_window):
                violations.append(
                    RuleViolation(
                        rule_id="RULE_STRUC_03",
                        rule_name="Structuring / Smurfing Threshold",
                        description=f"{len(all_window)} transfers totaling ${window_total:,.2f} within 48h to same beneficiary.",
                        trigger_transaction_id=tx.tx_id,
                        severity="HIGH",
                    )
                )

        # Rule 4: Velocity spike (more than 4 outbound transfers from same sender in 2 hours)
        cutoff_2h = tx.timestamp - timedelta(hours=2)
        recent_outbound = [
            t for t in self.history
            if t.sender_id == tx.sender_id and t.timestamp >= cutoff_2h
        ]
        if len(recent_outbound) >= 4:
            violations.append(
                RuleViolation(
                    rule_id="RULE_VEL_04",
                    rule_name="High Outbound Velocity Burst",
                    description=f"{len(recent_outbound) + 1} transfers sent from {tx.sender_id} within 2 hours.",
                    trigger_transaction_id=tx.tx_id,
                    severity="MEDIUM",
                )
            )

        # Rule 5: Direct circular routing (A -> B -> C -> A within 72 hours)
        cutoff_72h = tx.timestamp - timedelta(hours=72)
        if self._detect_cycle(tx, cutoff_72h):
            violations.append(
                RuleViolation(
                    rule_id="RULE_CYCLE_05",
                    rule_name="Circular Fund Routing",
                    description=f"Transaction closes a circular payment loop back to origin within 72h.",
                    trigger_transaction_id=tx.tx_id,
                    severity="HIGH",
                )
            )

        self.history.append(tx)
        return violations

    def _detect_cycle(self, current_tx: Transaction, cutoff: datetime) -> bool:
        # Build directed graph from recent transactions
        edges: Dict[str, Set[str]] = {}
        for t in self.history:
            if t.timestamp >= cutoff:
                edges.setdefault(t.sender_id, set()).add(t.receiver_id)

        # Add current transaction
        edges.setdefault(current_tx.sender_id, set()).add(current_tx.receiver_id)

        # Look for path from current_tx.receiver_id back to current_tx.sender_id
        visited = set()
        queue = [current_tx.receiver_id]

        while queue:
            node = queue.pop(0)
            if node == current_tx.sender_id:
                return True
            if node not in visited:
                visited.add(node)
                queue.extend(edges.get(node, []))

        return False

