"""A local web page for chatting with the agent.

    python -m paylane web      then open http://127.0.0.1:8765

Standard library only. It listens on 127.0.0.1, keeps each chat in memory with its own mock bank,
and shows what happened behind every reply: tool calls, the guard's verdicts, refunds and tickets.
"""

import json
import os
import threading
import uuid
from collections import OrderedDict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from . import clock, data, policy
from .agent import DEFAULT_EFFORT, DEFAULT_MODEL, SupportAgent
from .mock_api import MockPaylaneAPI
from .session import Session
from .tools import ToolBox

PAGE = Path(__file__).with_name("web.html")
MAX_CHATS = 50
MAX_MESSAGE_CHARS = 2000
MAX_BODY_BYTES = 64_000


class ChatStore:
    """Open chats, each with its own mock bank, session and agent. The oldest are dropped past MAX_CHATS."""

    def __init__(self, client=None, model=None, effort=None):
        self.client = client or anthropic.Anthropic(max_retries=4, timeout=180)
        self.model = model or os.environ.get("PAYLANE_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("PAYLANE_EFFORT", DEFAULT_EFFORT)
        self._chats = OrderedDict()
        self._lock = threading.Lock()

    def new(self) -> str:
        api, session = MockPaylaneAPI(), Session()
        agent = SupportAgent(ToolBox(api, session), client=self.client, model=self.model, effort=self.effort)
        chat_id = uuid.uuid4().hex
        with self._lock:
            self._chats[chat_id] = {"agent": agent, "api": api, "session": session, "lock": threading.Lock()}
            while len(self._chats) > MAX_CHATS:
                self._chats.popitem(last=False)
        return chat_id

    def get(self, chat_id):
        with self._lock:
            return self._chats.get(chat_id)


def chat_state(chat) -> dict:
    session, api = chat["session"], chat["api"]
    return {
        "customer": dict(session.customer) if session.customer else None,
        "failed_checks": session.failed_checks,
        "hold": session.account_hold,
        "hold_ticket": session.hold_ticket,
        "refunds": list(api.refunds),
        "tickets": [{key: t[key] for key in ("ticket_id", "reason", "priority", "txn_ids", "summary")}
                    for t in session.tickets],
    }


def _age(date: str) -> str:
    seconds = (clock.now() - clock.parse_utc(date)).total_seconds()
    days = seconds / 86400
    return f"exactly {int(days)} days" if seconds % 86400 == 0 else f"{int(days * 10) / 10:g} days"


def test_data() -> dict:
    """The mock customers and transactions, and what the policy says about each, for the page's cheat sheet."""
    card_status = {c["id"]: c["status"] for c in data.CUSTOMERS}
    transactions = []
    for t in data.TRANSACTIONS:
        check = policy.check_refund(t, kind=t.get("kind"), card_status=card_status[t["customer_id"]], now=clock.now())
        transactions.append({
            "id": t["id"], "customer_id": t["customer_id"], "amount": t["amount"], "merchant": t["merchant"],
            "status": t["status"], "kind": t.get("kind"), "age": _age(t["date"]),
            "policy": check.decision, "reason": check.reason,
        })
    customers = [{key: c[key] for key in ("id", "name", "email", "card_last4", "status")} for c in data.CUSTOMERS]
    return {"customers": customers, "transactions": transactions}


class Handler(BaseHTTPRequestHandler):
    server_version = "PaylaneDemo"

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/info":
            store = self.server.store
            return self._json(HTTPStatus.OK, {"model": store.model, "effort": store.effort, **test_data()})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self):
        body = self._read_json()
        if body is None:
            return None
        store = self.server.store
        if self.path == "/api/new":
            chat_id = store.new()
            return self._json(HTTPStatus.OK, {"chat_id": chat_id, "state": chat_state(store.get(chat_id))})
        if self.path == "/api/send":
            chat = store.get(str(body.get("chat_id", "")))
            message = str(body.get("message", "")).strip()
            if chat is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "This chat has expired. Start a new one."})
            if not message or len(message) > MAX_MESSAGE_CHARS:
                return self._json(HTTPStatus.BAD_REQUEST,
                                  {"error": f"Write a message of 1 to {MAX_MESSAGE_CHARS} characters."})
            with chat["lock"]:  # one reply at a time per chat; the conversation history is append-only
                try:
                    turn = chat["agent"].reply(message)
                except anthropic.APIError:
                    return self._json(HTTPStatus.BAD_GATEWAY,
                                      {"error": "The model service is unavailable. No reply was returned."})
            return self._json(HTTPStatus.OK, {"reply": turn.reply, "hidden": turn.hidden, "tools": turn.tools,
                                              "state": chat_state(chat)})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Content-Length must be a non-negative integer."})
            return None
        if length < 0:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Content-Length must be a non-negative integer."})
            return None
        if length > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Request too large."})
            return None
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Body must be JSON."})
            return None
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Body must be a JSON object."})
            return None
        return payload

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, default=str).encode("utf-8"), "application/json")

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def make_server(port=8765, store=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.store = store or ChatStore()
    return server


def serve(port=8765, model=None, effort=None):
    server = make_server(port, ChatStore(model=model, effort=effort))
    print(f"Paylane chat page: http://127.0.0.1:{server.server_port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
