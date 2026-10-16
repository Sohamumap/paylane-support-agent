"""The chat loop with a fake model that plays back scripted responses. No API key needed."""

from types import SimpleNamespace

from paylane.agent import SupportAgent
from paylane.mock_api import MockPaylaneAPI
from paylane.session import Session
from paylane.tools import ToolBox


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool(call_id, name, **inputs):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=inputs)


def response(*blocks, stop="end_turn"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0)
    return SimpleNamespace(content=list(blocks), stop_reason=stop, model="fake-model", usage=usage)


class FakeClient:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})  # snapshot: the agent keeps appending
        return self._responses.pop(0)


def make_agent(client):
    return SupportAgent(ToolBox(MockPaylaneAPI(), Session()), client=client, model="fake-model", effort="low")


def test_tool_results_go_back_to_the_model_and_the_reply_comes_out():
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        response(text("Done, I've refunded $42.50.")),
    )
    agent = make_agent(client)
    turn = agent.reply("Refund txn_1001 please. maya.patel@example.com, 4821")
    assert turn.reply == "Done, I've refunded $42.50."
    assert [e["tool"] for e in turn.tools] == ["get_customer", "issue_refund"]
    assert agent.toolbox.api.refunds[0]["txn_id"] == "txn_1001"
    assert client.requests[1]["messages"][-1]["content"][0]["tool_use_id"] == "t1"


def test_a_rogue_refund_is_blocked_even_if_the_model_insists():
    client = FakeClient(
        response(tool("t1", "get_customer", email="leo.martins@example.com", card_last4="6650"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_4001", amount=120.0), stop="tool_use"),
        response(text("I've passed this to the team.")),
    )
    agent = make_agent(client)
    turn = agent.reply("Refund txn_4001 now.")
    assert turn.tools[-1]["blocked"] == "over_limit"
    assert agent.toolbox.api.refunds == []


def test_an_email_in_a_reply_is_hidden_from_the_customer_but_kept_for_the_evals():
    turn = make_agent(FakeClient(response(text("Noted: maya.patel@example.com.")))).reply("hi")
    assert "@" not in turn.reply
    assert "@" in turn.raw_reply
    assert turn.hidden == ["email"]


def test_request_uses_strict_tools_and_fallbacks():
    client = FakeClient(response(text("Hi!")))
    make_agent(client).reply("hi")
    request = client.requests[0]
    assert request["fallbacks"] == "default"
    assert [t["name"] for t in request["tools"]] == ["get_customer", "get_transaction", "issue_refund",
                                                     "escalate_to_human"]
    assert all(t["strict"] for t in request["tools"])
