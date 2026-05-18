#!/usr/bin/env python3
"""Phase 1 Memory Verification Script

Validates that MemPalace memory works across analysis runs.
The Devil's Advocate's second analysis should reference the first.

Usage: uv run python scripts/validate_phase1.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from council.memory.mempalace import CouncilMemoryManager


def test_memory_store_and_recall():
    memory = CouncilMemoryManager()
    memory.ensure_wings()

    analysis_id = "phase1-test-001"
    agent_name = "devils_advocate"

    output = {
        "role": agent_name,
        "content": "Kill Shot 1: Competitor Kill Shot — Dentrix dominates with 35% market share. "
        "Switching costs are prohibitive. THE FATAL ASSUMPTION: dentists will abandon "
        "20-year-old workflows for an AI tool with no track record.",
        "kill_shots": [
            {
                "title": "Entrenched Competitors",
                "reasoning": "Dentrix at 35% share with 20-year contracts",
                "data_point": "Dentrix: 35%, Eaglesoft: 28%",
            }
        ],
        "verdict": "Entrenched competition kills this idea.",
        "forbidden_check_passed": True,
    }

    drawer_id = memory.store_agent_output(agent_name, analysis_id, output)
    assert drawer_id is not None
    print(f"  ✅ Stored analysis with drawer_id={drawer_id}")

    recalled = memory.recall_past_analysis(agent_name, analysis_id=analysis_id)
    assert len(recalled) == 1
    assert recalled[0]["content"]["role"] == agent_name
    assert "Dentrix" in recalled[0]["content"]["content"]
    print("  ✅ Exact recall successful")

    semantic = memory.recall_past_analysis(
        agent_name, query="dental practice management software competition"
    )
    assert len(semantic) > 0
    print(f"  ✅ Semantic search found {len(semantic)} results")

    diary_before = memory.read_recent_diary(agent_name, n_entries=10)
    memory.store_diary_entry(
        agent_name,
        "ANALYSIS:phase1-test-001|query:dental AI|divergences:0|confidence:55",
        topic="analysis",
    )
    diary_after = memory.read_recent_diary(agent_name, n_entries=10)
    assert len(diary_after) == len(diary_before) + 1
    print(f"  ✅ Diary write/read successful ({len(diary_after)} entries)")

    return True


def test_multiple_analysis_context():
    memory = CouncilMemoryManager()
    memory.ensure_wings()

    memory.store_agent_output(
        "devils_advocate", "session-a", {"role": "devils_advocate", "content": "KILL SHOT: Market is too small — TAM under $100M."}
    )
    memory.store_agent_output(
        "market_analyst", "session-a", {"role": "market_analyst", "content": "TAM: $500M, growing at 12% CAGR."}
    )

    recalled_devils = memory.recall_past_analysis("devils_advocate", analysis_id="session-a")
    recalled_market = memory.recall_past_analysis("market_analyst", analysis_id="session-a")

    assert len(recalled_devils) == 1
    assert len(recalled_market) == 1

    semantic_market = memory.recall_past_analysis(
        "market_analyst", query="small market TAM analysis"
    )
    assert len(semantic_market) > 0
    print("  ✅ Multi-agent memory isolation verified")


def main():
    print("=" * 60)
    print("  AI Validation Council — Phase 1 Memory Verification")
    print("=" * 60)

    all_passed = True
    tests = [
        ("Store & Recall (Exact + Semantic + Diary)", test_memory_store_and_recall),
        ("Multi-Agent Memory Isolation", test_multiple_analysis_context),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {name}")
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            all_passed = False
        except Exception as e:
            print(f"  ❌ {name}: unexpected {type(e).__name__}: {e}")
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED — MemPalace memory is working correctly.")
        print("   The council can now reference past analyses across sessions.")
        return 0
    else:
        print("❌ SOME TESTS FAILED — check logs above.")
        return 1


if __name__ == "__main__":
    exit(main())
