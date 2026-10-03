from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore
from model_provider import ProviderConfig


def make_config(tmp_path: Path) -> LabConfig:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    provider_cfg = ProviderConfig(provider="openai", model_name="gpt-4o-mini", temperature=0.0)
    return LabConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_dir=state_dir,
        compact_threshold_tokens=60,
        compact_keep_messages=2,
        model=provider_cfg,
        judge_model=provider_cfg,
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    store = UserProfileStore(tmp_path / "profiles")
    user_id = "test_user"

    # Write initial profile
    initial_text = "# Profile\n- name: Alice\n- city: Danang\n"
    store.write_text(user_id, initial_text)
    assert store.read_text(user_id) == initial_text
    assert store.file_size(user_id) > 0

    # Edit profile
    success = store.edit_text(user_id, "Danang", "Hue")
    assert success is True
    assert "city: Hue" in store.read_text(user_id)
    assert "Danang" not in store.read_text(user_id)


def test_compact_trigger(tmp_path: Path) -> None:
    manager = CompactMemoryManager(threshold_tokens=40, keep_messages=2)
    thread_id = "thread_stress"

    for i in range(8):
        manager.append(thread_id, "user", f"Lượt nói dài số {i} với thật nhiều chi tiết kỹ thuật cần nén.")

    assert manager.compaction_count(thread_id) > 0
    ctx = manager.context(thread_id)
    assert len(ctx["messages"]) == 2
    assert "Summary" in str(ctx["summary"])


def test_cross_session_recall(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    user_id = "user_cross"
    intro = "Chào bạn, mình tên là DũngCT. Nơi ở hiện tại là Huế."

    baseline.reply(user_id, "session-1", intro)
    advanced.reply(user_id, "session-1", intro)

    # In a new session/thread:
    query = "Mình tên gì và hiện đang ở đâu?"
    base_res = baseline.reply(user_id, "session-2", query)["response"]
    adv_res = advanced.reply(user_id, "session-2", query)["response"]

    # Baseline forgets across sessions
    assert "DũngCT" not in base_res

    # Advanced recalls via persistent User.md
    assert "DũngCT" in adv_res
    assert "Huế" in adv_res


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    thread_id = "long_thread"
    user_id = "user_long"

    long_message = (
        "Đây là một lượt trao đổi rất dài trong hội thoại với nhiều chi tiết về "
        "Artemis III, máy bay X-59 và báo cáo khí hậu của WMO cần phân tích kỹ lưỡng."
    )

    for _ in range(12):
        baseline.reply(user_id, thread_id, long_message)
        advanced.reply(user_id, thread_id, long_message)

    baseline_prompt_tokens = baseline.prompt_token_usage(thread_id)
    advanced_prompt_tokens = advanced.prompt_token_usage(thread_id)

    assert advanced.compaction_count(thread_id) > 0
    assert advanced_prompt_tokens < baseline_prompt_tokens

