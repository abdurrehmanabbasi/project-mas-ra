"""Streamlit Interactive Web Dashboard for Autonomous AI Research & Literature Review."""

import json
import os
import time
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
    if "graph" not in st.session_state:
        st.session_state.graph = create_research_graph()
    return st.session_state.graph


# Sidebar - Navigation & System Status
st.sidebar.title("🔬 Research Assistant")
st.sidebar.caption("Multi-Agent Autonomous Literature Review")

menu = st.sidebar.radio(
    "Navigation",
    ["Projects & New Search", "Active Run Monitor", "Human Review Checkpoint", "Report Library"],
)

st.sidebar.divider()
st.sidebar.markdown("### System Metrics")
all_projects = DatabaseService.list_projects()
st.sidebar.metric("Total Projects", len(all_projects))


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
                    st.success(f"Project created! Run ID: `{run.id}` launched.")
                    st.info("Switch to 'Active Run Monitor' in the sidebar to observe execution.")

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
        runs = []
        for p in all_projects:
            for r in p.runs:
                runs.append(r)
        if runs:
            selected_run = st.selectbox("Select Existing Run", runs, format_func=lambda r: f"Run {r.id[:8]} - {r.status} ({r.current_phase})")
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
            st.markdown(f"### Researching: *{project.research_question}*")
            st.caption(f"Run ID: `{run.id}` | Thread: `{run.thread_id}` | Status: **{run.status.upper()}**")

            col1, col2, col3 = st.columns(3)
            col1.metric("Current Phase", run.current_phase)
            col2.metric("Papers Harvested", run.papers_count)
            col3.metric("Evidence Extracted", run.evidence_count)

            if run.status in ["queued", "running"]:
                if st.button("Execute Pipeline Step / Run Graph", type="primary"):
                    with st.spinner("Multi-agent graph running..."):
                        graph = get_graph_instance()
                        config = {"configurable": {"thread_id": run.thread_id}}
                        initial_state = {
                            "project_id": run.project_id,
                            "research_question": project.research_question,
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
                                st.warning("Graph execution paused for Human-in-the-Loop review!")
                                st.info("Switch to 'Human Review Checkpoint' in the sidebar to review.")
                            else:
                                final_rep = final_state.get("final_report", {})
                                if final_rep:
                                    DatabaseService.save_report(
                                        project_id=run.project_id,
                                        run_id=run.id,
                                        title=final_rep.get("title", project.title),
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
                                st.success("Research run completed successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Execution error: {e}")
                            DatabaseService.update_run_status(run_id=run.id, status="failed", error_message=str(e))

            elif run.status == "waiting_for_review":
                st.warning("⚠️ This run is waiting for human approval at the review checkpoint.")
                if st.button("Go to Human Review Panel"):
                    st.session_state.menu = "Human Review Checkpoint"
                    st.rerun()

            elif run.status == "completed":
                st.success("✅ Research synthesis completed!")
                report = DatabaseService.get_report_by_run(run.id)
                if report:
                    if st.button("View Synthesized Report"):
                        st.session_state.menu = "Report Library"
                        st.rerun()


# ---------------------------------------------------------------------------
# View 3: Human Review Checkpoint
# ---------------------------------------------------------------------------
elif menu == "Human Review Checkpoint":
    st.title("🛡️ Human-in-the-Loop Review Checkpoint")
    st.write("Inspect gathered literature, extracted evidence, critique scores, and citation checks before finalization.")

    run_id = st.session_state.get("active_run_id")
    if not run_id:
        st.info("No active run selected. Select a run waiting for review from 'Active Run Monitor'.")
    else:
        run = DatabaseService.get_run(run_id)
        if run.status != "waiting_for_review":
            st.info(f"Run status is `{run.status}` (not currently paused at review checkpoint).")
        else:
            graph = get_graph_instance()
            config = {"configurable": {"thread_id": run.thread_id}}
            snapshot = graph.get_state(config)

            # Get review package
            pkg_data = None
            for task in snapshot.tasks:
                if task.interrupts:
                    for intr in task.interrupts:
                        pkg_data = intr.value
                        break
            if not pkg_data and "review_package" in snapshot.values:
                pkg_data = snapshot.values["review_package"]

            if pkg_data:
                st.subheader(f"Inquiry: {pkg_data.get('research_question')}")
                st.caption(f"Objective: {pkg_data.get('objective')}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Selected Papers", pkg_data.get("selected_papers_count", 0))
                col2.metric("Evidence Claims", pkg_data.get("evidence_count", 0))
                col3.metric("Critic Quality Score", f"{pkg_data.get('critique_score', 1.0):.2f}")

                # Papers Summary
                with st.expander("📄 Harvested Papers Summary", expanded=True):
                    papers = pkg_data.get("papers_summary", [])
                    st.table(papers)

                # Key Evidence
                with st.expander("🔍 Key Extracted Evidence Excerpts", expanded=False):
                    evidence = pkg_data.get("key_evidence", [])
                    for ev in evidence:
                        st.markdown(f"- **{ev.get('claim')}** (Scope: `{ev.get('content_scope')}`)")
                        st.caption(f"Quote: \"{ev.get('supporting_passage')}\"")

                # Missing Topics & Citations
                missing = pkg_data.get("missing_topics", [])
                if missing:
                    st.warning(f"Critic detected missing subtopics: {', '.join(missing)}")

                # Review Decisions
                st.subheader("Submit Human Decision")
                col_app, col_rev, col_rej = st.columns(3)

                with col_app:
                    if st.button("✅ Approve & Synthesize Report", type="primary", use_container_width=True):
                        cmd = Command(resume={"action": "approve"})
                        final_state = graph.invoke(cmd, config=config)
                        final_rep = final_state.get("final_report", {})
                        if final_rep:
                            DatabaseService.save_report(
                                project_id=run.project_id,
                                run_id=run.id,
                                title=final_rep.get("title", "Synthesized Report"),
                                report_dict=final_rep,
                                markdown_content=final_rep.get("content_markdown", ""),
                            )
                        DatabaseService.update_run_status(run_id=run.id, status="completed", current_phase="report_synthesized")
                        st.success("Approved! Report synthesized.")
                        st.rerun()

                with col_rev:
                    revision_feedback = st.text_input("Revision Request Feedback", placeholder="e.g. Focus more on benchmark contamination")
                    if st.button("🔄 Request Revision Cycle", use_container_width=True):
                        cmd = Command(resume={"action": "request_revision", "feedback": revision_feedback})
                        final_state = graph.invoke(cmd, config=config)
                        snapshot = graph.get_state(config)
                        if snapshot.next:
                            DatabaseService.update_run_status(run_id=run.id, status="waiting_for_review", current_phase="human_review")
                        st.info("Revision cycle dispatched.")
                        st.rerun()

                with col_rej:
                    if st.button("❌ Reject Research Run", use_container_width=True):
                        cmd = Command(resume={"action": "reject"})
                        graph.invoke(cmd, config=config)
                        DatabaseService.update_run_status(run_id=run.id, status="rejected", current_phase="rejected")
                        st.error("Run rejected.")
                        st.rerun()


# ---------------------------------------------------------------------------
# View 4: Report Library
# ---------------------------------------------------------------------------
elif menu == "Report Library":
    st.title("📑 Literature Review Library")

    run_id = st.session_state.get("active_run_id")
    report = None
    if run_id:
        report = DatabaseService.get_report_by_run(run_id)

    if not report:
        # Check all runs with reports
        all_reports = []
        for p in all_projects:
            for r in p.runs:
                rep = DatabaseService.get_report_by_run(r.id)
                if rep:
                    all_reports.append(rep)

        if all_reports:
            sel_rep = st.selectbox("Select Report to Read", all_reports, format_func=lambda r: f"{r.title} ({r.created_at.strftime('%Y-%m-%d')})")
            report = sel_rep
        else:
            st.info("No generated reports found yet. Complete a research run to view reports here.")

    if report:
        st.subheader(report.title)
        st.caption(f"Generated: {report.created_at.strftime('%Y-%m-%d %H:%M')} | Report ID: `{report.id}`")

        # Export buttons
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥 Download Markdown (.md)",
                data=report.markdown_content,
                file_name=f"literature_review_{report.id[:8]}.md",
                mime="text/markdown",
            )
        with col_dl2:
            try:
                rep_data = json.loads(report.report_json)
                rep_obj = ResearchReport.model_validate(rep_data)
                pdf_tmp_path = os.path.join(os.environ.get("TEMP", "."), f"report_{report.id[:8]}.pdf")
                ReportExporter.export_pdf(rep_obj, pdf_tmp_path)
                with open(pdf_tmp_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    "📄 Download Styled PDF (.pdf)",
                    data=pdf_bytes,
                    file_name=f"literature_review_{report.id[:8]}.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.warning(f"PDF compilation notice: {e}")

        st.divider()
        st.markdown(report.markdown_content)

