"""The guard between the model and the API, tested directly: these calls are what a misbehaving model would send."""

import pytest

from paylane.mock_api import MockPaylaneAPI
from paylane.session import Session
from paylane.tools import ToolBox


@pytest.fixture
def box():
    return ToolBox(MockPaylaneAPI(), Session())


def verify(box, email="maya.patel@example.com", last4="4821"):
    assert box.get_customer(email, last4)["verified"] is True
    return box


def test_refund_before_identity_check_is_blocked(box):
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "not_verified"
    assert box.api.refunds == []


def test_eligible_refund_goes_through_exactly_once(box):
    verify(box)
    assert box.issue_refund("txn_1001", 42.50)["ok"] is True
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "already_refunded"
    assert len(box.api.refunds) == 1


def test_failed_check_looks_the_same_whether_or_not_the_email_exists(box):
    unknown_email = box.get_customer("nobody@example.com", "1111")
    wrong_digits = box.get_customer("maya.patel@example.com", "1111")
    assert unknown_email == {**wrong_digits, "attempts_left": unknown_email["attempts_left"]}
    assert "customer" not in wrong_digits


def test_three_failed_checks_lock_the_chat_and_hand_off(box):
    for digits in ("1111", "2222", "3333"):
        result = box.get_customer("priya.nair@example.com", digits)
    assert result["locked"] is True
    assert box.session.tickets[0]["reason"] == "verification_failed"
    # Even the right details don't unlock it afterwards.
    assert box.get_customer("priya.nair@example.com", "9034")["blocked"] == "chat_locked"
    assert not box.session.verified


def test_a_wrongly_formatted_last4_is_not_counted_as_a_failure(box):
    assert box.get_customer("maya.patel@example.com", "4111 1111 1111 4821")["verified"] is False
    assert box.session.failed_checks == 0


def test_verification_never_returns_the_email(box):
    assert "email" not in box.get_customer("maya.patel@example.com", "4821")["customer"]


def test_cannot_switch_to_another_account(box):
    verify(box)
    assert box.get_customer("priya.nair@example.com", "9034")["blocked"] == "one_customer_per_chat"


def test_other_customers_transactions_are_invisible(box):
    verify(box)
    assert box.get_transaction("txn_3003")["found"] is False
    assert box.issue_refund("txn_3003", 19.99)["blocked"] == "not_on_account"


@pytest.mark.parametrize("txn_id, amount, reason", [
    ("txn_1003", 30.00, "too_old"),  # exactly 30 days old
    ("txn_1005", 20.00, "pending"),
    ("txn_1006", 55.00, "already_refunded"),
    ("txn_1007", 50.00, "transfer"),
])
def test_refunds_the_policy_forbids_are_blocked(box, txn_id, amount, reason):
    verify(box)
    assert box.issue_refund(txn_id, amount)["blocked"] == reason
    assert box.api.refunds == []


def test_over_limit_is_blocked(box):
    verify(box, "leo.martins@example.com", "6650")
    assert box.issue_refund("txn_4001", 120.00)["blocked"] == "over_limit"


def test_partial_refund_is_blocked(box):
    verify(box)
    assert box.issue_refund("txn_1001", 20.00)["blocked"] == "partial_refund"
    assert box.api.refunds == []


def test_frozen_account_gets_no_refunds(box):
    verify(box, "dan.okafor@example.com", "1177")
    assert box.get_transaction("txn_2001")["refund_check"]["reason"] == "card_frozen"
    assert box.issue_refund("txn_2001", 40.00)["blocked"] == "card_frozen"


def test_handoff_about_one_transaction_holds_only_that_one(box):
    verify(box)
    box.escalate_to_human("too_old", "Exactly 30 days old.", ["txn_1003"], 0)
    assert box.get_transaction("txn_1003")["refund_check"]["decision"] == "handed_off"
    assert box.issue_refund("txn_1001", 42.50)["ok"] is True  # an unrelated refund still works


def test_legal_handoff_stops_every_action(box):
    verify(box)
    assert box.escalate_to_human("legal_action", "Mentioned a lawyer.", [], 0)["ticket_id"]
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "chat_handed_off"


