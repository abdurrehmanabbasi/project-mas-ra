"""CLI demonstration runner for Autonomous AI Research Assistant (Milestone 2)."""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph.workflow import create_research_graph


def main():
    parser = argparse.ArgumentParser(
        description="Run an autonomous academic literature search, evidence extraction, and synthesis."
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

    print("\n" + "=" * 75)
    print("🔬 AUTONOMOUS AI RESEARCH ASSISTANT (Milestone 2 Evidence-Grounded Pipeline)")
    print("=" * 75)
    print(f"📌 Inquiry: {args.question}")
    print(f"📚 Sources: {', '.join(args.sources)} (Target papers: {args.max_papers})")
    print("-" * 75)

    graph = create_research_graph()

    initial_state = {
        "research_question": args.question,
        "scope": {
            "max_papers": args.max_papers,
            "preferred_sources": args.sources,
            "date_range_start": 2020,
            "date_range_end": 2026,
        },
        "revision_count": 0,
        "max_revisions": 2,
    }

    config = {"configurable": {"thread_id": "cli-session-002"}}

    print("🚀 Executing research intelligence graph...")
    final_state = graph.invoke(initial_state, config=config)

    # 1. Research Plan
    plan = final_state.get("research_plan", {})
    print(f"\n📋 Objective:\n   {plan.get('objective')}")
    print(f"\n🔍 Formulated Subquestions ({len(plan.get('tasks', []))} tasks):")
    for task in plan.get("tasks", []):
        print(f"   • {task.get('subquestion')} [Query: '{task.get('query')}']")

    # 2. Paper Content Provenance
    contents = final_state.get("paper_contents", [])
    full_text_count = sum(1 for c in contents if c.get("content_scope") == "full_text")
    abstract_count = sum(1 for c in contents if c.get("content_scope") == "abstract_only")
    print(f"\n📑 Retrieved Paper Content Provenance ({len(contents)} papers):")
    print(f"   • Full-text PDFs parsed: {full_text_count}")
    print(f"   • Abstract-only scope: {abstract_count}")

    # 3. Grounded Evidence Passages
    evidence = final_state.get("extracted_evidence", [])
    print(f"\n🧪 Extracted Grounded Evidence ({len(evidence)} atomic records):")
    for i, ev in enumerate(evidence[:4], 1):
        passage = ev.get("supporting_passage", "")[:120]
        scope = ev.get("content_scope", "abstract_only")
        print(f"   {i}. \"{passage}...\" [Scope: {scope}]")

    # 4. Cross-Paper Synthesis
    synthesis = final_state.get("synthesis", {})
    themes = synthesis.get("themes", [])
    print(f"\n📊 Thematic Synthesis ({len(themes)} themes):")
    for theme in themes:
        print(f"   • {theme.get('theme_name')}: {theme.get('description')}")

    # 5. Critic Evaluation & Revision History
    critique = final_state.get("critique", {})
    revision_count = final_state.get("revision_count", 0)
    score = critique.get("quality_score", 1.0)
    print(f"\n⚖️ Critic Evaluation:")
    print(f"   • Quality / Coverage Score: {score:.2f}")
    print(f"   • Revisions Executed: {revision_count}")
    if critique.get("missing_topics"):
        print(f"   • Flagged Gaps: {', '.join(critique.get('missing_topics')[:2])}")

    # 6. Final Report
    report = final_state.get("final_report", {})
    print("\n" + "=" * 75)
    print("📝 FINAL SYNTHESIS REPORT")
    print("=" * 75)
    print(report.get("content_markdown", "No content generated."))
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
