// MAS-RA Interactive Educational App Logic

// -------------------------------------------------------------------------
// 0. Theme Switcher & Navigation Tabs
// -------------------------------------------------------------------------
const themeToggleBtn = document.getElementById("btn-theme-toggle");
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggleBtn.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
  requestAnimationFrame(drawChart);
}
themeToggleBtn.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
});

const tabBtns = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");
tabBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;
    tabBtns.forEach(b => (b.dataset.active = b === btn ? "true" : "false"));
    tabPanels.forEach(p => p.classList.toggle("hidden", p.id !== `tab-${target}`));
    if (target === "eval") {
      requestAnimationFrame(drawChart);
    }
  });
});

// -------------------------------------------------------------------------
// 1. Live LangGraph Pipeline Simulator
// -------------------------------------------------------------------------
const TOPICS = {
  se: {
    question: "How do multi-agent LLM frameworks coordinate software engineering benchmarks?",
    papers: [
      "SPEAR: Multi-Agent Smart Contract Auditing (2025)",
      "AgentBench: Evaluating LLMs as Agents (2023)"
    ],
    claim: "Multi-agent frameworks decompose repository debugging into planner, coder, and verifier roles.",
    quote: "In our evaluation on 300 software tasks, specialized coordination raised pass@1 by 24%."
  },
  health: {
    question: "How are multi-agent AI systems applied in real-time health monitoring?",
    papers: [
      "Federated Multi-Agent ECG Anomaly Detection (2024)",
      "Clinical Triage Agents via Structured Telemetry (2025)"
    ],
    claim: "Distributed monitoring agents fuse wearable telemetry with clinical reasoning while preserving privacy.",
    quote: "Multi-agent edge inference reduced false alarm rates by 31% across ICU benchmark traces."
  }
};

const NODE_INFO = {
  planner: {
    file: "app/agents/planner.py -> planner_node",
    desc: "Reads research_question and ResearchScope, calls GPT-4o-mini with function_calling to produce a ResearchPlan with 3 orthogonal subquestions and keyword queries.",
    lesson: "Narrow single queries miss half the literature; orthogonal task decomposition guarantees breadth before searching."
  },
  search_worker: {
    file: "app/graph/nodes.py -> search_worker_node",
    desc: "Dispatched dynamically via LangGraph Send() API in parallel. Each worker queries arXiv Atom API and Semantic Scholar Graph API (with HTTP 429 exponential backoff).",
    lesson: "LangGraph Send() enables true map-reduce fan-out where worker results merge back through merge_papers_reducer."
  },
  deduplicate_and_rank: {
    file: "app/tools/paper_dedup.py -> deduplicate_and_rank_node",
    desc: "Eliminates duplicates across arXiv and Semantic Scholar using DOI, provider ID, normalized titles, and Jaccard similarity > 0.85, then ranks by year and citations.",
    lesson: "Merging preserves the best abstract and multiple source URLs instead of discarding cross-provider links."
  },
  retrieve_content: {
    file: "app/tools/paper_retriever.py -> retrieve_content_node",
    desc: "Skips any paper_id already present in paper_contents, downloads open-access PDFs (15 MB max, 15s wall-clock deadline), verifies %PDF header, and parses sections via pypdf.",
    lesson: "If a PDF is paywalled or times out, it degrades cleanly to abstract_only and records provenance scope explicitly."
  },
  extract_evidence: {
    file: "app/agents/extractor.py -> extract_evidence_node",
    desc: "Skips papers already in paper_analyses, calls ExtractorAgent to pull methodology, datasets, limitations, and Evidence records requiring verbatim supporting_passage quotes.",
    lesson: "Enforcing verbatim quotes + provenance scope prevents the LLM from inventing ungrounded empirical claims."
  },
  analyze_literature: {
    file: "app/agents/analyst.py -> analyze_literature_node",
    desc: "Synthesizes cross-paper ResearchSynthesis objects: thematic clusters, direct comparison matrices, conflicting findings, and research gaps.",
    lesson: "True literature review compares methodologies against each other rather than listing isolated paper summaries."
  },
  critique: {
    file: "app/agents/critic.py -> critique_node",
    desc: "Audits extracted evidence against the original ResearchPlan. Assigns a quality_score (0.0 to 1.0). If deficient and revision_count < max_revisions, triggers revision loop.",
    lesson: "Bounded reflection loops turn linear scripts into self-correcting workflows without risking infinite loops."
  },
  prepare_revision: {
    file: "app/graph/nodes.py -> prepare_revision_node",
    desc: "Increments revision_count and sends Critic suggested keyword queries back to search_worker nodes via dispatch_revision_tasks.",
    lesson: "Only newly discovered papers get downloaded and extracted on revision cycles, cutting latency dramatically."
  },
  verify_citations: {
    file: "app/tools/citation_verifier.py -> verify_citations_node",
    desc: "Checks DOI format against CrossRef regex standards, validates URLs, and confirms every selected paper has grounded Evidence backing.",
    lesson: "Deterministic post-verification acts as an engineering safety net before any report reaches the user."
  },
  human_review: {
    file: "app/graph/nodes.py -> human_review_node",
    desc: "When skip_human_review=False, builds ReviewPackage and calls LangGraph interrupt(). State saves to SQLiteMemorySaver until user approves, requests revision, or rejects.",
    lesson: "Human-in-the-Loop interrupts give experts full audit authority before expensive final synthesis runs."
  },
  synthesize_summary: {
    file: "app/agents/writer.py -> synthesize_summary_node",
    desc: "Compiles publication-grade ResearchReport (abstract, thematic sections, comparative analysis, gaps, references) and exports Markdown + XML-safe ReportLab PDF.",
    lesson: "ReportWriterAgent works strictly from grounded Evidence items and verified CitationCheck records."
  }
};

