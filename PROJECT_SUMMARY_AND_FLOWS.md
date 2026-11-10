# MAS-RA: Complete Project Summary & Visual Flows

**Project:** Autonomous AI Research & Literature Review Assistant (MAS-RA)  
**Stack:** Python 3.12, LangGraph, LangChain / OpenAI (`gpt-4o-mini`), FastAPI, Streamlit, SQLAlchemy, SQLite / PostgreSQL (`pgvector`), ReportLab, `pypdf`  
**Verification Status:** 54/54 automated tests passing (`pytest -q`), Streamlit UI end-to-end flow verified, FastAPI REST service verified

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [High-Level System Architecture Flow](#2-high-level-system-architecture-flow)
3. [End-to-End LangGraph Execution Flow](#3-end-to-end-langgraph-execution-flow)
4. [Human-in-the-Loop (HITL) & Persistent Checkpoint Sequence](#4-human-in-the-loop-hitl--persistent-checkpoint-sequence)
5. [Streamlit Dashboard User Journey](#5-streamlit-dashboard-user-journey)
6. [Database & Checkpoint Storage Schema](#6-database--checkpoint-storage-schema)
7. [Component & Module Reference](#7-component--module-reference)
   - [A. Multi-Agent Layer (`app/agents/`)](#a-multi-agent-layer-appagents)
   - [B. Academic Tools & Export Engine (`app/tools/`)](#b-academic-tools--export-engine-apptools)
   - [C. LangGraph State & Workflow (`app/graph/`)](#c-langgraph-state--workflow-appgraph)
   - [D. FastAPI Backend (`app/api/`)](#d-fastapi-backend-appapi)
   - [E. Persistence & Checkpointing (`app/database/`)](#e-persistence--checkpointing-appdatabase)
   - [F. Evaluation & Ablation Suite (`app/evaluation/`)](#f-evaluation--ablation-suite-appevaluation)
   - [G. Scripts, Deployment & Presentation Assets](#g-scripts-deployment--presentation-assets)
8. [How to Run the Application](#8-how-to-run-the-application)

---

## 1. Project Overview

MAS-RA automates systematic academic literature reviews through coordinated specialized AI agents rather than single-prompt LLM calls. Every empirical claim extracted from arXiv and Semantic Scholar literature is anchored to a verbatim source passage (`supporting_passage`), tagged with its provenance (`full_text` vs. `abstract_only`), audited by an adversarial critic with bounded self-refinement loops, verified against DOI/URL/grounding rules, optionally reviewed by a human at a persistent checkpoint interrupt, and compiled into Markdown and styled PDF reports.

---

## 2. High-Level System Architecture Flow

```mermaid
flowchart TD
    User(["Researcher / User"]) --> UI["Streamlit Dashboard (streamlit_app/app.py :8501)"]
    User --> API["FastAPI REST Service (app/api/app.py :8000)"]
    User --> CLI["CLI Runner (scripts/run_research_cli.py)"]

    UI --> Graph["LangGraph Workflow Engine (app/graph/workflow.py)"]
    API --> Graph
    CLI --> Graph

    subgraph Agents ["Multi-Agent Layer (app/agents/)"]
        P["PlannerAgent"]
        E["ExtractorAgent"]
        A["AnalystAgent"]
        C["CriticAgent"]
        W["ReportWriterAgent"]
    end

    subgraph Tools ["Academic Tools Layer (app/tools/)"]
        AX["ArxivSearchTool"]
        S2["SemanticScholarTool"]
        DD["PaperDeduplicator"]
        PR["PaperRetriever (15MB / Timeout Guard)"]
        PP["PDFParser (pypdf)"]
        CV["CitationVerifier"]
        RE["ReportExporter (Markdown & ReportLab PDF)"]
    end

    Graph --> Agents
    Graph --> Tools

    Graph --> CP["Checkpointer Factory (app/database/checkpointer.py)"]
    UI --> DB["DatabaseService (app/database/service.py)"]
    API --> DB

    CP -->|"Postgres reachable :5432"| PG[("PostgreSQL + pgvector")]
    CP -->|"Fallback (Stdlib sqlite3)"| CPDB[("research_checkpoints.db")]
    DB -->|"Postgres reachable :5432"| PG
    DB -->|"Fallback (Local SQLite)"| RDB[("research.db")]
```

---

## 3. End-to-End LangGraph Execution Flow

Implemented in [`app/graph/workflow.py`](app/graph/workflow.py) and [`app/graph/nodes.py`](app/graph/nodes.py) over shared [`ResearchState`](app/graph/state.py):

```mermaid
flowchart TD
    StartNode(["START"]) --> Planner["planner (PlannerAgent -> 3 to 5 tasks)"]

    Planner -->|"dispatch_search_tasks (Send API)"| Worker1["search_worker 1 (arXiv & S2)"]
    Planner -->|"dispatch_search_tasks (Send API)"| Worker2["search_worker 2 (arXiv & S2)"]
    Planner -->|"dispatch_search_tasks (Send API)"| WorkerN["search_worker N (arXiv & S2)"]

    Worker1 --> Dedup["deduplicate_and_rank (PaperDeduplicator + Year/Citation Sort)"]
    Worker2 --> Dedup
    WorkerN --> Dedup

    Dedup --> Retrieve["retrieve_content (Skips already-parsed IDs -> PDF or Abstract Fallback)"]
    Retrieve --> Extract["extract_evidence (Skips already-analyzed IDs -> Verbatim Claims)"]
    Extract --> Analyze["analyze_literature (AnalystAgent -> Themes, Comparisons, Gaps)"]
    Analyze --> Critique["critique (CriticAgent -> Quality Score 0.0 to 1.0)"]

    Critique -->|"needs_revision=True and revision_count < max_revisions"| PrepRev["prepare_revision (revision_count + 1)"]
    PrepRev -->|"dispatch_revision_tasks (Send API)"| Worker1

    Critique -->|"Score sufficient or budget exhausted"| Verify["verify_citations (CitationVerifier -> DOI Regex, URLs, Grounding)"]
    Verify --> HITL{"human_review (skip_human_review?)"}

    HITL -->|"skip_human_review=False: interrupt()"| WaitUser["Pause & Save ReviewPackage Checkpoint"]
    WaitUser -->|"Command resume: action=approve"| Writer["synthesize_summary (ReportWriterAgent -> Markdown & JSON)"]
    WaitUser -->|"Command resume: action=request_revision"| PrepHumanRev["prepare_human_revision (Human Feedback Query)"]
    WaitUser -->|"Command resume: action=reject"| Reject["mark_rejected (Terminate cleanly)"]

    HITL -->|"skip_human_review=True"| Writer
    PrepHumanRev -->|"dispatch_human_revision_tasks (Send API)"| Worker1

    Writer --> EndNode(["END"])
    Reject --> EndNode
```

---

## 4. Human-in-the-Loop (HITL) & Persistent Checkpoint Sequence

Backed by [`SQLiteMemorySaver`](app/database/checkpointer.py) (`research_checkpoints.db`), allowing paused `human_review` runs to survive server restarts without binary PostgreSQL driver dependencies:

```mermaid
sequenceDiagram
    actor Researcher
    participant UI as Streamlit UI / FastAPI
    participant Graph as LangGraph Engine
    participant CP as SQLiteMemorySaver (research_checkpoints.db)
    participant DB as DatabaseService (research.db)

    Researcher->>UI: Launch Run (skip_human_review = False)
    UI->>DB: Create ResearchRunModel (status = queued -> running)
    UI->>Graph: stream(initial_state, thread_id)
    Graph->>CP: Persist node checkpoints (cp_storage, cp_blobs, cp_writes)
    Graph->>Graph: Reach human_review -> call interrupt(review_package)
    Graph-->>UI: Stop streaming (snapshot.next = human_review)
    UI->>DB: Update run (status = waiting_for_review, papers, evidence)

    Note over Researcher,CP: Even if server restarts here, checkpoint remains in SQLite

    Researcher->>UI: Inspect Tabs & Click Approve (or Request Revision / Reject)
    UI->>Graph: stream(Command(resume={"action": "approve"}), thread_id)
    Graph->>CP: Load interrupted checkpoint state
    Graph->>Graph: Execute synthesize_summary (ReportWriterAgent)
    Graph-->>UI: Final state with final_report & content_markdown
    UI->>DB: save_report() & mark run completed
    UI-->>Researcher: Redirect to Report Library (Markdown & PDF Export)
```

---

## 5. Streamlit Dashboard User Journey

Implemented in [`streamlit_app/app.py`](streamlit_app/app.py) with `@st.cache_resource` shared graph compilation, synchronized `_pending_nav` tab redirection, real-time node streaming, and native Streamlit containers:

```mermaid
flowchart LR
    V1["1. Projects & New Search\n- Create Project & Scope\n- Target Papers (1 to 20)\n- Year Range & Sources\n- Toggle Human Review"]
    V2["2. Active Run Monitor\n- Project & Run Selectors\n- Launch New / Relaunch Run\n- Live Agent Node Streaming\n- Status & Count Metrics"]
    V3["3. Human Review Checkpoint\n- Tab: Harvested Literature\n- Tab: Verbatim Evidence\n- Tab: Critic Quality Audit\n- Tab: Citation Checks\n- Approve / Revise / Reject"]
    V4["4. Report Library\n- Academic Report Selector\n- Full Markdown Renderer\n- Download Markdown (.md)\n- Download Styled PDF (.pdf)"]

    V1 -->|"Create Project & Launch Run"| V2
    V2 -->|"Pause at Checkpoint"| V3
    V2 -->|"Auto-Complete (Skip HITL)"| V4
    V3 -->|"Approve & Synthesize"| V4
    V3 -->|"Request Revision"| V2
```

---

## 6. Database & Checkpoint Storage Schema

Domain records persist via SQLAlchemy ORM in [`app/database/models.py`](app/database/models.py) (`research.db` or PostgreSQL), while LangGraph execution checkpoints persist in `research_checkpoints.db` (or `PostgresSaver`):

```mermaid
erDiagram
    PROJECTS ||--o{ RESEARCH_RUNS : "has many"
    RESEARCH_RUNS ||--o{ REPORTS : "generates"

    PROJECTS {
        string id PK
        string title
        text research_question
        text scope_json
        string status
        datetime created_at
    }

    RESEARCH_RUNS {
        string id PK
        string project_id FK
        string thread_id UK
        string status
        string current_phase
        int papers_count
        int evidence_count
        text scope_json
        text error_message
    }

    REPORTS {
        string id PK
        string project_id FK
        string run_id FK
        string title
        text report_json
        text markdown_content
        datetime created_at
    }

    CP_STORAGE {
        string thread_id PK
        string checkpoint_ns PK
        string checkpoint_id PK
        blob cp_bytes
        blob meta_bytes
        string parent_id
    }

    CP_WRITES {
        string thread_id PK
        string checkpoint_ns PK
        string checkpoint_id PK
        string task_id PK
        int write_idx PK
        blob val_bytes
    }

    CP_BLOBS {
        string thread_id PK
        string checkpoint_ns PK
        string channel PK
        string version_json PK
        blob val_bytes
    }
```

---

## 7. Component & Module Reference

### A. Multi-Agent Layer (`app/agents/`)

| Agent | File | Responsibility | Output Schema / Fallback |
| :--- | :--- | :--- | :--- |
| **PlannerAgent** | [`app/agents/planner.py`](app/agents/planner.py) | Decomposes inquiry into 3 to 5 orthogonal search tasks (`function_calling`) | `ResearchPlan` (`_heuristic_fallback_plan`) |
| **ExtractorAgent** | [`app/agents/extractor.py`](app/agents/extractor.py) | Extracts methods, benchmarks, and verbatim grounded evidence items | `PaperAnalysis` + `List[Evidence]` (`_heuristic_fallback_extraction`) |
| **AnalystAgent** | [`app/agents/analyst.py`](app/agents/analyst.py) | Synthesizes themes, cross-paper comparisons, disagreements, and gaps | `ResearchSynthesis` (`_heuristic_fallback_synthesis`) |
| **CriticAgent** | [`app/agents/critic.py`](app/agents/critic.py) | Audits thematic coverage (score `0.0-1.0`) and triggers bounded revision tasks | `Critique` (`_heuristic_fallback_critique`) |
| **ReportWriterAgent** | [`app/agents/writer.py`](app/agents/writer.py) | Authors publication-grade literature review with references and audit checks | `ResearchReport` (`_write_deterministic`) |

### B. Academic Tools & Export Engine (`app/tools/`)

| Tool | File | Function |
| :--- | :--- | :--- |
| **ArxivSearchTool** | [`app/tools/arxiv_search.py`](app/tools/arxiv_search.py) | Queries arXiv Atom API with polite rate-limit delay and year filtering |
| **SemanticScholarTool** | [`app/tools/semantic_scholar.py`](app/tools/semantic_scholar.py) | Queries Semantic Scholar Graph API with exponential backoff on HTTP `429` |
| **PaperDeduplicator** | [`app/tools/paper_dedup.py`](app/tools/paper_dedup.py) | Deduplicates by normalized DOI, provider ID, title, and Jaccard similarity (`> 0.85`), merging provider sources |
| **PaperRetriever** | [`app/tools/paper_retriever.py`](app/tools/paper_retriever.py) | Streams PDFs with 15 MB ceiling, wall-clock timeout deadline, and `%PDF` header check |
| **PDFParser** | [`app/tools/pdf_parser.py`](app/tools/pdf_parser.py) | Parses full text via `pypdf`, cleans ligatures/hyphens, segments sections, falls back to `abstract_only` / `metadata_only` |
| **CitationVerifier** | [`app/tools/citation_verifier.py`](app/tools/citation_verifier.py) | Validates DOI regex syntax, verifies source URLs, and confirms evidence grounding per paper |
| **ReportExporter** | [`app/tools/report_exporter.py`](app/tools/report_exporter.py) | Formats Markdown and XML-escaped styled PDF documents via ReportLab |

### C. LangGraph State & Workflow (`app/graph/`)

- **State ([`app/graph/state.py`](app/graph/state.py)):** Tracks `research_plan`, `research_tasks`, `search_results` (`merge_papers_reducer`), `selected_papers`, `paper_contents` (`operator.add`), `extracted_evidence` (`operator.add`), `paper_analyses` (`operator.add`), `synthesis`, `critique`, `verified_citations`, `review_package`, `revision_count`, `final_report`, and `status`.
- **Prompts ([`app/graph/prompts.py`](app/graph/prompts.py)):** Version-controlled system and user templates for Planner, Extractor, Analyst, Critic, and Report Writer.
- **Nodes & Workflow ([`app/graph/nodes.py`](app/graph/nodes.py), [`app/graph/workflow.py`](app/graph/workflow.py)):** Handles dynamic `Send()` fan-out, skips duplicate downloads/extractions on revision loops, executes HITL `interrupt()`, and compiles the StateGraph.

### D. FastAPI Backend (`app/api/`)

Exposed in [`app/api/app.py`](app/api/app.py) and [`app/api/routes.py`](app/api/routes.py):

- **Health:** `GET /health`
- **Projects:** `POST /api/projects`, `GET /api/projects`, `GET /api/projects/{project_id}`
- **Runs:** `POST /api/projects/{project_id}/runs`, `GET /api/runs/{run_id}`
- **Artifacts & Inspection:** `GET /api/runs/{run_id}/papers`, `GET /api/runs/{run_id}/evidence`
- **Human Review:** `GET /api/runs/{run_id}/review`, `POST /api/runs/{run_id}/review`
- **Reports & Export:** `GET /api/runs/{run_id}/report`, `GET /api/runs/{run_id}/export/markdown`, `GET /api/runs/{run_id}/export/pdf`

### E. Persistence & Checkpointing (`app/database/`)

- [`app/database/models.py`](app/database/models.py): SQLAlchemy 2.0 models `ProjectModel`, `ResearchRunModel`, `ReportModel`.
- [`app/database/service.py`](app/database/service.py): `DatabaseService` repository with socket pre-check (`_is_postgres_available`), automatic fallback to SQLite (`research.db` or `MAS_LOCAL_SQLITE_URL` during tests), and `selectinload` eager loading.
- [`app/database/checkpointer.py`](app/database/checkpointer.py): `get_checkpointer()` returning `MemorySaver` in testing, `PostgresSaver` when Postgres is reachable, or persistent [`SQLiteMemorySaver`](app/database/checkpointer.py) (`research_checkpoints.db`).

### F. Evaluation & Ablation Suite (`app/evaluation/`)

- [`app/evaluation/metrics.py`](app/evaluation/metrics.py): `MetricsCalculator` computing `CitationEvaluationResult` (DOI validity, URL accessibility, claim support), `EvidenceEvaluationResult` (`full_text` vs `abstract_only` ratio, confidence), `CoverageEvaluationResult`, and `SystemBenchmarkScore`.
- [`app/evaluation/ablation_runner.py`](app/evaluation/ablation_runner.py): `AblationExperimentRunner` comparing `full_multi_agent` vs `ablation_no_critic_revisions` against [`data/evaluation/benchmark_queries.json`](data/evaluation/benchmark_queries.json).

### G. Scripts, Deployment & Presentation Assets

- **CLI Scripts (`scripts/`):**
  - [`scripts/run_research_cli.py`](scripts/run_research_cli.py): End-to-end terminal pipeline runner.
  - [`scripts/run_benchmark_evaluation.py`](scripts/run_benchmark_evaluation.py): Benchmark and ablation runner.
  - [`scripts/backup_database.py`](scripts/backup_database.py) & [`scripts/restore_database.py`](scripts/restore_database.py): JSON database backup/restore utilities.
- **Deployment & Migrations:** [`Dockerfile`](Dockerfile), [`docker-compose.yml`](docker-compose.yml), [`alembic/`](alembic/), and [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
- **Presentation Deck:** [`generate_deck.py`](generate_deck.py) and [`MAS_RA_Academic_Presentation.pptx`](MAS_RA_Academic_Presentation.pptx) (12-slide 16:9 academic presentation with embedded speaker notes).

---

## 8. How to Run the Application

```powershell
# 1. Start Streamlit Web Dashboard (http://localhost:8501)
.\.venv\Scripts\python.exe -m streamlit run streamlit_app/app.py --server.port 8501

# 2. Start FastAPI Backend (http://localhost:8000/docs)
.\.venv\Scripts\python.exe -m uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload

# 3. Run Single Research Query via CLI
.\.venv\Scripts\python.exe scripts/run_research_cli.py --question "How are multi-agent AI systems improving autonomous software engineering?" --max-papers 3

# 4. Run Automated Test Suite (Isolated from research.db)
.\.venv\Scripts\python.exe -m pytest -q
```

