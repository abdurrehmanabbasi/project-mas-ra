"""Streamlit Interactive Web Dashboard for Autonomous AI Research & Literature Review."""

import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

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
    page_title="MAS-RA: Autonomous Research Assistant",
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


@st.cache_resource
def get_shared_compiled_graph():
    """Cache compiled graph so checkpointer state is preserved across all reruns."""
    return create_research_graph()


def get_graph():
    return get_shared_compiled_graph()


# ---------------------------------------------------------------------------
# Navigation State Management
# ---------------------------------------------------------------------------
MENU_OPTIONS = [
    "Projects & New Search",
    "Active Run Monitor",
    "Human Review Checkpoint",
    "Report Library",
]

if "menu" not in st.session_state:
    st.session_state.menu = "Projects & New Search"

if st.session_state.menu not in MENU_OPTIONS:
    st.session_state.menu = "Projects & New Search"

if "sidebar_nav_radio" not in st.session_state:
    st.session_state.sidebar_nav_radio = st.session_state.menu


def navigate_to(target_menu: str, run_id: Optional[str] = None, project_id: Optional[str] = None, report_id: Optional[str] = None):
    """Safely navigate between tabs using a pre-widget pending redirect key."""
    st.session_state.menu = target_menu
    st.session_state._pending_nav = target_menu
    if run_id:
        st.session_state.active_run_id = run_id
    if project_id:
        st.session_state.active_project_id = project_id
    if report_id:
        st.session_state.active_report_id = report_id
    st.rerun()


