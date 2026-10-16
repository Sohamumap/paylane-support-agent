"""The chat page's server, driven over real HTTP with the scripted fake model. No API key needed."""

import json
import threading
import urllib.request

import pytest

from paylane.web import ChatStore, make_server
from test_agent_loop import FakeClient, response, text, tool


@pytest.fixture
def server():
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        response(text("Done: I've refunded **$42.50**. Reach me at maya.patel@example.com")),
    )
    srv = make_server(port=0, store=ChatStore(client=client, model="fake-model", effort="low"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def post(url, payload):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as res:
        return json.loads(res.read())


def test_page_and_test_data_are_served(server):
    with urllib.request.urlopen(server + "/") as res:
        assert b"Paylane Support" in res.read()
    with urllib.request.urlopen(server + "/api/info") as res:
        info = json.loads(res.read())
    by_id = {t["id"]: t for t in info["transactions"]}
    assert by_id["txn_1003"]["age"] == "exactly 30 days"
    assert by_id["txn_1003"]["policy"] == "escalate"


def test_a_chat_turn_returns_the_reply_tools_and_state(server):
    chat_id = post(server + "/api/new", {})["chat_id"]
    result = post(server + "/api/send", {"chat_id": chat_id, "message": "Refund txn_1001, maya.patel@example.com 4821"})
    assert "@" not in result["reply"] and result["hidden"] == ["email"]
    assert [e["tool"] for e in result["tools"]] == ["get_customer", "issue_refund"]
    assert result["state"]["customer"]["id"] == "cus_1001"
    assert result["state"]["refunds"][0]["txn_id"] == "txn_1001"


def test_unknown_chat_is_rejected(server):
    with pytest.raises(urllib.error.HTTPError) as err:
        post(server + "/api/send", {"chat_id": "nope", "message": "hi"})
    assert err.value.code == 404
