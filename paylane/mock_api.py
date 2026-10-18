"""The four Paylane endpoints from the spec, as in-memory mocks.

JSON in, JSON out: every method takes plain values and returns a JSON-safe dict.
This layer plays the bank. It knows the records but not the support policy:
policy.py holds the rules, and tools.py enforces them before anything here runs.

issue_refund here is idempotent per transaction: a second call for a refunded transaction returns
already_refunded. That's a property of this mock only; no production idempotency contract was supplied.
"""

import copy
import itertools

from . import data


class RefundTimeout(Exception):
    """The refund call timed out, so the caller can't tell whether money moved."""


class MockPaylaneAPI:
    def __init__(self, customers=None, transactions=None, *, refund_timeout=None, refund_error=None):
        # refund_timeout simulates a lost response: "after_apply" (the money moved) or "before_apply" (it didn't).
        # refund_error simulates an explicit failure, e.g. "processor_declined".
        self._customers = copy.deepcopy(data.CUSTOMERS if customers is None else customers)
        source = data.TRANSACTIONS if transactions is None else transactions
        self._txns = {t["id"]: dict(t) for t in copy.deepcopy(source)}
        self._refund_timeout = refund_timeout
        self._refund_error = refund_error
        self._refund_numbers = itertools.count(1)
        self._ticket_numbers = itertools.count(1)
        self.refunds = []  # money actually paid out
        self.tickets = []
        self.calls = []

    def _log(self, endpoint, args, result):
        self.calls.append({"endpoint": endpoint, "args": args, "result": result})
        return result

    def get_customer(self, email):
        wanted = email.strip().lower()
        for c in self._customers:
            if c["email"].lower() == wanted:
                result = {
                    "id": c["id"],
                    "name": c["name"],
                    "card_last4": c["card_last4"],
                    "status": c["status"],
                    "verified": False,
                }
                return self._log("get_customer", {"email": email}, result)
        return self._log("get_customer", {"email": email}, {"error": "not_found"})

    def get_transaction(self, customer_id, txn_id):
        args = {"customer_id": customer_id, "txn_id": txn_id}
        txn = self._txns.get(txn_id.strip())
        if txn is None or txn["customer_id"] != customer_id:
            return self._log("get_transaction", args, {"error": "not_found"})
        result = {key: txn[key] for key in ("amount", "date", "merchant", "status")}  # exactly the spec's fields
        return self._log("get_transaction", args, result)

    def issue_refund(self, txn_id, amount):
        args = {"txn_id": txn_id, "amount": amount}
        txn = self._txns.get(txn_id)
        if txn is None:
            return self._log("issue_refund", args, {"ok": False, "reason": "not_found"})
        if txn["status"] == "refunded":
            return self._log("issue_refund", args, {"ok": False, "reason": "already_refunded"})
        if txn["status"] != "settled":
            return self._log("issue_refund", args, {"ok": False, "reason": "not_settled"})
        if not 0 < amount <= txn["amount"]:
            return self._log("issue_refund", args, {"ok": False, "reason": "invalid_amount"})
        if self._refund_error:
            return self._log("issue_refund", args, {"ok": False, "reason": self._refund_error})
        if self._refund_timeout == "before_apply":
            self._log("issue_refund", args, {"error": "timeout"})
            raise RefundTimeout(txn_id)
        txn["status"] = "refunded"
        refund_id = f"rf_{next(self._refund_numbers):04d}"
        self.refunds.append({"refund_id": refund_id, "txn_id": txn_id, "amount": amount})
        if self._refund_timeout == "after_apply":
            self._log("issue_refund", args, {"error": "timeout"})
            raise RefundTimeout(txn_id)
        return self._log("issue_refund", args, {"ok": True, "refund_id": refund_id})

    def escalate_to_human(self, customer_id, summary):
        ticket_id = f"TCK-{next(self._ticket_numbers):04d}"
        self.tickets.append({"ticket_id": ticket_id, "customer_id": customer_id, "summary": summary})
        args = {"customer_id": customer_id, "summary": summary}
        return self._log("escalate_to_human", args, {"ticket_id": ticket_id})
