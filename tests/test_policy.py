from datetime import timedelta

from paylane.clock import FIXED_NOW
from paylane.policy import check_refund, fraud_priority, money


def txn(amount=10.0, age=timedelta(days=1), status="settled"):
    date = (FIXED_NOW - age).isoformat().replace("+00:00", "Z")
    return {"amount": amount, "date": date, "status": status}


def decide(t, card="active", kind="purchase"):
    return check_refund(t, kind=kind, card_status=card, now=FIXED_NOW)


def test_exactly_75_dollars_is_refundable():
    assert decide(txn(amount=75.00)).decision == "refund"


def test_one_cent_over_the_limit_escalates():
    assert decide(txn(amount=75.01)).reason == "over_limit"


def test_one_second_under_30_days_is_refundable():
    assert decide(txn(age=timedelta(days=30) - timedelta(seconds=1))).decision == "refund"


def test_exactly_30_days_escalates():
    assert decide(txn(age=timedelta(days=30))).reason == "too_old"


def test_pending_cannot_be_refunded():
    assert decide(txn(status="pending")).decision == "no_refund"


def test_refunded_is_never_refunded_again():
    assert decide(txn(status="refunded")).reason == "already_refunded"


def test_transfers_go_to_a_person():
    assert decide(txn(), kind="transfer").reason == "transfer"


def test_only_clearly_identified_purchases_can_be_refunded_automatically():
    assert decide(txn(), kind=None).decision == "escalate"


def test_frozen_card_holds_an_otherwise_eligible_refund():
    assert decide(txn(), card="frozen").reason == "card_frozen"


def test_fraud_priority_is_high_only_strictly_over_500():
    assert fraud_priority(money(500)) == "normal"
    assert fraud_priority(money("500.01")) == "high"
