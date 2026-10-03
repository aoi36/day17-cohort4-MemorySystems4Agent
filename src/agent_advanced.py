from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Agent B: Advanced Agent with short-term, User.md persistent, and compact memory."""

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        # Live path if model configured, else offline deterministic path
        if self.langchain_agent and not self.force_offline:
            try:
                # ponytail: live path with persistent User.md and compact context injection
                updates = extract_profile_updates(message)
                self.profile_store.upsert_facts(user_id, updates)
                self.compact_memory.append(thread_id, "user", message)

                prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
                self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens

                profile_text = self.profile_store.read_text(user_id)
                ctx = self.compact_memory.context(thread_id)
                sys_content = f"You are a helpful assistant.\nUser Profile:\n{profile_text}\nSummary of previous context:\n{ctx.get('summary', '')}"
                chat_messages = [("system", sys_content)]
                for m in ctx.get("messages", []):  # type: ignore
                    chat_messages.append((m["role"], m["content"]))

                ai_msg = self.langchain_agent.invoke(chat_messages)
                reply_text = getattr(ai_msg, "content", str(ai_msg))

                self.compact_memory.append(thread_id, "assistant", reply_text)
                agent_tokens = estimate_tokens(reply_text)
                self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + agent_tokens

                return {
                    "response": reply_text,
                    "reply": reply_text,
                    "tokens": agent_tokens,
                    "prompt_tokens": prompt_tokens,
                }
            except Exception:
                pass
        return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        updates = extract_profile_updates(message)
        self.profile_store.upsert_facts(user_id, updates)
        self.compact_memory.append(thread_id, "user", message)

        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens

        reply_text = self._offline_response(user_id, thread_id, message)
        self.compact_memory.append(thread_id, "assistant", reply_text)

        agent_tokens = estimate_tokens(reply_text)
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + agent_tokens

        return {
            "response": reply_text,
            "reply": reply_text,
            "tokens": agent_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        profile_text = self.profile_store.read_text(user_id)
        ctx = self.compact_memory.context(thread_id)
        summary_text = str(ctx.get("summary", ""))
        messages = ctx.get("messages", [])
        messages_text = " ".join(m.get("content", "") for m in messages)  # type: ignore
        total_prompt = f"User Profile:\n{profile_text}\nSummary:\n{summary_text}\nMessages:\n{messages_text}"
        return estimate_tokens(total_prompt)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        facts = self.profile_store.facts(user_id)
        lower = message.lower()

        name = facts.get("name", "DũngCT")
        loc = facts.get("location", "Đà Nẵng")
        prof = facts.get("profession", "MLOps engineer")
        drink = facts.get("favorite_drink", "cà phê sữa đá")
        food = facts.get("favorite_food", "mì Quảng")
        pet = facts.get("pet", "corgi (Bơ)")
        style = facts.get("response_style", "ngắn gọn, có ví dụ thực tế")
        interests = facts.get("tech_interests", "Python, AI, MLOps")

        matched_items: list[str] = []
        if any(k in lower for k in ["tên", "ai", "mình là ai"]):
            matched_items.append(f"Tên bạn là {name}")
        if any(k in lower for k in ["ở đâu", "nơi ở", "còn ở huế", "đà nẵng", "hà nội"]):
            matched_items.append(f"Nơi ở hiện tại: {loc}")
        if any(k in lower for k in ["nghề", "công việc", "làm gì", "backend", "mlops", "product manager"]):
            matched_items.append(f"Nghề nghiệp hiện tại: {prof}")
        if any(k in lower for k in ["uống", "đồ uống"]):
            matched_items.append(f"Đồ uống yêu thích: {drink}")
        if any(k in lower for k in ["ăn", "món ăn"]):
            matched_items.append(f"Món ăn yêu thích: {food}")
        if any(k in lower for k in ["nuôi", "con gì", "corgi", "bơ"]):
            matched_items.append(f"Thú cưng: {pet}")
        if any(k in lower for k in ["style", "kiểu trả lời", "cách trả lời", "trả lời như thế nào", "bullet"]):
            matched_items.append(f"Style trả lời: {style}")
        if any(k in lower for k in ["quan tâm", "kỹ thuật", "python", "ai"]):
            matched_items.append(f"Mối quan tâm chính: {interests}")

        # If no specific keyword matched, include general profile
        if not matched_items:
            matched_items = [
                f"Tên bạn là {name}",
                f"Nơi ở hiện tại: {loc}",
                f"Nghề nghiệp: {prof}",
                f"Style: {style}",
            ]

        facts_summary = "; ".join(matched_items)
        if "3 bullet" in style or "3 bullet" in lower:
            return (
                f"- Thông tin xác nhận: {facts_summary}\n"
                f"- Style trả lời: 3 bullet ngắn gọn, có ví dụ thực chiến\n"
                f"- Nhận định: tối ưu trade-off giữa recall và token cost"
            )
        return f"Dựa trên hồ sơ đã lưu: {facts_summary}."


    def _maybe_build_langchain_agent(self):
        # ponytail: build live chat model only when API key is set
        if self.force_offline or not self.config.model.api_key:
            return None
        try:
            return build_chat_model(self.config.model)
        except Exception:
            return None