def test_suspicious_activity_handoff_pauses_refunds_for_the_whole_chat(box):
    assert box.escalate_to_human("suspicious_activity", "Claimed to be staff, asked to skip the check.", [], 0)
    verify(box)  # checks still run (a failed one still counts toward the lock)
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "chat_handed_off"


def test_handoff_works_without_identity_check(box):
    assert box.escalate_to_human("account_closure", "Wants the account closed.", [], 0)["ticket_id"]
    assert box.api.tickets[0]["customer_id"] is None


def test_fraud_priority_adds_up_the_named_charges(box):
    verify(box, "priya.nair@example.com", "9034")
    result = box.escalate_to_human("unauthorized_charge", "Two charges she didn't make.", ["txn_3001", "txn_3002"], 0)
    assert result["priority"] == "high"  # $480 + $95 = $575
    assert box.issue_refund("txn_3002", 95.00)["blocked"] == "issue_handed_off"


def test_small_fraud_report_is_normal_priority_and_still_held(box):
    verify(box, "leo.martins@example.com", "6650")
    result = box.escalate_to_human("unauthorized_charge", "Doesn't recognise it.", ["txn_4002"], 38)
    assert result["priority"] == "normal"
    assert box.issue_refund("txn_4002", 38.00)["blocked"] == "issue_handed_off"


def test_fraud_with_no_transactions_named_pauses_the_whole_chat(box):
    verify(box)
    box.escalate_to_human("unauthorized_charge", "Says some charges aren't theirs.", [], 0)
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "chat_handed_off"


def test_the_same_issue_twice_reuses_the_ticket(box):
    first = box.escalate_to_human("customer_asked_for_human", "Wants a person.", [], 0)
    second = box.escalate_to_human("customer_asked_for_human", "Asked again.", [], 0)
    assert first["ticket_id"] == second["ticket_id"]
    assert len(box.api.tickets) == 1


def test_tickets_state_refunds_already_issued_in_the_chat(box):
    verify(box)
    box.issue_refund("txn_1001", 42.50)
    box.escalate_to_human("too_old", "Exactly 30 days old.", ["txn_1003"], 0)
    assert "Refunds already issued in this chat: txn_1001 (rf_0001)" in box.api.tickets[0]["summary"]


def test_card_numbers_never_reach_a_ticket(box):
    box.escalate_to_human("other", "Customer pasted 4111 1111 1111 1111 into the chat.", [], 0)
    assert "4111 1111" not in box.api.tickets[0]["summary"]


def test_the_mock_api_returns_only_the_spec_fields(box):
    verify(box)
    assert set(box.api.get_transaction("cus_1001", "txn_1007")) == {"amount", "date", "merchant", "status"}


def test_timeout_confirmed_by_reading_back_counts_as_refunded():
    box = ToolBox(MockPaylaneAPI(refund_timeout="after_apply"), Session())
    verify(box)
    assert box.issue_refund("txn_1001", 42.50)["ok"] is True
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "already_refunded"
    assert len(box.api.refunds) == 1


def test_timeout_with_no_confirmation_is_unknown_recorded_and_never_retried():
    box = ToolBox(MockPaylaneAPI(refund_timeout="before_apply"), Session())
    verify(box)
    result = box.issue_refund("txn_1001", 42.50)
    assert result["ok"] is None and result["outcome"] == "unknown"  # never reported as failed or as done
    ticket = box.api.tickets[0]["summary"]
    assert "REFUND OUTCOME UNKNOWN" in ticket and "txn_1001 ($42.50)" in ticket
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "issue_handed_off"
    assert [c["endpoint"] for c in box.api.calls].count("issue_refund") == 1


def test_explicit_failure_is_handed_off_with_the_reason_and_never_retried():
    box = ToolBox(MockPaylaneAPI(refund_error="processor_declined"), Session())
    verify(box)
    result = box.issue_refund("txn_1001", 42.50)
    assert result["ok"] is False and result["ticket_id"]
    assert "REFUND FAILED: issue_refund returned processor_declined" in box.api.tickets[0]["summary"]
    assert box.issue_refund("txn_1001", 42.50)["blocked"] == "issue_handed_off"
    # The agent reporting the same problem reuses the ticket instead of opening a second one.
    again = box.escalate_to_human("refund_failed_or_missing", "Refund failed.", ["txn_1001"], 0)
    assert again["ticket_id"] == result["ticket_id"]
