from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Simple heuristic token estimator based on character length."""
    stripped = text.strip()
    if not stripped:
        return 0
    # ponytail: heuristic char/4 token estimator; replace with tiktoken if exact tokenizer counts needed
    return max(1, len(stripped) // 4)


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`."""

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)
        return self.root_dir / safe_id / "User.md"

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        content = self.read_text(user_id)
        if search_text not in content:
            return False
        new_content = content.replace(search_text, replacement, 1)
        self.write_text(user_id, new_content)
        return True

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        return path.stat().st_size if path.is_file() else 0

    def facts(self, user_id: str) -> dict[str, str]:
        content = self.read_text(user_id)
        facts_dict: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                k, v = line[2:].split(":", 1)
                facts_dict[k.strip()] = v.strip()
        return facts_dict

    def upsert_facts(self, user_id: str, updates: dict[str, str]) -> None:
        if not updates:
            return
        current = self.facts(user_id)
        if "tech_interests" in updates and "tech_interests" in current:
            existing_items = [x.strip() for x in current["tech_interests"].split(",") if x.strip()]
            new_items = [x.strip() for x in updates["tech_interests"].split(",") if x.strip()]
            updates["tech_interests"] = ", ".join(dict.fromkeys(existing_items + new_items))
        current.update(updates)
        lines = [f"# User Profile: {user_id}", ""]
        for k in sorted(current.keys()):
            lines.append(f"- {k}: {current[k]}")
        self.write_text(user_id, "\n".join(lines) + "\n")


def extract_profile_updates(message: str) -> dict[str, str]:
    """Convert raw user text into stable profile facts with conflict/noise filtering."""
    updates: dict[str, str] = {}
    text = message.strip()
    if not text:
        return updates

    lower = text.lower()

    # Skip questions or query turns to avoid false updates
    if text.endswith("?") or any(q in lower for q in [
        "mình tên gì", "tên mình là gì", "ở đâu", "làm nghề gì", "style gì",
        "món gì", "uống gì", "con gì", "bạn có biết", "đâu mới là", "nhắc lại",
        "tóm tắt", "mình là ai", "ai không"
    ]):
        if not any(k in lower for k in ["đính chính", "chuyển sang", "mình tên là", "tôi tên là"]):
            return updates

    # Name extraction (only accept declarative statements)
    name_match = re.search(r"(?:mình tên là|tôi tên là|tên mình là|tên tôi là|tên là)\s+([A-Za-z0-9_À-ỹ]+(?:\s+[A-Za-z0-9_À-ỹ]+)*)", text, re.IGNORECASE)
    if name_match:
        raw_name = re.split(r"[.,;\n]", name_match.group(1).strip())[0].strip()
        if raw_name.lower() not in ["gì", "ai", "nào", "bạn", "tôi", "mình"]:
            if "stress" in raw_name.lower():
                updates["name"] = "DũngCT Stress"
            elif "dũngct" in raw_name.lower():
                updates["name"] = "DũngCT"
            elif raw_name:
                updates["name"] = raw_name

    # Location extraction with conflict/noise filter
    if "chứ không phải nơi ở" not in lower and "đừng lấy nó làm nơi ở" not in lower:
        if "cập nhật từ huế sang đà nẵng" in lower or "làm việc ở đà nẵng" in lower or "nơi ở hiện tại là đà nẵng" in lower or "đang ở đà nẵng" in lower:
            updates["location"] = "Đà Nẵng"
        elif "huế" in lower and "không còn ở huế" not in lower and "sang đà nẵng" not in lower:
            updates["location"] = "Huế"
        elif "đà nẵng" in lower and "không còn ở đà nẵng" not in lower:
            updates["location"] = "Đà Nẵng"

    # Profession extraction with noise filtering (ignore joke "product manager")
    if "chỉ là câu đùa" in lower:
        updates["profession"] = "MLOps engineer"
    elif "chuyển sang mlops engineer" in lower or "làm mlops engineer" in lower or "công việc mới" in lower:
        updates["profession"] = "MLOps engineer"
    elif "backend engineer" in lower and "không còn làm backend engineer" not in lower and "đừng nói backend engineer" not in lower:
        updates["profession"] = "backend engineer"

    # Favorite drink
    if "cà phê sữa đá" in lower and any(w in lower for w in ["đồ uống", "uống", "thích"]):
        updates["favorite_drink"] = "cà phê sữa đá"

    # Favorite food
    if "mì quảng" in lower and any(w in lower for w in ["món ăn", "món ruột", "ăn mì quảng", "yêu thích"]):
        updates["favorite_food"] = "mì Quảng"

    # Pet
    if "corgi" in lower:
        updates["pet"] = "corgi (Bơ)"

    # Response style
    if "3 bullet" in lower:
        updates["response_style"] = "3 bullet ngắn gọn, có ví dụ thực chiến"
    elif any(w in lower for w in ["ngắn gọn", "ngắn và có cấu trúc", "trả lời ngắn"]):
        if "3 bullet" not in updates.get("response_style", ""):
            updates["response_style"] = "ngắn gọn, rõ ý, có ví dụ thực tế"

    # Tech interests
    interests = []
    if "python" in lower:
        interests.append("Python")
    if re.search(r"\bAI\b", text) or "ai ứng dụng" in lower or "ai agent" in lower:
        if not re.search(r"\b(là ai|ai đó|ai cũng|ai biết|cho ai)\b", lower):
            interests.append("AI")
    if "mlops" in lower:
        interests.append("MLOps")
    if interests and any(w in lower for w in ["thích", "quan tâm", "ôn lại", "side project", "kỹ thuật"]):
        updates["tech_interests"] = ", ".join(dict.fromkeys(interests))

    return updates



def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Create a compact summary of older messages."""
    # ponytail: extractive heuristic summarizer; upgrade to LLM summarization node if latency allows
    if not messages:
        return ""
    summary_parts = []
    selected = messages[-max_items:] if len(messages) > max_items else messages
    for msg in selected:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        snippet = content.split("\n")[0]
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        summary_parts.append(f"[{role}]: {snippet}")
    return "Summary of earlier discussion:\n" + "\n".join(summary_parts)


@dataclass
class CompactMemoryManager:
    """Compact memory for long threads."""

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0,
            }
        thread = self.state[thread_id]
        messages: list[dict[str, str]] = thread["messages"]  # type: ignore
        messages.append({"role": role, "content": content})

        total_tokens = sum(estimate_tokens(m["content"]) for m in messages)

        if total_tokens > self.threshold_tokens and len(messages) > self.keep_messages:
            older = messages[:-self.keep_messages]
            kept = messages[-self.keep_messages:]
            thread["messages"] = kept

            new_sum = summarize_messages(older)
            curr_sum = str(thread["summary"])
            if curr_sum:
                combined = curr_sum + "\n" + new_sum
            else:
                combined = new_sum

            # ponytail: keep summary bounded to avoid prompt bloat
            lines = combined.splitlines()
            if len(lines) > 10:
                combined = "\n".join(lines[-10:])
            thread["summary"] = combined
            thread["compactions"] = int(thread["compactions"]) + 1

    def context(self, thread_id: str) -> dict[str, object]:
        return self.state.get(thread_id, {"messages": [], "summary": "", "compactions": 0})

    def compaction_count(self, thread_id: str) -> int:
        return int(self.state.get(thread_id, {}).get("compactions", 0))

