"""The chat loop. Claude decides what to say and which tool to call; the ToolBox decides what actually happens."""

import json
import os
from dataclasses import dataclass

import anthropic

from .prompt import SYSTEM_PROMPT
from .redact import redact
from .tools import TOOLS, ToolBox

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
MAX_TOOL_ROUNDS = 8
FALLBACK_BETA = "server-side-fallback-2026-07-01"
REFUSAL_REPLY = "Sorry, I can't help with that in this chat. I can pass it to our support team if you'd like."
STUCK_REPLY = "Sorry, I couldn't finish that. Could you say it again?"


@dataclass
class Turn:
    customer: str
    reply: str  # what the customer sees, after redaction
    raw_reply: str  # what the model wrote; the evals read this one
    hidden: list  # what redaction removed, if anything
    tools: list  # this turn's tool calls, with the guard's verdict
    model_calls: list  # one entry per API call: model, stop reason, token usage


class SupportAgent:
    def __init__(self, toolbox: ToolBox, client=None, model=None, effort=None, fallbacks=True):
        self.toolbox = toolbox
        self.client = client or anthropic.Anthropic(max_retries=4, timeout=180)
        self.model = model or os.environ.get("PAYLANE_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("PAYLANE_EFFORT", DEFAULT_EFFORT)
        self.fallbacks = fallbacks
        # Append-only: earlier turns are never edited, so thinking blocks and the prompt cache stay valid.
        self.messages = []

    def reply(self, customer_text: str) -> Turn:
        self.messages.append({"role": "user", "content": customer_text})
        first_event = len(self.toolbox.session.events)
        texts, calls = [], []
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._call()
            calls.append(_call_record(response))
            if response.stop_reason == "refusal":
                texts.append(REFUSAL_REPLY)
                break
            self.messages.append({"role": "assistant", "content": response.content})
            texts += [block.text for block in response.content if block.type == "text" and block.text.strip()]
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                break
            results = []
            for block in tool_uses:
                output = self.toolbox.run(block.name, dict(block.input))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output)})
            self.messages.append({"role": "user", "content": results})
        raw = "\n\n".join(text.strip() for text in texts).strip() or STUCK_REPLY
        clean, hidden = redact(raw)
        return Turn(customer_text, clean, raw, hidden, self.toolbox.session.events[first_event:], calls)

    def _call(self):
        # fallbacks="default": if a safety classifier declines, the API re-runs the request on its recommended model.
        extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if self.fallbacks else {}
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=self.messages,
            output_config={"effort": self.effort},
            **extra,
        )


def _call_record(response) -> dict:
    usage = response.usage
    return {
        "model": response.model,
        "stop_reason": response.stop_reason,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }
