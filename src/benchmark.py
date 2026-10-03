from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tabulate import tabulate

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    if not expected:
        return 1.0
    ans_lower = answer.lower()
    matched = sum(1 for exp in expected if exp.lower() in ans_lower)
    ratio = matched / len(expected)
    if ratio >= 1.0:
        return 1.0
    if ratio > 0.0:
        return 0.5
    return 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    # ponytail: heuristic quality metric; replace with LLM judge in live evaluation
    if not answer or "Tôi chưa có thông tin" in answer:
        return 0.2
    score = 0.5
    ans_lower = answer.lower()
    matched = sum(1 for exp in expected if exp.lower() in ans_lower)
    if expected:
        score += 0.4 * (matched / len(expected))
    if len(answer.strip()) > 20:
        score += 0.1
    return round(min(1.0, score), 2)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    all_threads: set[str] = set()
    recall_scores: list[float] = []
    quality_scores: list[float] = []
    user_ids: set[str] = set()

    for conv in conversations:
        user_id = conv.get("user_id", "default_user")
        user_ids.add(user_id)
        conv_id = conv.get("id", "conv")
        all_threads.add(conv_id)

        for turn in conv.get("turns", []):
            agent.reply(user_id=user_id, thread_id=conv_id, message=turn)

        recall_thread_id = f"{conv_id}-recall"
        all_threads.add(recall_thread_id)
        for q in conv.get("recall_questions", []):
            question = q["question"]
            expected = q.get("expected_contains", [])
            res = agent.reply(user_id=user_id, thread_id=recall_thread_id, message=question)
            answer = res.get("response") or res.get("reply", "")
            recall_scores.append(recall_points(answer, expected))
            quality_scores.append(heuristic_quality(answer, expected))

    total_agent_tokens = sum(agent.token_usage(tid) for tid in all_threads)
    total_prompt_tokens = sum(agent.prompt_token_usage(tid) for tid in all_threads)
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    mem_bytes = 0
    if hasattr(agent, "memory_file_size"):
        mem_bytes = sum(agent.memory_file_size(uid) for uid in user_ids)

    compactions = 0
    if hasattr(agent, "compaction_count"):
        compactions = sum(agent.compaction_count(tid) for tid in all_threads)

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=mem_bytes,
        compactions=compactions,
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    headers = [
        "Agent",
        "Agent tokens only",
        "Prompt tokens processed",
        "Cross-session recall",
        "Response quality",
        "Memory growth (bytes)",
        "Compactions",
    ]
    table = [
        [
            r.agent_name,
            r.agent_tokens_only,
            r.prompt_tokens_processed,
            f"{r.recall_score * 100:.1f}%",
            f"{r.response_quality:.2f}",
            r.memory_growth_bytes,
            r.compactions,
        ]
        for r in rows
    ]
    return tabulate(table, headers=headers, tablefmt="github")


def main() -> None:
    config = load_config(Path(__file__).resolve().parent.parent)

    std_data_path = config.data_dir / "conversations.json"
    stress_data_path = config.data_dir / "advanced_long_context.json"

    std_conversations = load_conversations(std_data_path)
    stress_conversations = load_conversations(stress_data_path)

    print("=== Standard Benchmark ===")
    baseline_std = BaselineAgent(config, force_offline=True)
    advanced_std = AdvancedAgent(config, force_offline=True)
    std_rows = [
        run_agent_benchmark("Baseline", baseline_std, std_conversations, config),
        run_agent_benchmark("Advanced", advanced_std, std_conversations, config),
    ]
    print(format_rows(std_rows))

    print("\n=== Long-Context Stress Benchmark ===")
    baseline_stress = BaselineAgent(config, force_offline=True)
    advanced_stress = AdvancedAgent(config, force_offline=True)
    stress_rows = [
        run_agent_benchmark("Baseline", baseline_stress, stress_conversations, config),
        run_agent_benchmark("Advanced", advanced_stress, stress_conversations, config),
    ]
    print(format_rows(stress_rows))


if __name__ == "__main__":
    main()