let simState = {
  stepIdx: -1,
  pausedAtHitl: false,
  rejected: false,
  timer: null,
  seq: []
};

function buildSequence() {
  const wantRev = document.getElementById("opt-critic-rev").checked;
  const s = [
    "planner", "search_worker", "deduplicate_and_rank",
    "retrieve_content", "extract_evidence", "analyze_literature", "critique"
  ];
  if (wantRev) {
    s.push(
      "prepare_revision", "search_worker", "deduplicate_and_rank",
      "retrieve_content", "extract_evidence", "analyze_literature", "critique"
    );
  }
  s.push("verify_citations", "human_review", "synthesize_summary");
  return s;
}

function inspectNode(nodeId, customJson) {
  const info = NODE_INFO[nodeId];
  if (!info) return;
  document.getElementById("insp-title").textContent = `Node: ${nodeId}`;
  document.getElementById("insp-file").textContent = info.file;
  document.getElementById("insp-desc").textContent = info.desc;
  document.getElementById("insp-lesson").textContent = info.lesson;
  if (customJson) {
    document.getElementById("insp-json").textContent = JSON.stringify(customJson, null, 2);
  }
}

function renderSim() {
  const nodes = document.querySelectorAll(".sim-node");
  const currentNode = simState.stepIdx >= 0 ? simState.seq[simState.stepIdx] : "START";
  const visited = new Set(simState.seq.slice(0, Math.max(0, simState.stepIdx)));

  nodes.forEach(el => {
    const nid = el.dataset.node;
    const badge = el.querySelector(".node-badge");
    el.dataset.status = "idle";
    if (simState.rejected && nid === "human_review") {
      el.dataset.status = "rejected";
    } else if (simState.pausedAtHitl && nid === "human_review") {
      el.dataset.status = "paused";
    } else if (nid === currentNode) {
      el.dataset.status = "active";
    } else if (visited.has(nid)) {
      el.dataset.status = "done";
    }
    if (badge) {
      badge.textContent = el.dataset.status;
    }
  });

  const t = TOPICS[document.getElementById("sim-topic").value];
  const paywall = document.getElementById("opt-paywall").checked;
  const scopeMode = paywall ? "abstract_only" : "full_text";
  const idx = simState.stepIdx;
  const revCount = simState.seq.slice(0, idx + 1).filter(n => n === "prepare_revision").length;
  const papers = idx >= simState.seq.indexOf("deduplicate_and_rank") && idx >= 0 ? 2 : 0;
  const evidence = idx >= simState.seq.indexOf("extract_evidence") && idx >= 0 ? 6 : 0;

  let statusLabel = "queued";
  if (simState.rejected) statusLabel = "rejected";
  else if (simState.pausedAtHitl) statusLabel = "waiting_for_review";
  else if (currentNode === "synthesize_summary" && idx === simState.seq.length - 1) statusLabel = "completed";
  else if (idx >= 0) statusLabel = "running";

  document.getElementById("stat-node").textContent = currentNode;
  document.getElementById("stat-status").textContent = statusLabel;
  document.getElementById("stat-papers").textContent = papers;
  document.getElementById("stat-evidence").textContent = evidence;
  document.getElementById("stat-revisions").textContent = `${revCount} / 2`;
  document.getElementById("hitl-panel").classList.toggle("hidden", !simState.pausedAtHitl);

  const snapshot = {
    status: statusLabel,
    research_question: t.question,
    revision_count: revCount,
    selected_papers: papers ? t.papers : [],
    content_scope: idx >= simState.seq.indexOf("retrieve_content") && idx >= 0 ? scopeMode : "pending",
    extracted_evidence: evidence ? [{ claim: t.claim, supporting_passage: t.quote, scope: scopeMode }] : [],
    critique: idx >= simState.seq.indexOf("critique") && idx >= 0 ? {
      quality_score: revCount === 0 && document.getElementById("opt-critic-rev").checked ? 0.62 : 0.88,
      needs_revision: revCount === 0 && document.getElementById("opt-critic-rev").checked
    } : null,
    final_report_ready: statusLabel === "completed"
  };

  if (currentNode !== "START") {
    inspectNode(currentNode, snapshot);
  } else {
    document.getElementById("insp-json").textContent = JSON.stringify(snapshot, null, 2);
  }
}

