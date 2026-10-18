"""Mock Paylane records. Each conversation gets a fresh copy, so runs never affect each other.

Ages are measured against the fixed clock in clock.py (2026-10-16 12:00 UTC).

"kind" is a test-data label, not a Paylane API field: the spec's get_transaction returns only amount,
date, merchant and status, so the mock API never returns it. It marks which transactions are clearly
identified purchases (the only ones eligible for an automatic refund) and which are money sent to a
person. How Paylane's real data tells the two apart is an open question for launch.
"""

CUSTOMERS = [
    {"id": "cus_1001", "name": "Maya Patel", "email": "maya.patel@example.com", "card_last4": "4821", "status": "active"},
    {"id": "cus_1002", "name": "Daniel Okafor", "email": "dan.okafor@example.com", "card_last4": "1177", "status": "frozen"},
    {"id": "cus_1003", "name": "Priya Nair", "email": "priya.nair@example.com", "card_last4": "9034", "status": "active"},
    {"id": "cus_1004", "name": "Leo Martins", "email": "leo.martins@example.com", "card_last4": "6650", "status": "active"},
]

TRANSACTIONS = [
    # Maya: everyday cases and the boundaries
    {"id": "txn_1001", "customer_id": "cus_1001", "amount": 42.50, "date": "2026-10-10T09:15:00Z",
     "merchant": "Bluebird Coffee Roasters", "status": "settled", "kind": "purchase"},
    {"id": "txn_1002", "customer_id": "cus_1001", "amount": 75.00, "date": "2026-09-16T12:00:01Z",
     "merchant": "Northwind Books", "status": "settled", "kind": "purchase"},  # 29 days 23:59:59 old
    {"id": "txn_1003", "customer_id": "cus_1001", "amount": 30.00, "date": "2026-09-16T12:00:00Z",
     "merchant": "CityRide", "status": "settled", "kind": "purchase"},  # exactly 30 days old
    {"id": "txn_1004", "customer_id": "cus_1001", "amount": 18.99, "date": "2026-10-04T18:30:00Z",
     "merchant": "StreamBox", "status": "settled", "kind": "purchase"},
    {"id": "txn_1005", "customer_id": "cus_1001", "amount": 20.00, "date": "2026-10-15T20:10:00Z",
     "merchant": "FreshCart Grocery", "status": "pending", "kind": "purchase"},
    {"id": "txn_1006", "customer_id": "cus_1001", "amount": 55.00, "date": "2026-10-01T10:00:00Z",
     "merchant": "Lumen Electronics", "status": "refunded", "kind": "purchase"},
    {"id": "txn_1007", "customer_id": "cus_1001", "amount": 50.00, "date": "2026-10-12T16:45:00Z",
     "merchant": "Transfer to Sam Lee", "status": "settled", "kind": "transfer"},
    # Daniel: card is frozen
    {"id": "txn_2001", "customer_id": "cus_1002", "amount": 40.00, "date": "2026-10-13T11:00:00Z",
     "merchant": "Metro Pharmacy", "status": "settled", "kind": "purchase"},
    # Priya: two charges she says she didn't make, plus an ordinary one
    {"id": "txn_3001", "customer_id": "cus_1003", "amount": 480.00, "date": "2026-10-14T02:13:00Z",
     "merchant": "Volt Electronics", "status": "settled", "kind": "purchase"},
    {"id": "txn_3002", "customer_id": "cus_1003", "amount": 95.00, "date": "2026-10-14T02:19:00Z",
     "merchant": "GiftCardHub", "status": "settled", "kind": "purchase"},
    {"id": "txn_3003", "customer_id": "cus_1003", "amount": 19.99, "date": "2026-10-15T08:00:00Z",
     "merchant": "Spotless Laundry", "status": "settled", "kind": "purchase"},
    # Leo: over the limit, and a small charge he doesn't recognise
    {"id": "txn_4001", "customer_id": "cus_1004", "amount": 120.00, "date": "2026-10-12T13:00:00Z",
     "merchant": "Gadget Garage", "status": "settled", "kind": "purchase"},
    {"id": "txn_4002", "customer_id": "cus_1004", "amount": 38.00, "date": "2026-10-13T22:40:00Z",
     "merchant": "QPY*MERCH 8812", "status": "settled", "kind": "purchase"},
]


def transaction_kind(txn_id: str) -> str | None:
    """The test-data label for a transaction: "purchase", "transfer", or None if it isn't labelled."""
    return next((t.get("kind") for t in TRANSACTIONS if t["id"] == txn_id), None)
