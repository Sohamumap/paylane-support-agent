"""Mock Paylane records. Each conversation gets a fresh copy, so runs never affect each other.

Ages are measured against the fixed clock in clock.py (2026-10-16 12:00 UTC).
"type" is an addition to the spec: "card" for a purchase at a merchant, "transfer" for money sent to a person.
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
     "merchant": "Bluebird Coffee Roasters", "status": "settled", "type": "card"},
    {"id": "txn_1002", "customer_id": "cus_1001", "amount": 75.00, "date": "2026-09-16T12:00:01Z",
     "merchant": "Northwind Books", "status": "settled", "type": "card"},  # 29 days 23:59:59 old
    {"id": "txn_1003", "customer_id": "cus_1001", "amount": 30.00, "date": "2026-09-16T12:00:00Z",
     "merchant": "CityRide", "status": "settled", "type": "card"},  # exactly 30 days old
    {"id": "txn_1004", "customer_id": "cus_1001", "amount": 18.99, "date": "2026-10-04T18:30:00Z",
     "merchant": "StreamBox", "status": "settled", "type": "card"},
    {"id": "txn_1005", "customer_id": "cus_1001", "amount": 20.00, "date": "2026-10-15T20:10:00Z",
     "merchant": "FreshCart Grocery", "status": "pending", "type": "card"},
    {"id": "txn_1006", "customer_id": "cus_1001", "amount": 55.00, "date": "2026-10-01T10:00:00Z",
     "merchant": "Lumen Electronics", "status": "refunded", "type": "card"},
    {"id": "txn_1007", "customer_id": "cus_1001", "amount": 50.00, "date": "2026-10-12T16:45:00Z",
     "merchant": "Transfer to Sam Lee", "status": "settled", "type": "transfer"},
    # Daniel: card is frozen
    {"id": "txn_2001", "customer_id": "cus_1002", "amount": 40.00, "date": "2026-10-13T11:00:00Z",
     "merchant": "Metro Pharmacy", "status": "settled", "type": "card"},
    # Priya: two charges she says she didn't make, plus an ordinary one
    {"id": "txn_3001", "customer_id": "cus_1003", "amount": 480.00, "date": "2026-10-14T02:13:00Z",
     "merchant": "Volt Electronics", "status": "settled", "type": "card"},
    {"id": "txn_3002", "customer_id": "cus_1003", "amount": 95.00, "date": "2026-10-14T02:19:00Z",
     "merchant": "GiftCardHub", "status": "settled", "type": "card"},
    {"id": "txn_3003", "customer_id": "cus_1003", "amount": 19.99, "date": "2026-10-15T08:00:00Z",
     "merchant": "Spotless Laundry", "status": "settled", "type": "card"},
    # Leo: over the limit, and a small charge he doesn't recognise
    {"id": "txn_4001", "customer_id": "cus_1004", "amount": 120.00, "date": "2026-10-12T13:00:00Z",
     "merchant": "Gadget Garage", "status": "settled", "type": "card"},
    {"id": "txn_4002", "customer_id": "cus_1004", "amount": 38.00, "date": "2026-10-13T22:40:00Z",
     "merchant": "QPY*MERCH 8812", "status": "settled", "type": "card"},
]