function stepSim() {
  if (simState.pausedAtHitl || simState.rejected) return;
  if (simState.stepIdx === -1) {
    simState.seq = buildSequence();
  }
  if (simState.stepIdx + 1 >= simState.seq.length) {
    stopAutoPlay();
    return;
  }
  simState.stepIdx += 1;
  const curr = simState.seq[simState.stepIdx];
  if (curr === "human_review" && document.getElementById("opt-hitl").checked) {
    simState.pausedAtHitl = true;
    stopAutoPlay();
  }
  renderSim();
}

function stopAutoPlay() {
  if (simState.timer) {
    clearInterval(simState.timer);
    simState.timer = null;
    document.getElementById("btn-play").textContent = "Auto-Play";
  }
}

function resetSim() {
  stopAutoPlay();
  simState = { stepIdx: -1, pausedAtHitl: false, rejected: false, timer: null, seq: [] };
  document.getElementById("insp-title").textContent = "Inspector: Click Step Next or Select a Node";
  renderSim();
}

document.getElementById("btn-step").addEventListener("click", stepSim);
document.getElementById("btn-reset").addEventListener("click", resetSim);
document.getElementById("btn-play").addEventListener("click", () => {
  if (simState.timer) {
    stopAutoPlay();
  } else {
    if (simState.stepIdx >= simState.seq.length - 1 && simState.seq.length > 0) resetSim();
    document.getElementById("btn-play").textContent = "Pause";
    stepSim();
    simState.timer = setInterval(() => {
      if (simState.pausedAtHitl || simState.rejected || simState.stepIdx >= simState.seq.length - 1) {
        stopAutoPlay();
      } else {
        stepSim();
      }
    }, 900);
  }
});

document.getElementById("hitl-approve").addEventListener("click", () => {
  simState.pausedAtHitl = false;
  stepSim();
});
document.getElementById("hitl-revise").addEventListener("click", () => {
  simState.pausedAtHitl = false;
  simState.seq = [
    ...simState.seq.slice(0, simState.stepIdx + 1),
    "prepare_revision", "search_worker", "deduplicate_and_rank", "retrieve_content", "extract_evidence", "analyze_literature", "critique", "verify_citations", "human_review", "synthesize_summary"
  ];
  stepSim();
});
document.getElementById("hitl-reject").addEventListener("click", () => {
  simState.pausedAtHitl = false;
  simState.rejected = true;
  renderSim();
});

document.querySelectorAll(".sim-node").forEach(btn => {
  btn.addEventListener("click", () => inspectNode(btn.dataset.node));
});

