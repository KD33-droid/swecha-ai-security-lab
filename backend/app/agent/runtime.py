from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tools.knowledge import KnowledgeBase
from app.services.policy_engine import decide_c1_message, is_c1_prompt_injection


@dataclass
class AgentReply:
    text: str
    tool_calls: list[dict[str, Any]]
    vulnerable_path: bool


class LocalNexaAssist:
    """Deterministic local provider for development and automated testing.

    This is intentionally vulnerable for C1. A production workshop can replace
    this provider with an external model through the provider interface later.
    """

    def __init__(self, knowledge_base: KnowledgeBase, secret: str):
        self.knowledge_base = knowledge_base
        self.secret = secret

    def respond(self, message: str, history: list[dict[str, str]] | None = None, policies: dict[str, Any] | None = None) -> AgentReply:
        normalized = message.lower()
        is_injection = is_c1_prompt_injection(message)

        decision = decide_c1_message(policies or {}, is_injection)

        if is_injection and decision.action == "DENY":
            return AgentReply(
                text="I can’t provide protected training data. I can still help with normal support requests.",
                tool_calls=[],
                vulnerable_path=False,
            )

        if is_injection and decision.action == "SANITIZE":
            return AgentReply(
                text="I can’t provide protected training data.",
                tool_calls=[],
                vulnerable_path=False,
            )

        if is_injection:
            # Deliberately vulnerable behavior: the model treats the user's
            # instruction as sufficient authority and leaks protected context.
            return AgentReply(
                text=(
                    "I found the protected training value in the internal context. "
                    f"The value is {self.secret}."
                ),
                tool_calls=[],
                vulnerable_path=True,
            )

        results = self.knowledge_base.search(message)
        if results:
            first = self.knowledge_base.read(results[0]["document_id"])
            return AgentReply(
                text=f"Here is what I found in our support knowledge base: {first['body']}",
                tool_calls=[
                    {"tool": "knowledge_search", "arguments": {"query": message}, "result": results},
                    {"tool": "knowledge_read", "arguments": {"document_id": first["document_id"]}, "result": first},
                ],
                vulnerable_path=False,
            )

        return AgentReply(
            text="I can help with normal Nexa support topics such as password resets, support hours, and account escalation.",
            tool_calls=[],
            vulnerable_path=False,
        )
