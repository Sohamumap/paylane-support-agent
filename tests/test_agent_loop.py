"""The chat loop with a fake model that plays back scripted responses. No API key needed."""

from types import SimpleNamespace

import anthropic

import paylane.agent as agent_module
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
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


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


def test_tool_planning_text_is_auditable_but_only_the_final_reply_is_shown():
    client = FakeClient(
        response(text("Check straight away."),
                 tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(text("Thanks, you're verified. Which transaction can I check?")),
    )
    turn = make_agent(client).reply("maya.patel@example.com, 4821")
    assert turn.reply == "Thanks, you're verified. Which transaction can I check?"
    assert turn.raw_reply == turn.reply
    assert turn.intermediate_replies == ["Check straight away."]


def test_last_allowed_tool_round_reports_a_completed_refund_and_closes_history(monkeypatch):
    monkeypatch.setattr(agent_module, "MAX_TOOL_ROUNDS", 2)
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        response(text("Your refund was already confirmed.")),
    )
    agent = make_agent(client)
    turn = agent.reply("Refund txn_1001, maya.patel@example.com, 4821")
    assert "refund is confirmed for txn_1001" in turn.reply
    assert "say it again" not in turn.reply
    assert len(agent.toolbox.api.refunds) == 1 and len(client.requests) == 2
    # Every issued tool call has a result, and the recovery message is in the conversation.
    result_ids = {item["tool_use_id"] for msg in agent.messages if msg["role"] == "user"
                  and isinstance(msg["content"], list) for item in msg["content"]}
    assert result_ids == {"t1", "t2"}
    assert agent.messages[-1]["role"] == "assistant"
    assert agent.messages[-1]["content"][0]["text"] == turn.raw_reply
    agent.reply("What happened?")
    assert len(agent.toolbox.api.refunds) == 1


def test_refusal_after_refund_preserves_confirmed_outcome_in_reply_and_history():
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        response(stop="refusal"),
    )
    agent = make_agent(client)
    turn = agent.reply("Refund txn_1001, maya.patel@example.com, 4821")
    assert "refund is confirmed for txn_1001" in turn.reply
    assert agent.messages[-1]["content"][0]["text"] == turn.raw_reply


def test_provider_error_after_refund_reports_the_success_without_retrying_payment():
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
        anthropic.APIConnectionError(request=SimpleNamespace(method="POST", url="https://example.invalid")),
    )
    agent = make_agent(client)
    turn = agent.reply("Refund txn_1001, maya.patel@example.com, 4821")
    assert "refund is confirmed for txn_1001" in turn.reply
    assert turn.model_calls[-1]["stop_reason"] == "api_error"
    assert len(agent.toolbox.api.refunds) == 1
    assert [call["endpoint"] for call in agent.toolbox.api.calls].count("issue_refund") == 1


def test_budget_fallback_preserves_uncertain_outcome_and_ticket(monkeypatch):
    monkeypatch.setattr(agent_module, "MAX_TOOL_ROUNDS", 2)
    client = FakeClient(
        response(tool("t1", "get_customer", email="maya.patel@example.com", card_last4="4821"), stop="tool_use"),
        response(tool("t2", "issue_refund", txn_id="txn_1001", amount=42.5), stop="tool_use"),
    )
    agent = SupportAgent(ToolBox(MockPaylaneAPI(refund_timeout="before_apply"), Session()), client=client)
    turn = agent.reply("Refund txn_1001, maya.patel@example.com, 4821")
    assert "couldn't confirm whether the refund went through for txn_1001" in turn.reply
    assert "TCK-0001" in turn.reply and "person will review" in turn.reply
    assert "refund is confirmed" not in turn.reply and "couldn't be completed" not in turn.reply


def test_truncated_success_claim_is_not_shown_as_a_final_reply():
    agent = make_agent(FakeClient(response(text("I've refunded your charge"), stop="max_tokens")))
    turn = agent.reply("hi")
    assert "refunded" not in turn.reply
    assert turn.intermediate_replies == ["I've refunded your charge"]