// -------------------------------------------------------------------------
// 2. Meet the 5 Specialized Agents
// -------------------------------------------------------------------------
const AGENTS = [
  {
    id: "planner",
    name: "PlannerAgent",
    file: "app/agents/planner.py",
    temp: "0.1",
    schema: "ResearchPlan -> List[ResearchTask]",
    role: "Breaks complex academic inquiries into 3 to 5 orthogonal search queries tailored for arXiv and Semantic Scholar APIs.",
    fallback: "_heuristic_fallback_plan(): extracts primary keywords and builds 3 core queries (architectures, benchmarks, limitations).",
    sampleOut: '{ "objective": "Evaluate multi-agent SE coordination", "tasks": [ { "query": "multi-agent LLM code generation", "priority": 1 } ] }'
  },
  {
    id: "extractor",
    name: "ExtractorAgent",
    file: "app/agents/extractor.py",
    temp: "0.0",
    schema: "ExtractionPayload (PaperAnalysis + Evidence[])",
    role: "Reads full_text (up to 25k chars) or abstract_only text and extracts atomic claims anchored to verbatim supporting_passage quotes.",
    fallback: "_heuristic_fallback_extraction(): splits sentences, matches empirical & benchmark keywords, preserves exact sentence quotes.",
    sampleOut: '{ "claim": "Debate improved GSM8K accuracy", "supporting_passage": "Across 500 problems, multi-agent debate improved accuracy by 14.2%.", "content_scope": "full_text" }'
  },
  {
    id: "analyst",
    name: "AnalystAgent",
    file: "app/agents/analyst.py",
    temp: "0.2",
    schema: "ResearchSynthesis (themes, comparisons, disagreements, gaps)",
    role: "Synthesizes evidence across papers instead of summarizing individually: clusters themes and contrasts trade-offs across datasets.",
    fallback: "_heuristic_fallback_synthesis(): groups papers into Coordination & Benchmarking axes with dataset comparisons.",
    sampleOut: '{ "themes": [{"theme_name": "Role Decomposition"}], "comparisons": [{"comparison_axis": "Latency vs Pass@1"}] }'
  },
  {
    id: "critic",
    name: "CriticAgent",
    file: "app/agents/critic.py",
    temp: "0.0",
    schema: "Critique (quality_score, needs_revision, suggested_revision_tasks)",
    role: "Evaluates coverage against the planned subquestions. Requests short 3 to 6 word follow-up keyword queries if quality_score < 0.75 and budget allows.",
    fallback: "_heuristic_fallback_critique(): computes keyword coverage ratio + corpus ratio, capped cleanly at MAX_REVISION_CYCLES = 2.",
    sampleOut: '{ "quality_score": 0.65, "missing_topics": ["Benchmark decontamination"], "needs_revision": true, "suggested_revision_tasks": ["LLM benchmark decontamination"] }'
  },
  {
    id: "writer",
    name: "ReportWriterAgent",
    file: "app/agents/writer.py",
    temp: "0.3",
    schema: "ResearchReport -> Markdown + ReportLab PDF",
    role: "Compiles Executive Abstract, Introduction, Thematic Sections, Comparative Analysis, Research Gaps, Limitations, and Verified Bibliography.",
    fallback: "_write_deterministic(): guarantees full citation-linked Markdown and PDF generation even if LLM call fails or key is offline.",
    sampleOut: "# Systematic Literature Review: ...\n## Executive Summary\n## Thematic Synthesis\n## References (with DOI Audit)"
  }
];

function selectAgent(id) {
  const a = AGENTS.find(x => x.id === id) || AGENTS[0];
  document.querySelectorAll(".agent-tab").forEach(b => {
    b.dataset.selected = b.dataset.agent === a.id ? "true" : "false";
  });
  document.getElementById("agent-detail").innerHTML = `
    <div class="inspector-header">
      <div>
        <h3>${a.name}</h3>
        <div class="mono text-primary" style="font-size:12px;">${a.file}</div>
      </div>
      <div class="header-actions">
        <span class="pill">temp=${a.temp}</span>
        <span class="pill">method="function_calling"</span>
      </div>
    </div>
    <div class="two-col" style="margin-top:12px;">
      <div class="section-gap">
        <div>
          <strong>Primary Responsibility</strong>
          <p class="text-muted" style="margin:4px 0 0;font-size:12px;">${a.role}</p>
        </div>
        <div>
          <strong>Schema Contract</strong>
          <div class="mono" style="margin-top:4px;font-size:12px;">${a.schema}</div>
        </div>
      </div>
      <div class="section-gap">
        <div>
          <strong>Deterministic Offline Fallback</strong>
          <p class="text-muted" style="margin:4px 0 0;font-size:12px;">${a.fallback}</p>
        </div>
        <div>
          <strong>Sample Structured Output</strong>
          <pre style="margin-top:6px;">${a.sampleOut}</pre>
        </div>
      </div>
    </div>
  `;
}

