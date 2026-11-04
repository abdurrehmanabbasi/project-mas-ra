"""Streamlit Interactive Web Dashboard for Autonomous AI Research & Literature Review."""

import json
import os
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path and remove script dir to avoid 'app.py' shadowing the 'app' package
_script_dir = str(Path(__file__).resolve().parent)
while _script_dir in sys.path:
    sys.path.remove(_script_dir)

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

import streamlit as st

# Configure wide page layout
st.set_page_config(
    page_title="Autonomous Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.database.service import DatabaseService
from app.graph.workflow import create_research_graph
from app.schemas.report import ResearchReport
from app.schemas.research import ResearchScope
from app.tools.report_exporter import ReportExporter
from langgraph.types import Command


def get_graph_instance():
    """Retrieve or initialize graph instance in session state."""
    if "graph" not in st.session_state:
        st.session_state.graph = create_research_graph()
    return st.session_state.graph


# ---------------------------------------------------------------------------
# Navigation Setup
# ---------------------------------------------------------------------------
menu_options = [
    "Projects & New Search",
    "Active Run Monitor",
    "Human Review Checkpoint",
    "Report Library",
]

if "menu" not in st.session_state:
    st.session_state.menu = "Projects & New Search"

if st.session_state.menu not in menu_options:
    st.session_state.menu = "Projects & New Search"

# Sidebar
st.sidebar.title("🔬 Research Assistant")
st.sidebar.caption("Multi-Agent Autonomous Literature Review")

def on_nav_change():
    st.session_state.menu = st.session_state.nav_radio

menu = st.sidebar.radio(
    "Navigation",
    menu_options,
    index=menu_options.index(st.session_state.menu),
    key="nav_radio",
    on_change=on_nav_change,
)
# Keep in sync
st.session_state.menu = menu

st.sidebar.divider()
st.sidebar.markdown("### System Metrics")
all_projects = DatabaseService.list_projects()
all_runs = DatabaseService.list_runs()
all_reports = DatabaseService.list_reports()

col_m1, col_m2 = st.sidebar.columns(2)
col_m1.metric("Projects", len(all_projects))
col_m2.metric("Reports", len(all_reports))
st.sidebar.caption(f"Total Workflow Runs: **{len(all_runs)}**")


# ---------------------------------------------------------------------------
# View 1: Projects & New Search
# ---------------------------------------------------------------------------
if menu == "Projects & New Search":
    st.title("📚 Research Projects")
    st.write("Initiate an autonomous literature review across arXiv and Semantic Scholar.")

    with st.expander("➕ Create New Research Project", expanded=True):
        with st.form("new_project_form"):
            title = st.text_input("Project Title", placeholder="e.g. Multi-Agent Systems in Autonomous Coding")
            question = st.text_area(
                "Central Research Question",
                placeholder="e.g. How are multi-agent architectures improving autonomous software engineering benchmarks?",
                help="Provide a clear, specific academic research inquiry.",
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                max_papers = st.slider("Target Number of Papers", min_value=1, max_value=25, value=5)
            with col2:
                start_year = st.number_input("Start Year", min_value=2000, max_value=2026, value=2020)
                end_year = st.number_input("End Year", min_value=2000, max_value=2026, value=2026)
            with col3:
                sources = st.multiselect("Academic Sources", ["arxiv", "semantic_scholar"], default=["arxiv", "semantic_scholar"])
                skip_review = st.checkbox("Skip Human Review Checkpoint (Automated Run)", value=False)

            submitted = st.form_submit_button("Create Project & Launch Run", type="primary")
            if submitted:
                if not title or not question:
                    st.error("Please provide both a project title and a research inquiry.")
                else:
                    scope = {
                        "max_papers": max_papers,
                        "date_range_start": start_year,
                        "date_range_end": end_year,
                        "preferred_sources": sources,
                        "skip_human_review": skip_review,
                    }
                    project = DatabaseService.create_project(title=title, research_question=question, scope=scope)
                    thread_id = f"thread-{project.id[:8]}"
                    run = DatabaseService.create_run(project_id=project.id, thread_id=thread_id, scope_override=scope)
                    st.session_state.active_run_id = run.id
                    st.session_state.active_thread_id = thread_id
                    st.session_state.menu = "Active Run Monitor"
                    st.success(f"Project created! Run ID: `{run.id}` launched.")
                    st.rerun()

    st.subheader("Existing Projects")
    if all_projects:
        for p in all_projects:
            with st.container(border=True):
                st.markdown(f"#### {p.title}")
                st.caption(f"Created: {p.created_at.strftime('%Y-%m-%d %H:%M')} | Status: `{p.status}`")
                st.write(p.research_question)
    else:
        st.info("No research projects created yet.")


# ---------------------------------------------------------------------------
# View 2: Active Run Monitor
# ---------------------------------------------------------------------------
elif menu == "Active Run Monitor":
    st.title("⚡ Active Run Monitor")

    run_id = st.session_state.get("active_run_id")
    if not run_id:
        st.warning("No active run selected. Launch a run from 'Projects & New Search' or select an existing one below.")
        if all_runs:
            selected_run = st.selectbox(
                "Select Existing Run",
                all_runs,
                format_func=lambda r: f"Run {r.id[:8]} - {r.status.upper()} (Phase: {r.current_phase}) - Created {r.created_at.strftime('%H:%M:%S')}",
            )
            if st.button("Load Run"):
                st.session_state.active_run_id = selected_run.id
                st.session_state.active_thread_id = selected_run.thread_id
                st.rerun()
    else:
        run = DatabaseService.get_run(run_id)
        if not run:
            st.error("Run not found.")
        else:
            project = DatabaseService.get_project(run.project_id)
            p_question = project.research_question if project else "Autonomous literature review"
            p_title = project.title if project else "Research Project"

            st.markdown(f"### Researching: *{p_question}*")
            st.caption(f"Project: **{p_title}** | Run ID: `{run.id}` | Thread: `{run.thread_id}` | Status: **{run.status.upper()}**")

            col1, col2, col3 = st.columns(3)
            col1.metric("Current Phase", run.current_phase.replace("_", " ").title())
            col2.metric("Papers Harvested", run.papers_count)
            col3.metric("Evidence Extracted", run.evidence_count)

            # Option to switch runs
            if all_runs and len(all_runs) > 1:
                with st.expander("Switch to a Different Run", expanded=False):
                    switch_run = st.selectbox(
                        "All Runs",
                        all_runs,
                        format_func=lambda r: f"Run {r.id[:8]} - {r.status.upper()} ({r.current_phase})",
                        key="switch_run_select",
                    )
                    if st.button("Switch Run"):
                        st.session_state.active_run_id = switch_run.id
                        st.session_state.active_thread_id = switch_run.thread_id
                        st.rerun()

            st.divider()

            if run.status in ["queued", "running"]:
                if st.button("🚀 Execute Pipeline Step / Run Graph", type="primary", use_container_width=True):
                    with st.spinner("Multi-agent graph executing across Planner, Search, PDF Extraction, Analyst, Critic..."):
                        graph = get_graph_instance()
                        config = {"configurable": {"thread_id": run.thread_id}}
                        initial_state = {
                            "project_id": run.project_id,
                            "research_question": p_question,
                            "scope": json.loads(run.scope_json or "{}"),
                        }
                        try:
                            final_state = graph.invoke(initial_state, config=config)
                            snapshot = graph.get_state(config)

                            if snapshot.next:
                                DatabaseService.update_run_status(
                                    run_id=run.id,
                                    status="waiting_for_review",
                                    current_phase="human_review",
                                    papers_count=len(final_state.get("selected_papers", [])),
                                    evidence_count=len(final_state.get("extracted_evidence", [])),
                                )
                                st.session_state.menu = "Human Review Checkpoint"
                                st.warning("Graph paused at Human-in-the-Loop review checkpoint!")
                                st.rerun()
                            else:
                                final_rep = final_state.get("final_report", {})
                                if final_rep:
                                    DatabaseService.save_report(
                                        project_id=run.project_id,
                                        run_id=run.id,
                                        title=final_rep.get("title", p_title),
                                        report_dict=final_rep,
                                        markdown_content=final_rep.get("content_markdown", ""),
                                    )
                                DatabaseService.update_run_status(
                                    run_id=run.id,
                                    status="completed",
                                    current_phase="report_synthesized",
                                    papers_count=len(final_state.get("selected_papers", [])),
                                    evidence_count=len(final_state.get("extracted_evidence", [])),
                                )
                                st.session_state.menu = "Report Library"
                                st.success("Research run completed successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Execution error: {e}")
                            DatabaseService.update_run_status(run_id=run.id, status="failed", error_message=str(e))

            elif run.status == "waiting_for_review":
                st.warning("⚠️ This run is waiting for your approval at the Human Review Checkpoint.")
                if st.button("🛡️ Open Human Review Panel", type="primary"):
                    st.session_state.menu = "Human Review Checkpoint"
                    st.rerun()

            elif run.status == "completed":
                st.success("✅ Research synthesis completed!")
                if st.button("📑 Read Synthesized Report", type="primary"):
                    st.session_state.menu = "Report Library"
                    st.rerun()

            elif run.status == "failed":
                st.error(f"❌ Run failed: {run.error_message}")


# ---------------------------------------------------------------------------
# View 3: Human Review Checkpoint
# ---------------------------------------------------------------------------
elif menu == "Human Review Checkpoint":
    st.title("🛡️ Human-in-the-Loop Review Checkpoint")
    st.write("Inspect gathered literature, extracted evidence, critic quality score, and citation grounding checks before synthesis.")

    # Find candidate runs for review
    review_runs = [r for r in all_runs if r.status == "waiting_for_review"]

    run_id = st.session_state.get("active_run_id")
    current_run = DatabaseService.get_run(run_id) if run_id else None

    if not current_run or current_run.status != "waiting_for_review":
        if review_runs:
            st.info(f"Found {len(review_runs)} run(s) waiting for review. Select one below:")
            sel_rev_run = st.selectbox(
                "Runs Waiting for Review",
                review_runs,
                format_func=lambda r: f"Run {r.id[:8]} - (Thread: {r.thread_id}) - Created {r.created_at.strftime('%H:%M:%S')}",
            )
            if st.button("Load Review Package"):
                st.session_state.active_run_id = sel_rev_run.id
                st.session_state.active_thread_id = sel_rev_run.thread_id
                st.rerun()
        else:
            st.info("No runs currently paused at the review checkpoint. Launch a run without 'Skip Human Review' from 'Projects & New Search' to test HITL.")
    else:
        run = current_run
        graph = get_graph_instance()
        config = {"configurable": {"thread_id": run.thread_id}}
        snapshot = graph.get_state(config)

        # Retrieve review package from interrupt payload or state values
        pkg_data = None
        if snapshot.tasks:
            for task in snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    for intr in task.interrupts:
                        val = getattr(intr, "value", intr)
                        if isinstance(val, dict):
                            pkg_data = val
                            break

        if not pkg_data and isinstance(snapshot.values, dict):
            pkg_data = snapshot.values.get("review_package")

        # Fallback to constructing preview from snapshot state
        if not pkg_data and isinstance(snapshot.values, dict):
            papers = snapshot.values.get("selected_papers", [])
            evidence = snapshot.values.get("extracted_evidence", [])
            critique = snapshot.values.get("critique", {})
            citations = snapshot.values.get("verified_citations", [])
            project = DatabaseService.get_project(run.project_id)
            pkg_data = {
                "research_question": snapshot.values.get("research_question", project.research_question if project else ""),
                "objective": snapshot.values.get("research_plan", {}).get("objective", "Autonomous literature synthesis"),
                "selected_papers_count": len(papers),
                "papers_summary": [
                    {"paper_id": p.get("paper_id", ""), "title": p.get("title", ""), "year": p.get("year", ""), "doi": p.get("doi", "")}
                    for p in papers
                ],
                "evidence_count": len(evidence),
                "key_evidence": evidence[:6],
                "critique_score": critique.get("quality_score", 1.0),
                "missing_topics": critique.get("missing_topics", []),
                "citation_checks": citations,
            }

        if pkg_data:
            st.markdown(f"### Inquiry: *{pkg_data.get('research_question')}*")
            st.caption(f"Objective: {pkg_data.get('objective')}")

            col1, col2, col3 = st.columns(3)
            col1.metric("Selected Papers", pkg_data.get("selected_papers_count", 0))
            col2.metric("Evidence Claims", pkg_data.get("evidence_count", 0))
            crit_score = pkg_data.get("critique_score", 1.0)
            col3.metric("Critic Quality Score", f"{crit_score:.2f} / 1.00")

            # 1. Harvested Papers Summary (No Pandas dependency)
            with st.expander("📄 Harvested Papers Summary", expanded=True):
                papers = pkg_data.get("papers_summary", [])
                if papers:
                    for idx, p in enumerate(papers, 1):
                        with st.container(border=True):
                            st.markdown(f"**{idx}. {p.get('title', 'Untitled')}** ({p.get('year', 'N/A')})")
                            doi_info = f"DOI: `{p.get('doi')}` | " if p.get("doi") else ""
                            st.caption(f"{doi_info}Paper ID: `{p.get('paper_id')}`")
                else:
                    st.info("No papers harvested yet.")

            # 2. Key Grounded Evidence
            with st.expander("🔍 Key Extracted Evidence Excerpts", expanded=False):
                evidence = pkg_data.get("key_evidence", [])
                if evidence:
                    for idx, ev in enumerate(evidence, 1):
                        st.markdown(f"**{idx}. {ev.get('claim')}** (Scope: `{ev.get('content_scope', 'abstract_only')}`)")
                        st.caption(f"Quote: \"{ev.get('supporting_passage', '')[:200]}...\"")
                else:
                    st.info("No evidence excerpts extracted yet.")

            # 3. Citation & DOI Verification Audit
            with st.expander("✅ Bibliographic & Citation Grounding Checks", expanded=True):
                citations = pkg_data.get("citation_checks", [])
                if citations:
                    for c in citations:
                        doi_icon = "✅" if c.get("doi_valid") else "⚠️"
                        claim_icon = "✅" if c.get("claim_supported") else "❌"
                        notes = f" — *{c.get('notes')}*" if c.get("notes") else ""
                        st.markdown(f"- **Paper `{c.get('paper_id')[:16]}`**: DOI: {doi_icon} | Grounding: {claim_icon}{notes}")
                else:
                    st.info("Citation checks verified.")

            # 4. Missing Topics Notice
            missing = pkg_data.get("missing_topics", [])
            if missing:
                st.warning(f"Critic detected gaps / missing subtopics: {', '.join(missing)}")

            st.divider()

            # Review Decision Controls
            st.subheader("Submit Human Decision")
            col_app, col_rev, col_rej = st.columns(3)

            with col_app:
                if st.button("✅ Approve & Synthesize Report", type="primary", use_container_width=True):
                    with st.spinner("Synthesizing final academic report..."):
                        cmd = Command(resume={"action": "approve"})
                        final_state = graph.invoke(cmd, config=config)
                        final_rep = final_state.get("final_report", {})
                        project = DatabaseService.get_project(run.project_id)
                        p_title = project.title if project else "Synthesized Report"

                        if final_rep:
                            rep_title = final_rep.get("title") or p_title
                            saved_rep = DatabaseService.save_report(
                                project_id=run.project_id,
                                run_id=run.id,
                                title=rep_title,
                                report_dict=final_rep,
                                markdown_content=final_rep.get("content_markdown", ""),
                            )
                        DatabaseService.update_run_status(
                            run_id=run.id,
                            status="completed",
                            current_phase="report_synthesized",
                            papers_count=len(final_state.get("selected_papers", [])),
                            evidence_count=len(final_state.get("extracted_evidence", [])),
                        )
                        st.session_state.menu = "Report Library"
                        st.success("Approved! Report synthesized successfully.")
                        st.rerun()

            with col_rev:
                revision_feedback = st.text_input("Revision Feedback", placeholder="e.g. Include more empirical benchmark studies")
                if st.button("🔄 Request Revision Cycle", use_container_width=True):
                    with st.spinner("Dispatching revision tasks to search workers..."):
                        cmd = Command(resume={"action": "request_revision", "feedback": revision_feedback})
                        final_state = graph.invoke(cmd, config=config)
                        snapshot = graph.get_state(config)
                        if snapshot.next:
                            DatabaseService.update_run_status(run_id=run.id, status="waiting_for_review", current_phase="human_review")
                        else:
                            DatabaseService.update_run_status(run_id=run.id, status="completed", current_phase="report_synthesized")
                        st.info("Revision cycle processed.")
                        st.rerun()

            with col_rej:
                st.write("")  # alignment spacer
                st.write("")
                if st.button("❌ Reject Research Run", use_container_width=True):
                    cmd = Command(resume={"action": "reject"})
                    graph.invoke(cmd, config=config)
                    DatabaseService.update_run_status(run_id=run.id, status="rejected", current_phase="rejected")
                    st.error("Run rejected.")
                    st.session_state.menu = "Active Run Monitor"
                    st.rerun()


# ---------------------------------------------------------------------------
# View 4: Report Library
# ---------------------------------------------------------------------------
elif menu == "Report Library":
    st.title("📑 Literature Review Library")

    if not all_reports:
        st.info("No generated reports found yet. Complete a research run from 'Projects & New Search' to generate your first review report.")
    else:
        # Determine default selected report
        run_id = st.session_state.get("active_run_id")
        default_idx = 0
        if run_id:
            for idx, r in enumerate(all_reports):
                if r.run_id == run_id:
                    default_idx = idx
                    break

        selected_report = st.selectbox(
            "Select Generated Report to Read",
            all_reports,
            index=default_idx,
            format_func=lambda r: f"{r.title} — {r.created_at.strftime('%Y-%m-%d %H:%M')}",
        )

        if selected_report:
            st.markdown(f"## {selected_report.title}")
            st.caption(f"Created: {selected_report.created_at.strftime('%Y-%m-%d %H:%M')} | Report ID: `{selected_report.id}` | Run ID: `{selected_report.run_id}`")

            # Download Actions
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "📥 Download Markdown (.md)",
                    data=selected_report.markdown_content,
                    file_name=f"literature_review_{selected_report.id[:8]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_dl2:
                try:
                    rep_data = json.loads(selected_report.report_json)
                    rep_obj = ResearchReport.model_validate(rep_data)
                    pdf_tmp_path = os.path.join(os.environ.get("TEMP", "."), f"report_{selected_report.id[:8]}.pdf")
                    ReportExporter.export_pdf(rep_obj, pdf_tmp_path)
                    with open(pdf_tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        "📄 Download Styled PDF (.pdf)",
                        data=pdf_bytes,
                        file_name=f"literature_review_{selected_report.id[:8]}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.caption(f"PDF compilation notice: {e}")

            st.divider()

            # Render Full Markdown Content
            st.markdown(selected_report.markdown_content)
