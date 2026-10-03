from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Agent A: Within-session short-term memory only. No persistent User.md."""

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        # Live path if model configured, else offline deterministic path
        if self.langchain_agent and not self.force_offline:
            try:
                # ponytail: live LangChain chat invocation; falls back to offline on any failure
                if thread_id not in self.sessions:
                    self.sessions[thread_id] = SessionState()
                session = self.sessions[thread_id]
                session.messages.append({"role": "user", "content": message})
                prompt_tokens = sum(estimate_tokens(m["content"]) for m in session.messages)
                session.prompt_tokens_processed += prompt_tokens

                ai_msg = self.langchain_agent.invoke([
                    (m["role"], m["content"]) for m in session.messages
                ])
                reply_text = getattr(ai_msg, "content", str(ai_msg))
                agent_tokens = estimate_tokens(reply_text)
                session.token_usage += agent_tokens
                session.messages.append({"role": "assistant", "content": reply_text})
                return {
                    "response": reply_text,
                    "reply": reply_text,
                    "tokens": agent_tokens,
                    "prompt_tokens": prompt_tokens,
                }
            except Exception:
                pass
        return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.sessions[thread_id].token_usage if thread_id in self.sessions else 0

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.sessions[thread_id].prompt_tokens_processed if thread_id in self.sessions else 0

    def compaction_count(self, thread_id: str) -> int:
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]

        session.messages.append({"role": "user", "content": message})
        # Baseline accumulates all previous turns in thread
        prompt_tokens = sum(estimate_tokens(m["content"]) for m in session.messages)
        session.prompt_tokens_processed += prompt_tokens

        # In a fresh thread, baseline has no prior context
        if len(session.messages) <= 1:
            reply_text = "Xin chào, tôi là trợ lý ảo. Tôi chưa có thông tin trước đó trong phiên này."
        else:
            reply_text = f"Đã ghi nhận trong phiên: {message[:40]}"

        agent_tokens = estimate_tokens(reply_text)
        session.token_usage += agent_tokens
        session.messages.append({"role": "assistant", "content": reply_text})

        return {
            "response": reply_text,
            "reply": reply_text,
            "tokens": agent_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _maybe_build_langchain_agent(self):
        # ponytail: build live chat model only when API key is set
        if self.force_offline or not self.config.model.api_key:
            return None
        try:
            return build_chat_model(self.config.model)
        except Exception:
            return None