const agentSelector = document.getElementById("agent-selector");
AGENTS.forEach(a => {
  const btn = document.createElement("button");
  btn.className = "agent-tab";
  btn.dataset.agent = a.id;
  btn.innerHTML = `<div style="font-weight:700;">${a.name}</div><div class="mono text-muted" style="margin-top:2px;">temp ${a.temp}</div>`;
  btn.addEventListener("click", () => selectAgent(a.id));
  agentSelector.appendChild(btn);
});
selectAgent("planner");

// -------------------------------------------------------------------------
// 3. Zero-Hallucination Tools Lab
// -------------------------------------------------------------------------
function normDoi(d) {
  return (d || "").trim().toLowerCase().replace(/^https?:\/\/(dx\.)?doi\.org\//, "").replace(/^doi:/, "").trim();
}
function normTitle(t) {
  return (t || "").toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
}

function runDedupLab() {
  const d1 = normDoi(document.getElementById("dd-d1").value);
  const d2 = normDoi(document.getElementById("dd-d2").value);
  const t1 = normTitle(document.getElementById("dd-t1").value);
  const t2 = normTitle(document.getElementById("dd-t2").value);
  const y1 = Number(document.getElementById("dd-y1").value);
  const y2 = Number(document.getElementById("dd-y2").value);

  const w1 = new Set(t1.split(" ").filter(Boolean));
  const w2 = new Set(t2.split(" ").filter(Boolean));
  const inter = [...w1].filter(w => w2.has(w)).length;
  const union = new Set([...w1, ...w2]).size || 1;
  const jaccard = inter / union;

  let match = false;
  let reason = "Distinct publications (no matching rule satisfied).";
  if (d1 && d2) {
    match = d1 === d2;
    reason = match ? `Stage 1 Normalized DOI Match: "${d1}"` : `DOIs differ ("${d1}" vs "${d2}")`;
  } else if (t1 && t2 && t1 === t2 && Math.abs(y1 - y2) <= 1) {
    match = true;
    reason = `Stage 3 Normalized Title Match (+-1 yr variance): "${t1}"`;
  } else if (jaccard > 0.85 && Math.abs(y1 - y2) <= 1) {
    match = true;
    reason = `Stage 4 Jaccard Token Overlap (${jaccard.toFixed(2)} > 0.85) & Year Delta <= 1`;
  }

  document.getElementById("dd-result").innerHTML = `
    <div style="font-weight:700;" class="${match ? "text-success" : "text-warning"}">
      ${match ? "DUPLICATE DETECTED -> MERGED INTO CANONICAL PAPER" : "KEEP SEPARATE RECORDS"}
    </div>
    <div class="text-muted" style="margin-top:4px;font-size:12px;">
      Reason: ${reason} | Jaccard: <span class="mono">${jaccard.toFixed(2)}</span>
    </div>
  `;
}
["dd-t1", "dd-d1", "dd-y1", "dd-t2", "dd-d2", "dd-y2"].forEach(id => {
  document.getElementById(id).addEventListener("input", runDedupLab);
});
runDedupLab();

function runCitationLab() {
  const doi = normDoi(document.getElementById("cv-doi").value);
  const passage = (document.getElementById("cv-passage").value || "").trim();
  const doiRegex = /^10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+$/;
  const doiOk = doiRegex.test(doi);
  const claimOk = passage.length > 15;
  document.getElementById("cv-result").innerHTML = `
    <div style="display:flex;flex-wrap:wrap;gap:16px;font-size:12px;font-weight:700;">
      <span class="${doiOk ? "text-success" : "text-error"}">DOI Regex: ${doiOk ? "VALID" : "INVALID"}</span>
      <span class="${claimOk ? "text-success" : "text-error"}">Grounding Excerpt: ${claimOk ? "SUPPORTED (>15 chars)" : "INSUFFICIENT"}</span>
    </div>
  `;
}
["cv-doi", "cv-passage"].forEach(id => document.getElementById(id).addEventListener("input", runCitationLab));
runCitationLab();

function runPdfLab() {
  const val = document.getElementById("pdf-scenario").value;
  const map = {
    ok: {
      scope: "full_text",
      status: "success",
      note: "Downloaded valid %PDF stream -> ligatures cleaned -> sections segmented for ExtractorAgent."
    },
    paywall: {
      scope: "abstract_only",
      status: "success (fallback)",
      note: "Server returned HTML / HTTP 202 (rejected by %PDF header check) -> gracefully fell back to peer-reviewed abstract."
    },
    timeout: {
      scope: "abstract_only",
      status: "success (fallback)",
      note: "Wall-clock timer hit 15s inside iter_bytes -> aborted stream cleanly and fell back to abstract_only."
    },
    scanned: {
      scope: "metadata_only",
      status: "partial",
      note: "Extracted < 50 chars and no abstract -> tagged metadata_only (Title + Authors) so writer never hallucinates details."
    }
  };
  const r = map[val];
  document.getElementById("pdf-result").innerHTML = `
    <div style="font-size:12px;">
      <strong>content_scope:</strong> <code class="text-primary">${r.scope}</code> |
      <strong>retrieval_status:</strong> <code>${r.status}</code>
    </div>
    <div class="text-muted" style="margin-top:4px;font-size:12px;">${r.note}</div>
  `;
}
document.getElementById("pdf-scenario").addEventListener("change", runPdfLab);
runPdfLab();

// -------------------------------------------------------------------------
// 4. Persistence & Checkpointing Simulator
// -------------------------------------------------------------------------
function updatePersistenceView() {
  const pg = document.getElementById("env-pg").checked;
  const testing = document.getElementById("env-testing").checked;
  const blocked = document.getElementById("env-applocker").checked;

  let dbTarget = "SQLite Local DB (sqlite:///./research.db)";
  let dbWhy = "Port 5432 socket probe (0.2s) returned unreachable; instant fallback avoids 1s connection hang.";
  if (testing) {
    dbTarget = "Isolated Temp SQLite DB (MAS_LOCAL_SQLITE_URL)";
    dbWhy = "tests/conftest.py isolates pytest runs into a temp folder so production research.db is never polluted.";
  } else if (pg && !blocked) {
    dbTarget = "PostgreSQL + pgvector (:5432/research_db)";
    dbWhy = "Socket check passed and psycopg driver loaded cleanly.";
  } else if (pg && blocked) {
    dbTarget = "SQLite Local DB (sqlite:///./research.db)";
    dbWhy = "psycopg binary DLL blocked by Windows App Control; exception handler falls back to SQLite automatically.";
  }

  let cpTarget = "SQLiteMemorySaver (research_checkpoints.db)";
  let cpWhy = "Backed by Python stdlib sqlite3 (zero external DLLs). Persists HITL interrupts across server restarts.";
  if (testing) {
    cpTarget = "MemorySaver (Pure RAM)";
    cpWhy = "APP_ENV=testing keeps unit and graph integration tests isolated in memory.";
  } else if (pg && !blocked) {
    cpTarget = "PostgresSaver (:5432/research_db)";
    cpWhy = "Lazy import of langgraph.checkpoint.postgres succeeds because Postgres is listening and unblocked.";
  }

  document.getElementById("env-routing-output").innerHTML = `
    <div class="subcard">
      <div class="text-muted" style="font-weight:700;">Domain Storage Route (DatabaseService)</div>
      <div class="mono text-primary" style="font-weight:700;margin-top:4px;">${dbTarget}</div>
      <p class="text-muted" style="margin:6px 0 0;font-size:12px;">${dbWhy}</p>
    </div>
    <div class="subcard">
      <div class="text-muted" style="font-weight:700;">LangGraph Checkpointer Route (get_checkpointer)</div>
      <div class="mono text-success" style="font-weight:700;margin-top:4px;">${cpTarget}</div>
      <p class="text-muted" style="margin:6px 0 0;font-size:12px;">${cpWhy}</p>
    </div>
  `;
}
["env-pg", "env-testing", "env-applocker"].forEach(id => document.getElementById(id).addEventListener("change", updatePersistenceView));
updatePersistenceView();

// -------------------------------------------------------------------------
// 5. Evaluation Benchmark Canvas Chart + REST API Explorer + Quiz
// -------------------------------------------------------------------------
function drawChart() {
  const canvas = document.getElementById("evalChart");
  if (!canvas || !canvas.parentElement) return;
  const w = Math.max(240, canvas.parentElement.clientWidth);
  if (!canvas.parentElement.clientWidth) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const compact = w < 460;
  const h = compact ? 255 : 225;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.height = `${h}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const cs = getComputedStyle(document.documentElement);
  const fg = cs.getPropertyValue("--fg").trim() || "#0f172a";
  const muted = cs.getPropertyValue("--muted").trim() || "#475569";
  const border = cs.getPropertyValue("--border").trim() || "#cbd5e1";
  const c1 = cs.getPropertyValue("--chart-baseline").trim() || "#94a3b8";
  const c2 = cs.getPropertyValue("--chart-masra").trim() || "#2563eb";

  const labels = [
    ["DOI", "Validity"],
    ["Verbatim", "Grounding"],
    ["Full-Text", "Scope"],
    ["Automated", "Tests"]
  ];
  const baseline = [40, 25, 10, 0];
  const masra = [100, 100, 82, 100];

  const padL = 40;
  const padR = 12;
  const padT = compact ? 48 : 30;
  const padB = compact ? 44 : 38;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  ctx.strokeStyle = border;
  ctx.fillStyle = muted;
  ctx.font = "12px sans-serif";
  [0, 50, 100].forEach(pct => {
    const y = padT + plotH * (1 - pct / 100);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillText(pct + "%", 2, y + 4);
  });

  // Responsive Legend
  ctx.fillStyle = c1;
  ctx.fillRect(padL, 6, 12, 12);
  ctx.fillStyle = fg;
  ctx.fillText("Single-Prompt Baseline", padL + 18, 16);

  const leg2X = compact ? padL : padL + 175;
  const leg2Y = compact ? 25 : 6;
  ctx.fillStyle = c2;
  ctx.fillRect(leg2X, leg2Y, 12, 12);
  ctx.fillStyle = fg;
  ctx.fillText("MAS-RA Multi-Agent", leg2X + 18, leg2Y + 10);

  const groupW = plotW / labels.length;
  const barW = Math.min(26, Math.max(10, groupW * 0.25));
  labels.forEach((parts, i) => {
    const cx = padL + groupW * (i + 0.5);
    const h1 = plotH * (baseline[i] / 100);
    const h2 = plotH * (masra[i] / 100);

    ctx.fillStyle = c1;
    ctx.fillRect(cx - barW - 2, padT + plotH - h1, barW, h1);

    ctx.fillStyle = c2;
    ctx.fillRect(cx + 2, padT + plotH - h2, barW, h2);

    ctx.fillStyle = fg;
    ctx.textAlign = "center";
    if (w < 540) {
      ctx.fillText(parts[0], cx, h - 22);
      ctx.fillText(parts[1], cx, h - 7);
    } else {
      ctx.fillText(parts.join(" "), cx, h - 12);
    }
  });
  ctx.textAlign = "left";
}
window.addEventListener("resize", drawChart);
if (typeof ResizeObserver !== "undefined") {
  const wrap = document.querySelector(".chart-wrap");
  if (wrap) new ResizeObserver(() => requestAnimationFrame(drawChart)).observe(wrap);
}

// FastAPI Endpoint Explorer
const ENDPOINTS = [
  { m: "GET", p: "/health", res: '{ "status": "healthy", "env": "development" }' },
  { m: "POST", p: "/api/projects", res: '{ "project_id": "6338a8d2...", "title": "Health Monitoring", "status": "active" }' },
  { m: "POST", p: "/api/projects/{id}/runs", res: '{ "run_id": "5818c7d5...", "status": "queued", "current_phase": "initializing" }' },
  { m: "GET", p: "/api/runs/{id}/review", res: '{ "selected_papers_count": 3, "critique_score": 0.85, "citation_checks": [...] }' },
  { m: "POST", p: "/api/runs/{id}/review", res: '// Body: {"action": "approve"}\n{ "run_id": "5818c7d5...", "status": "completed", "current_phase": "report_synthesized" }' },
  { m: "GET", p: "/api/runs/{id}/export/pdf", res: 'Content-Type: application/pdf\nContent-Disposition: attachment; filename="literature_review_5818c7d5.pdf"' }
];
const apiList = document.getElementById("api-list");
const apiPre = document.getElementById("api-preview");
ENDPOINTS.forEach((ep, idx) => {
  const b = document.createElement("button");
  b.className = "api-pill mono";
  b.textContent = `${ep.m} ${ep.p}`;
  b.dataset.selected = idx === 0 ? "true" : "false";
  b.addEventListener("click", () => {
    document.querySelectorAll(".api-pill").forEach(x => (x.dataset.selected = x === b ? "true" : "false"));
    apiPre.textContent = `// ${ep.m} ${ep.p}\n${ep.res}`;
  });
  apiList.appendChild(b);
  if (idx === 0) apiPre.textContent = `// ${ep.m} ${ep.p}\n${ep.res}`;
});