def _stream_graph_updates(graph: Any, payload: Any, config: Dict[str, Any]) -> None:
    """Stream LangGraph node updates using exact workflow node identifiers."""
    for chunk in graph.stream(payload, config=config, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue
        for node_name, node_update in chunk.items():
            update = node_update if isinstance(node_update, dict) else {}
            if node_name == "planner":
                p_tasks = update.get("research_plan", {}).get("tasks", [])
                st.write(f"📋 **Planner Agent**: Formulated {len(p_tasks)} focused search sub-tasks.")
            elif node_name == "search_worker":
                p_list = update.get("search_results", [])
                st.write(f"🔍 **Search Worker**: Retrieved {len(p_list)} candidate academic papers.")
            elif node_name == "deduplicate_and_rank":
                sel = update.get("selected_papers", [])
                st.write(f"📑 **Deduplication & Ranking**: Selected top {len(sel)} unique publications.")
            elif node_name == "retrieve_content":
                contents = update.get("paper_contents", [])
                st.write(f"📥 **PDF Retriever**: Parsed {len(contents)} paper content record(s).")
            elif node_name == "extract_evidence":
                ev_list = update.get("extracted_evidence", [])
                st.write(f"🔬 **Evidence Extractor**: Extracted {len(ev_list)} empirical claim passages.")
            elif node_name == "analyze_literature":
                st.write("📊 **Literature Analyst**: Generated thematic cross-paper comparative matrices.")
            elif node_name == "critique":
                crit_val = update.get("critique", {})
                score = crit_val.get("quality_score", 1.0)
                needs_rev = crit_val.get("needs_revision", False)
                suffix = " (dispatching revision searches)" if needs_rev else " (coverage approved)"
                st.write(f"⚖️ **Critic Agent**: Scored literature coverage at {score:.2f} / 1.00{suffix}.")
            elif node_name in ("prepare_revision", "prepare_human_revision"):
                st.write("🔄 **Revision Planner**: Dispatching targeted follow-up search workers...")
            elif node_name == "verify_citations":
                checks = update.get("verified_citations", [])
                st.write(f"✅ **Citation Verifier**: Audited DOIs and grounding across {len(checks)} references.")
            elif node_name == "human_review":
                st.write("🛡️ **Human Review**: Recorded reviewer decision.")
            elif node_name == "synthesize_summary":
                st.write("📝 **Report Writer Agent**: Publication-grade literature review compiled.")
            elif node_name == "mark_rejected":
                st.write("❌ **Workflow Terminated**: Run marked rejected.")


def _build_resilient_report_obj(report_row: Any) -> ResearchReport:
    """Validate stored report JSON into ResearchReport with safe defaults for legacy/partial records."""
    rep_data = json.loads(report_row.report_json) if report_row.report_json else {}
    rep_data.setdefault("project_id", report_row.project_id)
    rep_data.setdefault("report_id", report_row.id)
    rep_data.setdefault("title", report_row.title)
    rep_data.setdefault("abstract", "Executive abstract of systematic literature synthesis.")
    rep_data.setdefault("introduction", rep_data.get("abstract", "Introduction to literature review."))
    rep_data.setdefault("comparative_analysis", "Thematic comparative analysis across literature.")
    rep_data.setdefault("limitations", "Threats to validity and empirical study limitations.")
    rep_data.setdefault("sections", [])
    rep_data.setdefault("references", [])
    rep_data.setdefault("citation_checks", [])
    rep_data.setdefault("research_gaps", [])
    return ResearchReport.model_validate(rep_data)


def _persist_completed_run(run: Any, default_title: str, final_state: Dict[str, Any]) -> Optional[str]:
    """Persist synthesized report (reconstructing markdown if needed) and mark run completed."""
    final_rep = final_state.get("final_report", {})
    saved_rep_id: Optional[str] = None
    if final_rep:
        md_content = final_rep.get("content_markdown", "").strip()
        if not md_content:
            try:
                rep_data = dict(final_rep)
                rep_data.setdefault("project_id", run.project_id)
                rep_data.setdefault("title", default_title)
                rep_data.setdefault("abstract", "")
                rep_data.setdefault("introduction", "")
                rep_data.setdefault("comparative_analysis", "")
                rep_data.setdefault("limitations", "")
                md_content = ReportExporter.to_markdown(ResearchReport.model_validate(rep_data))
            except Exception:
                md_content = f"# {final_rep.get('title', default_title)}\n\n{final_rep.get('abstract', '')}"
        saved_rep = DatabaseService.save_report(
            project_id=run.project_id,
            run_id=run.id,
            title=final_rep.get("title") or default_title,
            report_dict=final_rep,
            markdown_content=md_content,
        )
        saved_rep_id = saved_rep.id
    DatabaseService.update_run_status(
        run_id=run.id,
        status="completed",
        current_phase="report_synthesized",
        papers_count=len(final_state.get("selected_papers", [])),
        evidence_count=len(final_state.get("extracted_evidence", [])),
    )
    return saved_rep_id


# ---------------------------------------------------------------------------
# Sidebar UI
# ---------------------------------------------------------------------------
st.sidebar.title("🔬 MAS-RA")
st.sidebar.caption("Autonomous AI Literature Review Assistant")


def on_sidebar_nav_change():
    st.session_state.menu = st.session_state.sidebar_nav_radio


if st.session_state.get("_pending_nav") in MENU_OPTIONS:
    _target_menu = st.session_state.pop("_pending_nav")
    st.session_state.menu = _target_menu
    st.session_state.sidebar_nav_radio = _target_menu

selected_nav = st.sidebar.radio(
    "Navigation",
    MENU_OPTIONS,
    key="sidebar_nav_radio",
    on_change=on_sidebar_nav_change,
)

st.sidebar.divider()

# System Metrics
all_projects = DatabaseService.list_projects()
all_runs = DatabaseService.list_runs()
all_reports = DatabaseService.list_reports()

st.sidebar.markdown("### Workspace Overview")
col_s1, col_s2, col_s3 = st.sidebar.columns(3)
col_s1.metric("Projects", len(all_projects))
col_s2.metric("Runs", len(all_runs))
col_s3.metric("Reports", len(all_reports))

# Active Context Card
active_run_id = st.session_state.get("active_run_id")
active_run = DatabaseService.get_run(active_run_id) if active_run_id else None
active_project = DatabaseService.get_project(active_run.project_id) if active_run else None

if active_run and active_project:
    st.sidebar.divider()
    st.sidebar.markdown("### Active Context")
    st.sidebar.info(
        f"**Project**: {active_project.title[:30]}...\n\n"
        f"**Run**: `{active_run.id[:8]}` ({active_run.status.upper()})"
    )


# ---------------------------------------------------------------------------
# View 1: Projects & New Search
# ---------------------------------------------------------------------------
if st.session_state.menu == "Projects & New Search":
    st.title("📚 Research Projects & New Search")
    st.write("Initiate an autonomous literature review across **arXiv** and **Semantic Scholar** with multi-agent intelligence.")

    with st.expander("➕ Create New Research Project", expanded=True):
        with st.form("new_project_form"):
            title = st.text_input(
                "Project Title",
                placeholder="e.g. Multi-Agent Software Engineering Benchmarks",
                help="A concise formal title for your literature review project.",
            )
            question = st.text_area(
                "Central Research Question",
                placeholder="e.g. How do multi-agent large language model architectures coordinate software engineering benchmarks?",
                help="Formulate a specific academic research inquiry to explore.",
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                max_papers = st.slider(
                    "Target Papers",
                    min_value=1,
                    max_value=20,
                    value=3,
                    help="Target corpus size (3–5 papers recommended for fast responsive demo).",
                )
            with col2:
                start_year = st.number_input("Start Year", min_value=2000, max_value=2026, value=2020)
                end_year = st.number_input("End Year", min_value=2000, max_value=2026, value=2026)
            with col3:
                sources = st.multiselect(
                    "Academic Repositories",
                    ["arxiv", "semantic_scholar"],
                    default=["arxiv", "semantic_scholar"],
                )
                require_review = st.checkbox(
                    "Enable Human Review Checkpoint",
                    value=True,
                    help="When enabled, the pipeline pauses after evidence extraction so you can inspect citations and approve or request revisions before final report generation.",
                )

            submitted = st.form_submit_button("🚀 Create Project & Launch Run", type="primary", use_container_width=True)
            if submitted:
                if not title.strip() or not question.strip():
                    st.error("Please provide both a project title and a central research question.")
                else:
                    scope = {
                        "max_papers": max_papers,
                        "date_range_start": int(start_year),
                        "date_range_end": int(end_year),
                        "preferred_sources": sources or ["arxiv"],
                        "skip_human_review": not require_review,
                    }
                    project = DatabaseService.create_project(
                        title=title.strip(),
                        research_question=question.strip(),
                        scope=scope,
                    )
                    thread_id = f"thread-{project.id[:8]}-{int(time.time())}"
                    run = DatabaseService.create_run(
                        project_id=project.id,
                        thread_id=thread_id,
                        scope_override=scope,
                    )
                    st.success(f"Project '{project.title}' created! Run `{run.id[:8]}` initialized.")
                    navigate_to("Active Run Monitor", run_id=run.id, project_id=project.id)

    st.subheader(f"Existing Projects ({len(all_projects)})")
    if not all_projects:
        st.info("No research projects created yet. Use the form above to start your first project.")
    else:
        for p in all_projects:
            with st.container(border=True):
                col_p1, col_p2 = st.columns([3, 1])
                with col_p1:
                    st.markdown(f"#### {p.title}")
                    st.caption(f"Created: {p.created_at.strftime('%Y-%m-%d %H:%M')} | Status: `{p.status.upper()}` | ID: `{p.id[:8]}`")
                    st.write(p.research_question)

                with col_p2:
                    p_runs = [r for r in all_runs if r.project_id == p.id]
                    p_reports = [rep for rep in all_reports if rep.project_id == p.id]
                    latest_run = p_runs[0] if p_runs else None

                    if latest_run:
                        if st.button("⚡ Open in Monitor", key=f"open_mon_{p.id}", use_container_width=True):
                            navigate_to("Active Run Monitor", run_id=latest_run.id, project_id=p.id)
                    else:
                        if st.button("➕ Start First Run", key=f"start_run_{p.id}", use_container_width=True):
                            thread_id = f"thread-{p.id[:8]}-{int(time.time())}"
                            scope = json.loads(p.scope_json or "{}")
                            new_run = DatabaseService.create_run(project_id=p.id, thread_id=thread_id, scope_override=scope)
                            navigate_to("Active Run Monitor", run_id=new_run.id, project_id=p.id)

                    if p_reports:
                        if st.button(f"📑 View Report ({len(p_reports)})", key=f"view_rep_{p.id}", use_container_width=True):
                            navigate_to("Report Library", project_id=p.id, report_id=p_reports[0].id)


# ---------------------------------------------------------------------------
# View 2: Active Run Monitor
# ---------------------------------------------------------------------------
elif st.session_state.menu == "Active Run Monitor":
    st.title("⚡ Active Run Monitor")

    if not all_projects:
        st.info("No projects available. Start by creating a project in 'Projects & New Search'.")
    else:
        # Determine selected project
        project_ids = [p.id for p in all_projects]
        curr_p_id = st.session_state.get("active_project_id")
        if curr_p_id not in project_ids:
            curr_p_id = project_ids[0]

        col_sel1, col_sel2, col_sel3 = st.columns([2, 2, 1])

        with col_sel1:
            sel_project = st.selectbox(
                "Select Project",
                all_projects,
                index=project_ids.index(curr_p_id),
                format_func=lambda p: f"{p.title} ({p.created_at.strftime('%m/%d %H:%M')})",
            )
            if sel_project.id != curr_p_id:
                st.session_state.active_project_id = sel_project.id
                st.session_state.active_run_id = None
                st.rerun()

        # Runs for this project
        project_runs = [r for r in all_runs if r.project_id == sel_project.id]

        with col_sel2:
            if not project_runs:
                st.selectbox("Select Run", ["No runs yet for this project"], disabled=True)
                selected_run = None
            else:
                run_ids = [r.id for r in project_runs]
                curr_r_id = st.session_state.get("active_run_id")
                r_idx = run_ids.index(curr_r_id) if curr_r_id in run_ids else 0
                selected_run = st.selectbox(
                    "Select Run",
                    project_runs,
                    index=r_idx,
                    format_func=lambda r: f"Run #{r.id[:8]} - {r.status.upper()} (Phase: {r.current_phase})",
                )
                if selected_run and selected_run.id != curr_r_id:
                    st.session_state.active_run_id = selected_run.id

        with col_sel3:
            st.write("")
            st.write("")
            if st.button("➕ Launch New Run", use_container_width=True):
                thread_id = f"thread-{sel_project.id[:8]}-{int(time.time())}"
                scope = json.loads(sel_project.scope_json or "{}")
                fresh_run = DatabaseService.create_run(
                    project_id=sel_project.id,
                    thread_id=thread_id,
                    scope_override=scope,
                )
                navigate_to("Active Run Monitor", run_id=fresh_run.id, project_id=sel_project.id)

        st.divider()

        if not selected_run:
            st.info(f"No runs exist for '{sel_project.title}' yet. Click '➕ Launch New Run' above to create one.")
        else:
            run = DatabaseService.get_run(selected_run.id) or selected_run

            # Inquiry Header Card
            with st.container(border=True):
                st.markdown(f"### Research Inquiry: *{sel_project.research_question}*")
                st.caption(f"Project: **{sel_project.title}** | Run ID: `{run.id}` | Thread: `{run.thread_id}`")

            # Metrics Row
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Status", run.status.upper())
            col_m2.metric("Current Phase", run.current_phase.replace("_", " ").title())
            col_m3.metric("Harvested Papers", run.papers_count)
            col_m4.metric("Extracted Evidence", run.evidence_count)

            st.write("")

            # Action States
            if run.status in ["queued", "running"]:
                st.markdown("#### Ready to Execute Autonomous Research Workflow")
                st.caption("The graph will orchestrate the Planner Agent, parallel Search Workers, streaming PDF Retriever, Evidence Extractor, Literature Analyst, Critic, and Citation Verifier.")

                if st.button("🚀 Execute Autonomous Pipeline", type="primary", use_container_width=True):
                    with st.status("Executing multi-agent research graph...", expanded=True) as status_box:
                        graph = get_graph()
                        config = {"configurable": {"thread_id": run.thread_id}}
                        initial_state = {
                            "project_id": run.project_id,
                            "research_question": sel_project.research_question,
                            "scope": json.loads(run.scope_json or "{}"),
                        }

                        try:
                            DatabaseService.update_run_status(run_id=run.id, status="running", current_phase="executing")
                            st.write("📋 **Planner Agent**: Decomposing research inquiry into orthogonal search tasks...")

                            # Stream nodes live as they execute
                            _stream_graph_updates(graph, initial_state, config)

                            snapshot = graph.get_state(config)
                            final_state = snapshot.values if snapshot else {}

                            # Check if paused at Human Review interrupt checkpoint
                            if snapshot.next:
                                st.write("🛡️ **Checkpoint Interrupt**: Execution safely paused for Human-in-the-Loop review.")
                                status_box.update(label="Paused at Human Review Checkpoint!", state="complete")
                                DatabaseService.update_run_status(
                                    run_id=run.id,
                                    status="waiting_for_review",
                                    current_phase="human_review",
                                    papers_count=len(final_state.get("selected_papers", [])),
                                    evidence_count=len(final_state.get("extracted_evidence", [])),
                                )
                                time.sleep(0.5)
                                navigate_to("Human Review Checkpoint", run_id=run.id, project_id=sel_project.id)
                            else:
                                status_box.update(label="Research Run Completed Successfully!", state="complete")
                                rep_id = _persist_completed_run(run, sel_project.title, final_state)
                                time.sleep(0.5)
                                navigate_to("Report Library", run_id=run.id, project_id=sel_project.id, report_id=rep_id)

                        except Exception as e:
                            status_box.update(label=f"Execution error: {e}", state="error")
                            st.error(f"Execution failed: {e}")
                            DatabaseService.update_run_status(run_id=run.id, status="failed", error_message=str(e))

            elif run.status == "waiting_for_review":
                st.warning("⚠️ **Human Review Required**: This run has gathered papers, extracted evidence, and evaluated coverage. It is paused at the checkpoint awaiting your review.")
                col_btn1, col_btn2 = st.columns([2, 1])
                with col_btn1:
                    if st.button("🛡️ Open Human Review Panel (Approve / Request Revision)", type="primary", use_container_width=True):
                        navigate_to("Human Review Checkpoint", run_id=run.id, project_id=sel_project.id)

            elif run.status == "completed":
                st.success("✅ **Run Completed**: Literature review has been fully synthesized with citation verification.")
                p_reports = [rep for rep in all_reports if rep.run_id == run.id]
                rep_id = p_reports[0].id if p_reports else None
                if st.button("📑 Read & Download Synthesized Report", type="primary", use_container_width=True):
                    navigate_to("Report Library", run_id=run.id, project_id=sel_project.id, report_id=rep_id)

            elif run.status == "failed":
                st.error(f"❌ **Run Failed**: {run.error_message}")
                if st.button("🔄 Restart Run", use_container_width=True):
                    new_thread = f"thread-{sel_project.id[:8]}-{int(time.time())}"
                    DatabaseService.update_run_status(
                        run_id=run.id,
                        status="queued",
                        current_phase="restarting",
                        error_message=None,
                        thread_id=new_thread,
                    )
                    st.rerun()


# ---------------------------------------------------------------------------
# View 3: Human Review Checkpoint
# ---------------------------------------------------------------------------
elif st.session_state.menu == "Human Review Checkpoint":
    st.title("🛡️ Human-in-the-Loop Review Checkpoint")
    st.write("Inspect gathered literature provenance, extracted verbatim evidence, critic quality score, and citation grounding checks before synthesis.")

    waiting_runs = [r for r in all_runs if r.status == "waiting_for_review"]

    if not waiting_runs:
        st.info("No runs are currently waiting for human review.")
        st.write("To test the Human Review Checkpoint:")
        st.markdown(
            "1. Go to **Projects & New Search**.\n"
            "2. Make sure **'Enable Human Review Checkpoint'** is checked.\n"
            "3. Click **'Create Project & Launch Run'**, then execute the pipeline."
        )
        if st.button("⚡ Go to Active Run Monitor"):
            navigate_to("Active Run Monitor")
    else:
        # Select run under review
        waiting_run_ids = [r.id for r in waiting_runs]
        curr_r_id = st.session_state.get("active_run_id")
        def_idx = waiting_run_ids.index(curr_r_id) if curr_r_id in waiting_run_ids else 0

        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            sel_run = st.selectbox(
                "Select Run Awaiting Review",
                waiting_runs,
                index=def_idx,
                format_func=lambda r: f"Run #{r.id[:8]} - Thread `{r.thread_id}` - Created {r.created_at.strftime('%H:%M:%S')}",
            )
            st.session_state.active_run_id = sel_run.id

        run = sel_run
        project = DatabaseService.get_project(run.project_id)
        p_question = project.research_question if project else "Autonomous literature review"
        p_title = project.title if project else "Literature Review"

        # Load graph and snapshot
        graph = get_graph()
        config = {"configurable": {"thread_id": run.thread_id}}
        snapshot = graph.get_state(config)

        # Extract review package
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

        # Fallback to constructing preview from snapshot state values if needed
        if not pkg_data and isinstance(snapshot.values, dict) and snapshot.values:
            papers = snapshot.values.get("selected_papers", [])
            evidence = snapshot.values.get("extracted_evidence", [])
            critique = snapshot.values.get("critique", {})
            citations = snapshot.values.get("verified_citations", [])
            pkg_data = {
                "research_question": snapshot.values.get("research_question", p_question),
                "objective": snapshot.values.get("research_plan", {}).get("objective", "Autonomous literature synthesis"),
                "selected_papers_count": len(papers),
                "papers_summary": [
                    {"paper_id": p.get("paper_id", ""), "title": p.get("title", ""), "year": p.get("year", ""), "doi": p.get("doi", "")}
                    for p in papers
                ],
                "evidence_count": len(evidence),
                "key_evidence": evidence[:8],
                "critique_score": critique.get("quality_score", 1.0),
                "missing_topics": critique.get("missing_topics", []),
                "citation_checks": citations,
            }

        if not pkg_data and not snapshot.values and not snapshot.next:
            st.warning("⚠️ **Thread Checkpoint Not in Active Memory**: This run was initiated in a previous server session or the memory checkpointer was reset.")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("⚡ Relaunch Run in Active Monitor", type="primary", use_container_width=True):
                    new_thread = f"thread-{run.project_id[:8]}-{int(time.time())}"
                    DatabaseService.update_run_status(
                        run_id=run.id,
                        status="queued",
                        current_phase="restarting",
                        thread_id=new_thread,
                    )
                    navigate_to("Active Run Monitor", run_id=run.id, project_id=run.project_id)
            with col_c2:
                if st.button("➕ Start Fresh Run for this Project", use_container_width=True):
                    new_thread = f"thread-{run.project_id[:8]}-{int(time.time())}"
                    scope = json.loads(project.scope_json or "{}") if project else {}
                    fresh_run = DatabaseService.create_run(project_id=run.project_id, thread_id=new_thread, scope_override=scope)
                    navigate_to("Active Run Monitor", run_id=fresh_run.id, project_id=run.project_id)
        elif pkg_data:
            with st.container(border=True):
                st.markdown(f"### Research Question: *{pkg_data.get('research_question')}*")
                st.caption(f"Objective: **{pkg_data.get('objective')}**")

            # Metrics
            col_k1, col_k2, col_k3 = st.columns(3)
            col_k1.metric("Harvested Papers", pkg_data.get("selected_papers_count", 0))
            col_k2.metric("Extracted Evidence Claims", pkg_data.get("evidence_count", 0))
            crit_score = pkg_data.get("critique_score", 1.0)
            col_k3.metric("Critic Quality Rating", f"{crit_score:.2f} / 1.00")

            # Tabbed Sections
            tab_papers, tab_evidence, tab_critique, tab_citations = st.tabs([
                "📄 Harvested Literature",
                "🔍 Grounded Evidence Passages",
                "⚖️ Thematic & Quality Audit",
                "✅ Citation & DOI Grounding",
            ])

            with tab_papers:
                papers = pkg_data.get("papers_summary", [])
                if papers:
                    for idx, p in enumerate(papers, 1):
                        with st.container(border=True):
                            st.markdown(f"**{idx}. {p.get('title', 'Untitled')}** ({p.get('year', 'N/A')})")
                            doi_info = f"DOI: `{p.get('doi')}` | " if p.get("doi") else ""
                            st.caption(f"{doi_info}Paper ID: `{p.get('paper_id')}`")
                else:
                    st.info("No papers summary found.")

            with tab_evidence:
                evidence = pkg_data.get("key_evidence", [])
                if evidence:
                    for idx, ev in enumerate(evidence, 1):
                        with st.container(border=True):
                            st.markdown(f"**Claim {idx}: {ev.get('claim')}**")
                            st.info(f"\"{ev.get('supporting_passage', '')}\"")
                            st.caption(f"Scope: `{ev.get('content_scope', 'abstract_only')}` | Paper ID: `{ev.get('paper_id')}`")
                else:
                    st.info("No evidence excerpts extracted yet.")

            with tab_critique:
                missing = pkg_data.get("missing_topics", [])
                if missing:
                    st.warning(f"**Critic Flagged Gaps / Missing Subtopics**: {', '.join(missing)}")
                else:
                    st.success("Critic reported sufficient thematic coverage across all research plan tasks.")

            with tab_citations:
                citations = pkg_data.get("citation_checks", [])
                if citations:
                    for c in citations:
                        doi_icon = "✅ Verified" if c.get("doi_valid") else "⚠️ Unresolved"
                        claim_icon = "✅ Supported" if c.get("claim_supported") else "❌ Unsupported"
                        notes = f" — *{c.get('notes')}*" if c.get("notes") else ""
                        st.markdown(f"- **Paper `{c.get('paper_id')[:16]}`**: DOI: {doi_icon} | Grounding: {claim_icon}{notes}")
                else:
                    st.info("Citation verification checks verified.")

            st.divider()

            # Human Decision Controls
            st.subheader("Submit Review Decision")
            col_dec1, col_dec2, col_dec3 = st.columns([2, 2, 1])

            with col_dec1:
                if st.button("✅ Approve & Synthesize Final Report", type="primary", use_container_width=True):
                    with st.status("Resuming graph & synthesizing final academic report...", expanded=True) as approve_status:
                        try:
                            cmd = Command(resume={"action": "approve"})
                            _stream_graph_updates(graph, cmd, config)
                            snap_done = graph.get_state(config)
                            final_state = snap_done.values if snap_done else {}
                            rep_id = _persist_completed_run(run, f"Systematic Review: {p_title}", final_state)
                            approve_status.update(label="Approved! Academic literature review synthesized.", state="complete")
                            navigate_to("Report Library", run_id=run.id, project_id=run.project_id, report_id=rep_id)
                        except Exception as e:
                            approve_status.update(label=f"Approval error: {e}", state="error")
                            st.error(f"Approval failed: {e}")

            with col_dec2:
                rev_notes = st.text_input("Revision Guidance (Optional)", placeholder="e.g. Include more studies on benchmark validity")
                if st.button("🔄 Request Revision Cycle", use_container_width=True):
                    with st.status("Dispatching revision tasks to search workers...", expanded=True) as rev_status:
                        try:
                            cmd = Command(resume={"action": "request_revision", "feedback": rev_notes})
                            _stream_graph_updates(graph, cmd, config)
                            snapshot = graph.get_state(config)
                            final_state = snapshot.values if snapshot else {}
                            if snapshot.next:
                                DatabaseService.update_run_status(
                                    run_id=run.id,
                                    status="waiting_for_review",
                                    current_phase="human_review",
                                    papers_count=len(final_state.get("selected_papers", [])),
                                    evidence_count=len(final_state.get("extracted_evidence", [])),
                                )
                                rev_status.update(label="Revision tasks completed. New review package ready.", state="complete")
                                st.rerun()
                            else:
                                rep_id = _persist_completed_run(run, f"Systematic Review: {p_title}", final_state)
                                rev_status.update(label="Revisions completed and report synthesized.", state="complete")
                                navigate_to("Report Library", run_id=run.id, project_id=run.project_id, report_id=rep_id)
                        except Exception as e:
                            rev_status.update(label=f"Revision dispatch failed: {e}", state="error")
                            st.error(f"Revision dispatch failed: {e}")

            with col_dec3:
                if st.button("❌ Reject Run", use_container_width=True):
                    try:
                        cmd = Command(resume={"action": "reject"})
                        graph.invoke(cmd, config=config)
                    except Exception:
                        pass
                    DatabaseService.update_run_status(run_id=run.id, status="rejected", current_phase="rejected")
                    st.error("Run rejected.")
                    navigate_to("Active Run Monitor", run_id=run.id, project_id=run.project_id)


# ---------------------------------------------------------------------------
# View 4: Report Library
# ---------------------------------------------------------------------------
elif st.session_state.menu == "Report Library":
    st.title("📑 Literature Review Library")
    st.write("Inspect, read, and export publication-grade academic literature reviews generated by the multi-agent system.")

    if not all_reports:
        st.info("No generated literature reviews found yet.")
        st.write("To generate your first report:")
        st.markdown(
            "1. Navigate to **Projects & New Search**.\n"
            "2. Create a project and launch a research run.\n"
            "3. Once completed or approved, your report will be displayed here."
        )
        if st.button("🚀 Start a New Research Project"):
            navigate_to("Projects & New Search")
    else:
        # Determine selected report
        rep_ids = [r.id for r in all_reports]
        curr_rep_id = st.session_state.get("active_report_id")

        # Match against active_run_id if active_report_id not set
        if curr_rep_id not in rep_ids:
            run_id = st.session_state.get("active_run_id")
            for r in all_reports:
                if r.run_id == run_id:
                    curr_rep_id = r.id
                    break

        r_idx = rep_ids.index(curr_rep_id) if curr_rep_id in rep_ids else 0

        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            selected_report = st.selectbox(
                "Select Academic Report",
                all_reports,
                index=r_idx,
                format_func=lambda r: f"{r.title} — {r.created_at.strftime('%Y-%m-%d %H:%M')}",
            )
            st.session_state.active_report_id = selected_report.id

        with col_r2:
            st.write("")
            st.write("")
            # Delete or re-run shortcut
            p = DatabaseService.get_project(selected_report.project_id)
            if p and st.button("⚡ Open in Monitor", key="rep_open_mon", use_container_width=True):
                navigate_to("Active Run Monitor", run_id=selected_report.run_id, project_id=p.id)

        st.divider()

        # Report Header Card
        with st.container(border=True):
            st.markdown(f"## {selected_report.title}")
            proj = DatabaseService.get_project(selected_report.project_id)
            p_title = proj.title if proj else "Project"
            st.caption(f"Project: **{p_title}** | Generated: {selected_report.created_at.strftime('%Y-%m-%d %H:%M')} | Report ID: `{selected_report.id}`")

            # Build resilient objects for display and export
            try:
                rep_obj = _build_resilient_report_obj(selected_report)
            except Exception:
                rep_obj = None

            rendered_md = (selected_report.markdown_content or "").strip()
            if not rendered_md and rep_obj is not None:
                rendered_md = ReportExporter.to_markdown(rep_obj)

            # Download Action Buttons
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    "📥 Download Markdown (.md)",
                    data=rendered_md,
                    file_name=f"literature_review_{selected_report.id[:8]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_d2:
                try:
                    if rep_obj is None:
                        rep_obj = _build_resilient_report_obj(selected_report)
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

        # Render Markdown Content
        if rendered_md:
            st.markdown(rendered_md)
        else:
            st.warning("This report record has no rendered markdown content yet.")
