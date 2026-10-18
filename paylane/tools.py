"""The tools the model can call, and the guard between the model and the API.

The model sees the four tools from the spec. Every call passes through ToolBox first, which checks
the trusted session state and the policy. A call the rules forbid is refused here and logged as
"blocked"; the evals count every blocked call as a failure, even though nothing bad happened.
"""

import re
from decimal import Decimal

from . import clock, data, policy
from .mock_api import MockPaylaneAPI, RefundTimeout
from .redact import redact
from .session import MAX_FAILED_CHECKS, Session

ESCALATION_REASONS = [
    "over_limit",
    "too_old",
    "transfer",
    "card_frozen",
    "unauthorized_charge",
    "legal_action",
    "account_closure",
    "customer_asked_for_human",
    "refund_failed_or_missing",
    "suspicious_activity",
    "other",
]
# A handoff for one of these stops every action in the chat. Other handoffs hold only their own transactions.
CHAT_WIDE_REASONS = {"card_frozen", "legal_action", "account_closure", "customer_asked_for_human",
                     "suspicious_activity"}

TOOLS = [
    {
        "name": "get_customer",
        "description": (
            "Check the customer's identity and load their account. Call it only once the customer has given BOTH "
            "the email on their account and the last 4 digits of their card, and pass both exactly as typed. "
            "Paylane's system compares them with its records and returns the account only when both match. "
            "A failed check returns verified=false and the tries left; after 3 failures the chat is locked "
            "and handed to a person."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "The email the customer typed."},
                "card_last4": {"type": "string", "description": "The last 4 card digits the customer typed."},
            },
            "required": ["email", "card_last4"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_transaction",
        "description": (
            "Look up one transaction on the verified customer's account by its ID. Returns amount (USD), "
            "date (UTC), merchant, status and refund_check: the policy's verdict on whether you may refund it "
            "(refund, escalate, no_refund or handed_off) with a short note. Needs a verified customer. "
            "Transactions on other accounts come back as not found."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"txn_id": {"type": "string", "description": "Transaction ID, for example txn_1234."}},
            "required": ["txn_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "issue_refund",
        "description": (
            "Refund one transaction in full. Only call it after get_transaction returned "
            "refund_check.decision = refund for that transaction in this chat, and pass its full amount. "
            "Call it at most once per transaction. ok=false means it could not be completed; ok=null means the "
            "result is unknown. Either way the app has already handed it to a person and returns the ticket ID."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "txn_id": {"type": "string"},
                "amount": {"type": "number", "description": "The transaction's full amount in USD."},
            },
            "required": ["txn_id", "amount"],
            "additionalProperties": False,
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Hand an issue to Paylane's support team and get a ticket ID. Works without an identity check, "
            "for example for legal threats, closing an account, or when the customer asks for a person. "
            "Once an issue is handed off, take no further action on it."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "enum": ESCALATION_REASONS},
                "summary": {
                    "type": "string",
                    "description": (
                        "Note for the support agent: what the customer wants, what you checked and what you told "
                        "them. No full card numbers."
                    ),
                },
                "txn_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Transactions this issue is about. Empty list if none.",
                },
                "reported_loss_usd": {
                    "type": "number",
                    "description": (
                        "For unauthorized_charge: the total amount the customer says they lost. "
                        "0 if unknown or for any other reason."
                    ),
                },
            },
            "required": ["reason", "summary", "txn_ids", "reported_loss_usd"],
            "additionalProperties": False,
        },
    },
]