// Comprehension Quiz
const QUIZ = [
  {
    q: "1. Which LangGraph feature dispatches Search Workers concurrently across planned subquestions?",
    opts: ["Send() conditional fan-out API", "Global thread sleep", "Static sequential chain"],
    ans: 0,
    exp: 'dispatch_search_tasks returns a list of Send("search_worker", payload) objects merged back via merge_papers_reducer.'
  },
  {
    q: "2. How does ExtractorAgent prevent fabricated citations when a PDF is paywalled?",
    opts: ["Guesses experimental tables", 'Tags content_scope="abstract_only" & requires verbatim quotes', "Skips the paper completely"],
    ans: 1,
    exp: "PDFParser falls back to abstract_only and ExtractorAgent requires supporting_passage verbatim quotes."
  },
  {
    q: "3. Why does SQLiteMemorySaver inherit from MemorySaver using stdlib sqlite3?",
    opts: ["Faster GPU tensor math", "Persists HITL interrupts across restarts without Windows-blocked binary DLLs", "Replaces SQLAlchemy"],
    ans: 1,
    exp: "Stdlib sqlite3 requires no external C-extension drivers while saving cp_storage/writes/blobs across restarts."
  },
  {
    q: "4. What prevents infinite self-correction loops in CriticAgent?",
    opts: ["MAX_REVISION_CYCLES budget check (default: 2)", "Hardcoding score=1.0 always", "Disabling search_worker"],
    ans: 0,
    exp: "When revision_count >= max_revisions, CriticAgent forces needs_revision=False and advances to verify_citations."
  }
];
const quizAnswers = new Array(QUIZ.length).fill(null);
const quizBox = document.getElementById("quiz-container");
QUIZ.forEach((item, qi) => {
  const card = document.createElement("div");
  card.className = "subcard";
  const title = document.createElement("div");
  title.style.fontWeight = "700";
  title.textContent = item.q;
  card.appendChild(title);

  const feedback = document.createElement("div");
  feedback.className = "hidden";
  feedback.style.marginTop = "8px";
  feedback.style.fontSize = "12px";

  item.opts.forEach((opt, oi) => {
    const btn = document.createElement("button");
    btn.className = "quiz-opt";
    btn.textContent = opt;
    btn.addEventListener("click", () => {
      quizAnswers[qi] = oi === item.ans;
      card.querySelectorAll("button").forEach((b, bi) => {
        b.style.borderColor = bi === oi ? (oi === item.ans ? "var(--success)" : "var(--error)") : "var(--border)";
      });
      feedback.textContent = (oi === item.ans ? "Correct! " : "Not quite. ") + item.exp;
      feedback.className = oi === item.ans ? "text-success" : "text-warning";
      const correctCount = quizAnswers.filter(Boolean).length;
      document.getElementById("quiz-score").textContent = `Score: ${correctCount} / ${QUIZ.length}`;
    });
    card.appendChild(btn);
  });
  card.appendChild(feedback);
  quizBox.appendChild(card);
});

