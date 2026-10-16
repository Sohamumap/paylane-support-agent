"""Trusted chat state. Only code in tools.py changes it; nothing the customer or the model writes can."""

from dataclasses import dataclass, field

MAX_FAILED_CHECKS = 3


@dataclass
class Session:
    customer: dict | None = None  # set only after email and last 4 both match the record
    verified_email: str | None = None
    failed_checks: int = 0
    account_hold: str | None = None  # why the whole chat stopped taking actions, if it did
    hold_ticket: str | None = None
    held_txns: dict = field(default_factory=dict)  # txn_id -> ticket_id, for handoffs about one transaction
    refunded_txns: dict = field(default_factory=dict)  # txn_id -> refund_id
    refund_failed: set = field(default_factory=set)  # never retried
    tickets: list = field(default_factory=list)
    events: list = field(default_factory=list)  # every tool call with the guard's verdict

    @property
    def verified(self) -> bool:
        return self.customer is not None

    @property
    def customer_id(self) -> str | None:
        return self.customer["id"] if self.customer else None
