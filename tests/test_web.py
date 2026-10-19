"""The chat page's server, driven over real HTTP with the scripted fake model. No API key needed."""

import http.client
import json
import threading
from types import SimpleNamespace
import urllib.parse
import urllib.request

import anthropic
import pytest

from paylane.mock_api import MockPaylaneAPI
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


def raw_post(server, payload=b"", content_length=None):
    """Send a request without urllib repairing its headers or encoding its body."""
    url = urllib.parse.urlsplit(server)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=2)
    try:
        conn.putrequest("POST", "/api/new")
        if content_length is not None:
            conn.putheader("Content-Length", content_length)
        conn.endheaders(payload)
        res = conn.getresponse()
        return res.status, json.loads(res.read())
    finally:
        conn.close()


@pytest.mark.parametrize("payload", [b"null", b"[]", b'"hello"', b"1", b"true"])
def test_json_body_must_be_an_object(server, payload):
    status, result = raw_post(server, payload, str(len(payload)))
    assert status == 400
    assert result["error"] == "Body must be a JSON object."


@pytest.mark.parametrize("length", ["invalid", "-1"])
def test_invalid_content_length_returns_an_error_without_waiting_for_a_body(server, length):
    status, result = raw_post(server, content_length=length)
    assert status == 400
    assert "Content-Length" in result["error"]


def test_invalid_utf8_returns_a_json_error(server):
    status, result = raw_post(server, b"\xff", "1")
    assert status == 400
    assert result["error"] == "Body must be JSON."


def test_empty_body_without_content_length_still_starts_a_chat(server):
    status, result = raw_post(server)
    assert status == 200
    assert result["chat_id"]
    assert result["state"]["customer"] is None


def test_provider_error_details_are_not_returned_to_the_browser(server, monkeypatch):
    def fail(self, message):
        raise anthropic.APIError("private-provider-detail", request=SimpleNamespace(url="https://example.com"),
                                 body={"private": "provider-payload"})

    monkeypatch.setattr("paylane.web.SupportAgent.reply", fail)
    chat_id = post(server + "/api/new", {})["chat_id"]
    with pytest.raises(urllib.error.HTTPError) as err:
        post(server + "/api/send", {"chat_id": chat_id, "message": "hello"})
    assert err.value.code == 502
    result = json.loads(err.value.read())
    assert result == {"error": "The model service is unavailable. No reply was returned."}


def test_refund_timeout_remains_unknown_in_the_http_response(monkeypatch):
    monkeypatch.setattr("paylane.web.MockPaylaneAPI", lambda: MockPaylaneAPI(refund_timeout="before_apply"))
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        response(text("I couldn't confirm whether the refund went through. A person will check under TCK-0001.")),
    )
    srv = make_server(port=0, store=ChatStore(client=client, model="fake-model", effort="low"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}"
        chat_id = post(url + "/api/new", {})["chat_id"]
        result = post(url + "/api/send", {"chat_id": chat_id, "message": "Refund txn_1001 please."})
        refund_result = result["tools"][-1]["result"]
        assert refund_result["ok"] is None and refund_result["outcome"] == "unknown"
        assert result["state"]["refunds"] == []
        assert "REFUND OUTCOME UNKNOWN" in result["state"]["tickets"][0]["summary"]
    finally:
        srv.shutdown()
        srv.server_close()