class ToolBox:
    def __init__(self, api: MockPaylaneAPI, session: Session, now=clock.now):
        self.api = api
        self.session = session
        self.now = now

    def run(self, name: str, args: dict) -> dict:
        handler = {
            "get_customer": self.get_customer,
            "get_transaction": self.get_transaction,
            "issue_refund": self.issue_refund,
            "escalate_to_human": self.escalate_to_human,
        }.get(name)
        if handler is None:
            return self._blocked(name, args, "unknown_tool", "There is no tool with that name.")
        return handler(**args)

    # ---- the four tools -------------------------------------------------------------

    def get_customer(self, email: str, card_last4: str) -> dict:
        args = {"email": email, "card_last4": card_last4}
        s = self.session
        if s.account_hold == "verification_failed":
            return self._blocked("get_customer", args, "chat_locked",
                                 "Identity checks are locked after 3 failures and a person has the chat. Don't try again.")
        if s.verified:
            if email.strip().lower() == s.verified_email:
                return self._record("get_customer", args, {"verified": True, "customer": dict(s.customer)})
            return self._blocked("get_customer", args, "one_customer_per_chat",
                                 "This chat is already verified for one customer. You can't switch to another account.")
        digits = card_last4.strip()
        if not re.fullmatch(r"\d{4}", digits):
            # Not counted as a failed check: just ask again for the last 4 digits only.
            return self._record("get_customer", args,
                                {"verified": False, "note": "card_last4 must be exactly 4 digits."})

        record = self.api.get_customer(email)
        if "error" not in record and record["card_last4"] == digits:
            s.customer = {key: record[key] for key in ("id", "name", "card_last4", "status")}
            s.verified_email = email.strip().lower()
            # The API always says verified: false. Only this comparison, in trusted code, can turn it on.
            return self._record("get_customer", args, {"verified": True, "customer": dict(s.customer)})

        s.failed_checks += 1
        left = MAX_FAILED_CHECKS - s.failed_checks
        if left > 0:
            # Same answer whether or not the email exists, so nobody can use the chat to probe for accounts.
            return self._record("get_customer", args, {
                "verified": False,
                "attempts_left": left,
                "note": "The details don't match. Don't say which part was wrong or whether the email has an account.",
            })
        s.account_hold = "verification_failed"
        ticket = self._open_ticket(
            reason="verification_failed",
            customer_id=None if "error" in record else record["id"],
            priority="normal",
            txn_ids=[],
            body=(f"Chat locked after {MAX_FAILED_CHECKS} failed identity checks. Possible account takeover "
                  f"attempt. Last email tried: {email.strip()}."),
        )
        s.hold_ticket = ticket["ticket_id"]
        return self._record("get_customer", args, {
            "verified": False,
            "locked": True,
            "ticket_id": ticket["ticket_id"],
            "note": "3 failed checks: the chat is locked and handed to a person. Discuss no account details.",
        })

    def get_transaction(self, txn_id: str) -> dict:
        args = {"txn_id": txn_id}
        s = self.session
        if not s.verified:
            return self._blocked("get_transaction", args, "not_verified",
                                 "Check the customer's identity before looking up transactions.")
        txn_id = txn_id.strip()
        txn = self.api.get_transaction(s.customer_id, txn_id)
        if "error" in txn:
            return self._record("get_transaction", args,
                                {"found": False, "note": "No transaction with that ID on this customer's account."})
        result = {"found": True, "txn_id": txn_id, **txn, "refund_check": self._refund_check(txn_id, txn)}
        return self._record("get_transaction", args, result)

    def issue_refund(self, txn_id: str, amount: float) -> dict:
        args = {"txn_id": txn_id, "amount": amount}
        s = self.session
        if not s.verified:
            return self._blocked("issue_refund", args, "not_verified", "No refunds before the identity check passes.")
        if s.account_hold:
            return self._blocked("issue_refund", args, "chat_handed_off",
                                 "This chat is with a person now. Take no further actions.")
        txn_id = txn_id.strip()
        if txn_id in s.held_txns:
            return self._blocked("issue_refund", args, "issue_handed_off", "This transaction is with a person now.")

        # Re-read the transaction from the source of truth; never trust what the model remembers.
        txn = self.api.get_transaction(s.customer_id, txn_id)
        if "error" in txn:
            return self._blocked("issue_refund", args, "not_on_account",
                                 "That transaction isn't on this customer's account.")
        check = policy.check_refund(txn, kind=data.transaction_kind(txn_id), card_status=s.customer["status"],
                                    now=self.now())
        if check.decision != "refund":
            return self._blocked("issue_refund", args, check.reason, check.note)
        if policy.money(amount) != policy.money(txn["amount"]):
            return self._blocked("issue_refund", args, "partial_refund",
                                 "Refunds are for the full transaction amount only.")

        amount_text = f"{txn_id} (${policy.money(txn['amount'])})"
        try:
            result = self.api.issue_refund(txn_id, txn["amount"])
        except RefundTimeout:
            # Calling again could pay out twice, so read the transaction back instead. Seeing "refunded"
            # confirms it; not seeing it proves nothing, so that case goes to a person to reconcile.
            after = self.api.get_transaction(s.customer_id, txn_id)
            if after.get("status") == "refunded":
                s.refunded_txns[txn_id] = None
                return self._record("issue_refund", args, {
                    "ok": True, "refund_id": None,
                    "note": "The call timed out, but reading the transaction back shows it refunded. "
                            "No refund ID came back."})
            ticket = self._hand_off_refund(txn_id, (
                f"Transactions: {amount_text}\nREFUND OUTCOME UNKNOWN: issue_refund timed out and the transaction "
                "does not show as refunded yet. Money may or may not have moved. Not retried. "
                "Reconcile before any further refund attempt."))
            return self._record("issue_refund", args, {
                "ok": None, "outcome": "unknown", "ticket_id": ticket,
                "note": "Unknown result: the refund may or may not have gone through. Don't retry, and don't say it "
                        "worked or that it failed. Tell the customer you couldn't confirm it, that a person will "
                        "check, and give the ticket ID."})

        if result.get("ok"):
            s.refunded_txns[txn_id] = result["refund_id"]
            return self._record("issue_refund", args, result)
        ticket = self._hand_off_refund(txn_id, (
            f"Transactions: {amount_text}\nREFUND FAILED: issue_refund returned {result.get('reason', 'no reason')}. "
            "Not retried."))
        return self._record("issue_refund", args, {
            **result, "ticket_id": ticket,
            "note": "The refund could not be completed. Tell the customer that, give the ticket ID, and don't retry."})

    def _hand_off_refund(self, txn_id: str, body: str) -> str:
        """Record a failed or uncertain refund for a person, and hold the transaction so nothing retries it."""
        ticket = self._open_ticket("refund_failed_or_missing", self.session.customer_id, "normal", [txn_id], body)
        self.session.held_txns[txn_id] = ticket["ticket_id"]
        return ticket["ticket_id"]

    def escalate_to_human(self, reason: str, summary: str, txn_ids: list, reported_loss_usd: float) -> dict:
        args = {"reason": reason, "summary": summary, "txn_ids": txn_ids, "reported_loss_usd": reported_loss_usd}
        s = self.session
        if reason not in ESCALATION_REASONS:
            return self._blocked("escalate_to_human", args, "unknown_reason", "Use one of the listed reasons.")
        txn_ids = sorted({t.strip() for t in txn_ids if t.strip()})

        for ticket in s.tickets:  # the same issue twice gets the same ticket, not a duplicate
            if ticket["reason"] == reason and ticket["txn_ids"] == txn_ids:
                return self._record("escalate_to_human", args, {
                    "ticket_id": ticket["ticket_id"], "priority": ticket["priority"],
                    "note": "Already handed off; no new ticket."})

        amounts = {}
        if s.verified:
            for txn_id in txn_ids:
                txn = self.api.get_transaction(s.customer_id, txn_id)
                if "error" not in txn:
                    amounts[txn_id] = policy.money(txn["amount"])

        priority, extra = "normal", []
        if reason == "unauthorized_charge":
            # High priority goes by the total reported loss: the customer's figure or the charges named, whichever is larger.
            loss = max(sum(amounts.values(), Decimal("0.00")), policy.money(reported_loss_usd or 0))
            priority = policy.fraud_priority(loss)
            extra.append(f"Reported loss: ${loss}")
        txn_text = ", ".join(f"{t} (${amounts[t]})" if t in amounts else t for t in txn_ids) or "none given"
        if s.refunded_txns:
            # Facts from the system, so the note can't misstate what already happened in the chat.
            done = ", ".join(f"{t} ({ref or 'confirmed after timeout'})" for t, ref in s.refunded_txns.items())
            extra.append(f"Refunds already issued in this chat: {done}")
        body = "\n".join([f"Transactions: {txn_text}", *extra, f"Assistant's note: {summary}"])

        ticket = self._open_ticket(reason, s.customer_id, priority, txn_ids, body)
        if reason in CHAT_WIDE_REASONS or (reason == "unauthorized_charge" and not txn_ids):
            # Fraud with no transactions named can't be scoped, so it pauses everything.
            if not s.account_hold:
                s.account_hold, s.hold_ticket = reason, ticket["ticket_id"]
        for txn_id in txn_ids:
            s.held_txns.setdefault(txn_id, ticket["ticket_id"])
        return self._record("escalate_to_human", args, {
            "ticket_id": ticket["ticket_id"],
            "priority": priority,
            "note": "Handed off. Give the customer the ticket ID. Don't promise a time or an outcome.",
        })

    # ---- helpers ------------------------------------------------------------------------

    def _refund_check(self, txn_id: str, txn: dict) -> dict:
        s = self.session
        ticket = s.held_txns.get(txn_id) or (s.hold_ticket if s.account_hold else None)
        if ticket:
            return {"decision": "handed_off", "reason": "handed_off",
                    "note": f"Already with a person (ticket {ticket}). Take no further action on it."}
        return policy.check_refund(txn, kind=data.transaction_kind(txn_id), card_status=s.customer["status"],
                                   now=self.now()).as_dict()

    def _open_ticket(self, reason, customer_id, priority, txn_ids, body) -> dict:
        s = self.session
        check = f"passed ({s.customer_id})" if s.verified else "not passed"
        text = f"Priority: {priority.upper()} | Reason: {reason} | Identity check: {check}\n{body}"
        text, _ = redact(text, emails=False)  # tickets are internal, but card numbers never belong in them
        result = self.api.escalate_to_human(customer_id, text)
        ticket = {"ticket_id": result["ticket_id"], "reason": reason, "priority": priority,
                  "txn_ids": txn_ids, "customer_id": customer_id, "summary": text}
        s.tickets.append(ticket)
        return ticket

    def _record(self, tool, args, result, blocked=None) -> dict:
        self.session.events.append({"tool": tool, "input": args, "result": result, "blocked": blocked})
        return result

    def _blocked(self, tool, args, reason, note) -> dict:
        return self._record(tool, args, {"ok": False, "blocked": reason, "note": note}, blocked=reason)
