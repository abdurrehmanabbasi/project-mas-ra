"""CLI demonstration runner for Autonomous AI Research Assistant."""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph.workflow import create_research_graph


def main():
    parser = argparse.ArgumentParser(
        description="Run an autonomous academic literature search and review."
    )
    parser.add_argument(
        "--question",
        type=str,
        default="How are multi-agent AI systems improving autonomous software engineering?",
        help="Research inquiry to explore",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=5,
        help="Maximum papers to select and review",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["arxiv", "semantic_scholar"],
        help="Academic search providers (arxiv, semantic_scholar)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("🔬 AUTONOMOUS AI RESEARCH ASSISTANT (Milestone 1 Pipeline)")
    print("=" * 70)
    print(f"📌 Inquiry: {args.question}")
    print(f"📚 Sources: {', '.join(args.sources)} (Max papers: {args.max_papers})")
    print("-" * 70)

    graph = create_research_graph()

    initial_state = {
        "research_question": args.question,
        "scope": {
            "max_papers": args.max_papers,
            "preferred_sources": args.sources,
            "date_range_start": 2020,
            "date_range_end": 2026,
        },
    }

    config = {"configurable": {"thread_id": "cli-session-001"}}

    print("🚀 Running research pipeline...")
    final_state = graph.invoke(initial_state, config=config)

    plan = final_state.get("research_plan", {})
    print(f"\n📋 Objective:\n   {plan.get('objective')}")
    print(f"\n🔍 Formulated Subquestions ({len(plan.get('tasks', []))} tasks):")
    for task in plan.get("tasks", []):
        print(f"   • {task.get('subquestion')} [Query: '{task.get('query')}']")

    selected = final_state.get("selected_papers", [])
    print(f"\n📄 Selected & Deduplicated Papers ({len(selected)} papers):")
    for i, p in enumerate(selected, 1):
        sources = ", ".join(s["provider"] for s in p.get("sources", []))
        authors = ", ".join(p.get("authors", [])[:2])
        print(f"   {i}. {p.get('title')} ({authors}, {p.get('year')}) [{sources}]")

    report = final_state.get("final_report", {})
    print("\n" + "=" * 70)
    print("📝 GENERATED SYNTHESIS REPORT")
    print("=" * 70)
    print(report.get("content_markdown", "No content generated."))
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
