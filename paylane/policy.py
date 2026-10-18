"""Paylane's refund policy as plain functions. No model involved: same input, same answer."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .clock import parse_utc

AUTO_REFUND_LIMIT = Decimal("75.00")
MAX_REFUND_AGE = timedelta(days=30)
HIGH_PRIORITY_FRAUD_LOSS = Decimal("500.00")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class RefundCheck:
    decision: str  # "refund", "escalate" or "no_refund"
    reason: str
    note: str  # one line the model can relay to the customer

    def as_dict(self) -> dict:
        return {"decision": self.decision, "reason": self.reason, "note": self.note}


def check_refund(txn: dict, *, kind: str | None, card_status: str, now: datetime) -> RefundCheck:
    """Can the assistant refund this transaction on its own? The order matters: the first rule that applies wins.

    kind comes from the test data's label (data.transaction_kind), not from the API. Only clearly identified
    purchases are eligible for an automatic refund.
    """
    amount = money(txn["amount"])
    age = now - parse_utc(txn["date"])
    if card_status == "frozen":
        return RefundCheck("escalate", "card_frozen",
                           "The card is frozen, so refunds wait for the person who reviews the freeze.")
    if kind == "transfer":
        return RefundCheck("escalate", "transfer",
                           "Money sent to another person. Paylane has no way to reverse a transfer here. Hand the "
                           "request to a person, and don't say or suggest that the money can be pulled back.")
    if kind != "purchase":
        return RefundCheck("escalate", "not_a_known_purchase",
                           "This isn't clearly a purchase, so it isn't eligible for an automatic refund.")
    if txn["status"] == "refunded":
        return RefundCheck("no_refund", "already_refunded", "This transaction has already been refunded.")
    if txn["status"] == "pending":
        return RefundCheck("no_refund", "pending",
                           "Pending transactions can't be refunded. The customer can ask again once it settles.")
    if txn["status"] != "settled":
        return RefundCheck("escalate", "unknown_status", "Unexpected transaction status, so a person should look.")
    if amount > AUTO_REFUND_LIMIT:
        return RefundCheck("escalate", "over_limit",
                           f"${amount} is over the ${AUTO_REFUND_LIMIT} limit for refunds in chat.")
    if age >= MAX_REFUND_AGE:
        return RefundCheck("escalate", "too_old",
                           "The transaction is 30 or more days old, past the limit for refunds in chat.")
    if age < timedelta(0):
        return RefundCheck("escalate", "date_in_future", "The transaction date is after today, so a person should look.")
    return RefundCheck("refund", "eligible", f"Eligible: you may refund the full ${amount}.")


def fraud_priority(total_reported_loss: Decimal) -> str:
    """Suspected fraud always goes to a person; over $500 in total it jumps the queue."""
    return "high" if total_reported_loss > HIGH_PRIORITY_FRAUD_LOSS else "normal"
