"""Generate concise, minimal Option A (Clean Light Academic) 10-slide PowerPoint deck for MAS-RA."""

import os
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


# Option A: Clean Light Academic Palette
NAVY = RGBColor(15, 23, 42)        # #0F172A Deep Navy Ink & Hero Bg
COBALT = RGBColor(29, 78, 216)     # #1D4ED8 Primary Accent
SKY = RGBColor(56, 189, 248)       # #38BDF8 Hero Accent Highlight
TEAL = RGBColor(13, 148, 136)      # #0D9488 Secondary Accent
EMERALD = RGBColor(21, 128, 61)    # #15803D Success / Verified
AMBER = RGBColor(217, 119, 6)      # #D97706 HITL / Caution
CRIMSON = RGBColor(220, 38, 38)    # #DC2626 Problem / Failure

CANVAS = RGBColor(248, 250, 252)   # #F8FAFC Page Canvas
WHITE = RGBColor(255, 255, 255)    # #FFFFFF Card Surface
SOFT_BLUE = RGBColor(239, 246, 255)# #EFF6FF Highlight Surface
SOFT_SLATE = RGBColor(241, 245, 249)# #F1F5F9 Nested Surface
BORDER = RGBColor(203, 213, 225)   # #CBD5E1 Card Border

CHARCOAL = RGBColor(51, 65, 85)    # #334155 Body Text
MUTED = RGBColor(100, 116, 139)    # #64748B Metadata / Footer
FONT_MAIN = "Calibri"
FONT_MONO = "Consolas"


def set_bg(slide, color=CANVAS):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    return bg


def add_rect(slide, left, top, width, height, fill_color=WHITE, border_color=None, border_pt=1.0, rounded=True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, left, top, width, height)
    if rounded:
        try:
            shp.adjustments[0] = 0.04
        except Exception:
            pass
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if border_color is not None:
        shp.line.color.rgb = border_color
        shp.line.width = Pt(border_pt)
    else:
        shp.line.fill.background()
    return shp


def add_text_box(
    slide,
    left,
    top,
    width,
    height,
    text="",
    font_size=14,
    bold=False,
    color=CHARCOAL,
    font_name=FONT_MAIN,
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.TOP,
):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if text:
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = color
    return tf


def add_bullets(tf, items, font_size=14, color=CHARCOAL, space_after=12, prefix="- "):
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if (i == 0 and len(tf.paragraphs[0].runs) == 0 and tf.paragraphs[0].text == "") else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = 1.15
        r = p.add_run()
        r.text = f"{prefix}{item}"
        r.font.name = FONT_MAIN
        r.font.size = Pt(font_size)
        r.font.color.rgb = color


def add_header_footer(slide, slide_num, category, title):
    set_bg(slide, CANVAS)
    add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.08), fill_color=COBALT, rounded=False)

    add_text_box(
        slide, Inches(0.7), Inches(0.3), Inches(10.0), Inches(0.28),
        text=category.upper(), font_size=11, bold=True, color=COBALT,
    )
    add_text_box(
        slide, Inches(0.7), Inches(0.58), Inches(11.9), Inches(0.58),
        text=title, font_size=26, bold=True, color=NAVY,
    )
    add_rect(slide, Inches(0.7), Inches(1.24), Inches(11.933), Inches(0.02), fill_color=BORDER, rounded=False)

    # Footer
    add_rect(slide, Inches(0.7), Inches(7.02), Inches(11.933), Inches(0.015), fill_color=BORDER, rounded=False)
    add_text_box(
        slide, Inches(0.7), Inches(7.1), Inches(9.5), Inches(0.28),
        text="MAS-RA: Autonomous Multi-Agent Research Assistant",
        font_size=10, color=MUTED,
    )
    add_text_box(
        slide, Inches(11.0), Inches(7.1), Inches(1.633), Inches(0.28),
        text=f"Slide {slide_num} / 10", font_size=10, bold=True, color=COBALT, align=PP_ALIGN.RIGHT,
    )


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def add_badge_circle(slide, left, top, size, label, fill_color=COBALT, text_color=WHITE, font_size=14):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, size, size)
    c.fill.solid()
    c.fill.fore_color.rgb = fill_color
    c.line.fill.background()
    tf = c.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name = FONT_MAIN
    r.font.size = Pt(font_size)
    r.font.bold = True
    r.font.color.rgb = text_color
    return c


def add_pill(slide, left, top, width, height, text, fill_color=SOFT_BLUE, border_color=COBALT, text_color=COBALT, font_size=11.5):
    shp = add_rect(slide, left, top, width, height, fill_color=fill_color, border_color=border_color, border_pt=1.0)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = FONT_MONO
    r.font.size = Pt(font_size)
    r.font.bold = True
    r.font.color.rgb = text_color
    return shp


def build_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Minimal Hero Title Slide
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    set_bg(s1, NAVY)

    add_rect(s1, Inches(0), Inches(0), Inches(0.28), Inches(7.5), fill_color=COBALT, rounded=False)
    add_rect(s1, Inches(0.28), Inches(0), Inches(0.08), Inches(7.5), fill_color=TEAL, rounded=False)

    add_text_box(
        s1, Inches(0.95), Inches(1.45), Inches(6.0), Inches(0.34),
        text="CAPSTONE PRESENTATION", font_size=12, bold=True, color=SKY,
    )
    add_text_box(
        s1, Inches(0.95), Inches(1.95), Inches(11.3), Inches(1.75),
        text="MAS-RA: Autonomous Multi-Agent\nLiterature Review Assistant",
        font_size=42, bold=True, color=WHITE,
    )
    add_text_box(
        s1, Inches(0.95), Inches(3.85), Inches(10.5), Inches(0.55),
        text="Evidence-Grounded Scientific Synthesis via LangGraph & Multi-Agent Verification",
        font_size=18, color=RGBColor(203, 213, 225),
    )

    pills = [
        ("LangGraph", Inches(1.55)),
        ("GPT-4o-mini", Inches(1.6)),
        ("arXiv + S2", Inches(1.55)),
        ("FastAPI", Inches(1.35)),
        ("Streamlit", Inches(1.45)),
        ("SQLite / Postgres", Inches(2.05)),
    ]
    px = Inches(0.95)
    for label, pw in pills:
        add_pill(
            s1, px, Inches(4.85), pw, Inches(0.44), label,
            fill_color=RGBColor(30, 41, 59), border_color=COBALT, text_color=WHITE, font_size=11.5,
        )
        px += pw + Inches(0.16)

    add_rect(s1, Inches(0.95), Inches(6.1), Inches(11.4), Inches(0.02), fill_color=RGBColor(51, 65, 85), rounded=False)
    add_text_box(
        s1, Inches(0.95), Inches(6.28), Inches(6.5), Inches(0.45),
        text="Problem  ->  Architecture  ->  Verification  ->  Evaluation",
        font_size=13, color=RGBColor(148, 163, 184),
    )
    add_text_box(
        s1, Inches(8.6), Inches(6.28), Inches(3.75), Inches(0.45),
        text="54 / 54 Tests Passing", font_size=13, bold=True, color=RGBColor(74, 222, 128), align=PP_ALIGN.RIGHT,
    )
    add_notes(
        s1,
        "Good morning everyone. Today I present MAS-RA, an Autonomous Multi-Agent Research Assistant. "
        "It replaces unreliable single-prompt summaries with a cyclic LangGraph pipeline that discovers real papers, grounds every claim in verbatim quotes, checks citations, and supports human approval."
    )

    # =========================================================================
    # SLIDE 2: Problem Statement (Concise Trio)
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_header_footer(s2, 2, "Problem Statement", "Why Standalone LLMs Fail Research")

    # Compact Stat Callout Strip
    add_rect(s2, Inches(0.7), Inches(1.58), Inches(11.933), Inches(0.68), fill_color=SOFT_BLUE, border_color=COBALT, border_pt=1.0)
    add_text_box(
        s2, Inches(0.95), Inches(1.68), Inches(11.4), Inches(0.48),
        text="5M+ Annual Papers   |   Manual Review: 2 to 4 Weeks   |   Naive LLMs: Hallucinations",
        font_size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
    )

    pillars = [
        ("1", "Fabricated Citations", ["Invented paper titles", "Fake or invalid DOIs", "Zero live API checks"]),
        ("2", "Shallow Coverage", ["Abstract-only guessing", "Skips full PDF methods", "Duplicate paper noise"]),
        ("3", "Zero Provenance", ["No verbatim quotes", "Blind research gaps", "No human checkpoint"]),
    ]
    cw = Inches(3.82)
    for idx, (num, head, bullets) in enumerate(pillars):
        cx = Inches(0.7) + idx * Inches(4.056)
        add_rect(s2, cx, Inches(2.58), cw, Inches(3.95), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s2, cx, Inches(2.58), cw, Inches(0.08), fill_color=CRIMSON, rounded=False)
        add_badge_circle(s2, cx + Inches(0.24), Inches(2.92), Inches(0.48), num, fill_color=CRIMSON, font_size=16)
        add_text_box(s2, cx + Inches(0.86), Inches(2.98), Inches(2.75), Inches(0.4), text=head, font_size=17, bold=True, color=NAVY)
        tf = add_text_box(s2, cx + Inches(0.28), Inches(3.75), cw - Inches(0.56), Inches(2.5))
        add_bullets(tf, bullets, font_size=15, space_after=18)

    add_notes(
        s2,
        "Over five million papers are published every year, turning manual literature review into a weeks-long bottleneck. "
        "Meanwhile, naive single-prompt LLMs fail academic rigor in three ways: they fabricate citations and DOIs, guess superficially without reading full PDFs, and offer no verbatim proof, self-correction, or human checkpoint."
    )

    # =========================================================================
    # SLIDE 3: Motivation & Objectives (Clean Flow + 2x2 Minimal Grid)
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_header_footer(s3, 3, "Motivation & Goals", "From Weeks of Reading to Audited Prototypes")

    stages = [
        ("Weeks of Reading", SOFT_SLATE, BORDER, CHARCOAL),
        ("MAS-RA Pipeline", SOFT_BLUE, COBALT, NAVY),
        ("Verified Synthesis", RGBColor(240, 253, 250), TEAL, NAVY),
        ("Faster Prototypes", RGBColor(240, 253, 244), EMERALD, NAVY),
    ]
    sw = Inches(2.75)
    for idx, (st_title, bg_c, bd_c, tx_c) in enumerate(stages):
        sx = Inches(0.7) + idx * Inches(3.06)
        add_rect(s3, sx, Inches(1.58), sw, Inches(0.88), fill_color=bg_c, border_color=bd_c, border_pt=1.5)
        add_text_box(s3, sx + Inches(0.14), Inches(1.66), sw - Inches(0.28), Inches(0.72), text=st_title, font_size=15, bold=True, color=tx_c, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        if idx < 3:
            add_text_box(s3, sx + sw + Inches(0.02), Inches(1.8), Inches(0.28), Inches(0.4), text="->", font_size=18, bold=True, color=COBALT, align=PP_ALIGN.CENTER)

    goals = [
        ("Real Repository Discovery", TEAL, ["Live arXiv + Semantic Scholar APIs", "4-stage DOI & title deduplication"]),
        ("Zero-Hallucination Core", COBALT, ["Exact verbatim source quotes", "Explicit full_text / abstract scope"]),
        ("Bounded Self-Refinement", AMBER, ["Critic coverage score (0.0 to 1.0)", "Max 2 automatic revision loops"]),
        ("Human Agency & Persistence", EMERALD, ["interrupt() human review gate", "Restart-safe SQLite checkpoints"]),
    ]
    gw = Inches(5.82)
    gh = Inches(1.85)
    for idx, (g_title, acc_c, g_pts) in enumerate(goals):
        col = idx % 2
        row = idx // 2
        gx = Inches(0.7) + col * (gw + Inches(0.29))
        gy = Inches(2.78) + row * (gh + Inches(0.24))
        add_rect(s3, gx, gy, gw, gh, fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s3, gx, gy, Inches(0.11), gh, fill_color=acc_c, rounded=False)
        add_text_box(s3, gx + Inches(0.32), gy + Inches(0.22), gw - Inches(0.5), Inches(0.38), text=g_title, font_size=16.5, bold=True, color=NAVY)
        tf = add_text_box(s3, gx + Inches(0.32), gy + Inches(0.74), gw - Inches(0.5), Inches(0.95))
        add_bullets(tf, g_pts, font_size=14, space_after=10)

    add_notes(
        s3,
        "Our goal is to compress weeks of domain exploration into minutes while keeping scientific integrity intact. "
        "We enforce four design pillars: real API discovery with deduplication, verbatim quote grounding, bounded self-refinement via a critic loop, and persistent human-in-the-loop checkpoints."
    )

    # =========================================================================
    # SLIDE 4: System Architecture (Pure Visual StateGraph)
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_header_footer(s4, 4, "System Architecture", "LangGraph Cyclic StateGraph")

    def draw_node(x, y, w, h, title, sub, fill=WHITE, border=COBALT, title_color=NAVY):
        add_rect(s4, x, y, w, h, fill_color=fill, border_color=border, border_pt=1.6)
        add_text_box(s4, x + Inches(0.08), y + Inches(0.1), w - Inches(0.16), Inches(0.32), text=title, font_size=12, bold=True, color=title_color, align=PP_ALIGN.CENTER)
        add_text_box(s4, x + Inches(0.08), y + Inches(0.44), w - Inches(0.16), h - Inches(0.5), text=sub, font_size=10.5, color=CHARCOAL, align=PP_ALIGN.CENTER)

    y1 = Inches(1.68)
    nh = Inches(0.92)
    draw_node(Inches(0.7), y1, Inches(1.05), nh, "START", "Query", fill=SOFT_SLATE, border=MUTED)
    add_text_box(s4, Inches(1.77), y1 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=COBALT, align=PP_ALIGN.CENTER)
    draw_node(Inches(2.07), y1, Inches(1.95), nh, "1. planner", "3-5 search tasks", fill=SOFT_BLUE, border=COBALT)
    add_text_box(s4, Inches(4.04), y1 + Inches(0.3), Inches(0.4), Inches(0.3), text="Send", font_size=10, bold=True, color=COBALT, align=PP_ALIGN.CENTER)
    draw_node(Inches(4.46), y1, Inches(2.25), nh, "2. search_worker", "Parallel arXiv & S2", fill=SOFT_BLUE, border=COBALT)
    add_text_box(s4, Inches(6.73), y1 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=COBALT, align=PP_ALIGN.CENTER)
    draw_node(Inches(7.03), y1, Inches(2.55), nh, "3. deduplicate_and_rank", "DOI + Jaccard", fill=WHITE, border=TEAL)
    add_text_box(s4, Inches(9.6), y1 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    draw_node(Inches(9.9), y1, Inches(2.73), nh, "4. retrieve_content", "Skip cached PDFs", fill=WHITE, border=TEAL)

    add_text_box(s4, Inches(11.05), Inches(2.7), Inches(0.45), Inches(0.32), text="v", font_size=16, bold=True, color=TEAL, align=PP_ALIGN.CENTER)

    y2 = Inches(3.15)
    draw_node(Inches(9.9), y2, Inches(2.73), nh, "5. extract_evidence", "Verbatim claims", fill=SOFT_BLUE, border=COBALT)
    add_text_box(s4, Inches(9.6), y2 + Inches(0.3), Inches(0.28), Inches(0.3), text="<-", font_size=14, bold=True, color=COBALT, align=PP_ALIGN.CENTER)
    draw_node(Inches(7.03), y2, Inches(2.55), nh, "6. analyze_literature", "Themes & matrix", fill=SOFT_BLUE, border=COBALT)
    add_text_box(s4, Inches(6.73), y2 + Inches(0.3), Inches(0.28), Inches(0.3), text="<-", font_size=14, bold=True, color=COBALT, align=PP_ALIGN.CENTER)
    draw_node(Inches(4.46), y2, Inches(2.25), nh, "7. critique", "Coverage score", fill=RGBColor(255, 251, 235), border=AMBER)

    draw_node(Inches(0.7), y2, Inches(3.28), nh, "7r. prepare_revision", "Loop <= 2 cycles", fill=RGBColor(255, 251, 235), border=AMBER, title_color=AMBER)
    add_text_box(s4, Inches(4.0), y2 + Inches(0.3), Inches(0.44), Inches(0.3), text="<-", font_size=14, bold=True, color=AMBER, align=PP_ALIGN.CENTER)
    add_text_box(s4, Inches(4.46), Inches(2.68), Inches(2.25), Inches(0.36), text="^ revision fan-out ^", font_size=10.5, bold=True, color=AMBER, align=PP_ALIGN.CENTER)

    add_text_box(s4, Inches(5.36), Inches(4.15), Inches(0.45), Inches(0.32), text="v", font_size=16, bold=True, color=EMERALD, align=PP_ALIGN.CENTER)

    y3 = Inches(4.56)
    draw_node(Inches(0.7), y3, Inches(2.6), nh, "8. verify_citations", "DOI & grounding", fill=RGBColor(240, 253, 244), border=EMERALD)
    add_text_box(s4, Inches(3.32), y3 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=EMERALD, align=PP_ALIGN.CENTER)
    draw_node(Inches(3.62), y3, Inches(2.8), nh, "9. human_review", "interrupt() Gate", fill=RGBColor(255, 251, 235), border=AMBER)
    add_text_box(s4, Inches(6.44), y3 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=EMERALD, align=PP_ALIGN.CENTER)
    draw_node(Inches(6.74), y3, Inches(2.85), nh, "10. synthesize_summary", "Markdown + PDF", fill=RGBColor(240, 253, 244), border=EMERALD)
    add_text_box(s4, Inches(9.61), y3 + Inches(0.3), Inches(0.28), Inches(0.3), text="->", font_size=14, bold=True, color=EMERALD, align=PP_ALIGN.CENTER)
    draw_node(Inches(9.91), y3, Inches(2.72), nh, "END / Rejected", "Saved to SQLite", fill=SOFT_SLATE, border=NAVY)

    # Concise State Reducer Strip
    add_rect(s4, Inches(0.7), Inches(5.9), Inches(11.933), Inches(0.78), fill_color=WHITE, border_color=COBALT, border_pt=1.2)
    add_text_box(
        s4, Inches(0.9), Inches(6.0), Inches(11.5), Inches(0.58),
        text="ResearchState:  merge_papers_reducer (parallel fan-in)   |   operator.add + paper_id skip cache (zero duplicate work)",
        font_size=13.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
    )
    add_notes(
        s4,
        "Here is our complete LangGraph workflow in app/graph/workflow.py. "
        "It connects planning, parallel Send() search workers, deduplication, PDF parsing, verbatim extraction, analysis, bounded critique revision loops, citation verification, human interrupt review, and report generation over shared ResearchState reducers."
    )

    # =========================================================================
    # SLIDE 5: Upstream Pipeline (Minimal 4-Step Funnel)
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_header_footer(s5, 5, "Upstream Pipeline", "Discovery, Deduplication & Ingestion")

    funnel = [
        ("1", "PlannerAgent", COBALT, ["function_calling plan", "3 to 5 search tasks", "Offline keyword fallback"]),
        ("2", "Search Workers", TEAL, ["Parallel Send() fan-out", "arXiv + Semantic Scholar", "HTTP 429 retry backoff"]),
        ("3", "Deduplicator", COBALT, ["Normalized DOI match", "Jaccard title > 0.85", "Year + citation ranking"]),
        ("4", "PDF Retriever", EMERALD, ["15 MB / 15s timeout", "%PDF header check", "Abstract scope fallback"]),
    ]
    fw = Inches(2.78)
    for idx, (num, name, col_c, pts) in enumerate(funnel):
        fx = Inches(0.7) + idx * Inches(3.05)
        add_rect(s5, fx, Inches(1.75), fw, Inches(4.8), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s5, fx, Inches(1.75), fw, Inches(0.9), fill_color=col_c, rounded=False)
        add_badge_circle(s5, fx + Inches(0.18), Inches(1.98), Inches(0.44), num, fill_color=WHITE, text_color=col_c, font_size=15)
        add_text_box(s5, fx + Inches(0.72), Inches(2.03), fw - Inches(0.84), Inches(0.36), text=name, font_size=16, bold=True, color=WHITE)

        tf = add_text_box(s5, fx + Inches(0.22), Inches(3.05), fw - Inches(0.44), Inches(3.2))
        add_bullets(tf, pts, font_size=14, space_after=22)

        if idx < 3:
            add_text_box(s5, fx + fw + Inches(0.02), Inches(3.9), Inches(0.25), Inches(0.4), text=">", font_size=20, bold=True, color=COBALT, align=PP_ALIGN.CENTER)

    add_notes(
        s5,
        "The upstream discovery pipeline runs in four steps. PlannerAgent decomposes the inquiry into 3 to 5 orthogonal search queries. Parallel workers query arXiv and Semantic Scholar with rate-limit backoff. "
        "PaperDeduplicator unifies duplicates via DOI matching and Jaccard title similarity. Finally, PaperRetriever downloads open PDFs under a 15 megabyte and 15 second deadline, cleanly degrading to abstract_only for paywalled manuscripts."
    )

    # =========================================================================
    # SLIDE 6: Zero-Hallucination Core (Minimal JSON + 3 Gates)
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    add_header_footer(s6, 6, "Zero-Hallucination Core", "Verbatim Evidence, Critique & Verification")

    # Left: Compact Evidence Card
    add_rect(s6, Inches(0.7), Inches(1.68), Inches(5.75), Inches(4.95), fill_color=NAVY, border_color=COBALT, border_pt=1.5)
    add_text_box(
        s6, Inches(0.95), Inches(1.88), Inches(5.25), Inches(0.36),
        text="ExtractorAgent Output (Evidence Schema)", font_size=15.5, bold=True, color=SKY,
    )
    sample_json = (
        '{\n'
        '  "paper_id": "paper-2308.03688",\n'
        '  "claim": "24% higher bug fix rate",\n'
        '  "supporting_passage": "Across 300 issues,\n'
        '    multi-agent setup resolved 24% more.",\n'
        '  "content_scope": "full_text",\n'
        '  "confidence": 0.94\n'
        '}'
    )
    add_rect(s6, Inches(0.95), Inches(2.4), Inches(5.25), Inches(3.1), fill_color=RGBColor(30, 41, 59), border_color=RGBColor(71, 85, 105), border_pt=1.0)
    add_text_box(
        s6, Inches(1.15), Inches(2.6), Inches(4.85), Inches(2.7),
        text=sample_json, font_size=13, color=RGBColor(226, 232, 240), font_name=FONT_MONO,
    )
    add_text_box(
        s6, Inches(0.95), Inches(5.82), Inches(5.25), Inches(0.5),
        text="Strict Rule: No verbatim quote = claim rejected",
        font_size=14, bold=True, color=RGBColor(74, 222, 128), align=PP_ALIGN.CENTER,
    )

    gates = [
        ("AnalystAgent", COBALT, ["Cross-paper thematic clustering", "Comparative methodology matrix"]),
        ("CriticAgent", AMBER, ["Coverage score (0.0 to 1.0)", "Max 2 keyword revision cycles"]),
        ("CitationVerifier", EMERALD, ["CrossRef DOI regex check", "100% evidence-claim alignment"]),
    ]
    for idx, (g_head, g_col, g_pts) in enumerate(gates):
        gy = Inches(1.68) + idx * Inches(1.72)
        add_rect(s6, Inches(6.75), gy, Inches(5.88), Inches(1.5), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s6, Inches(6.75), gy, Inches(0.12), Inches(1.5), fill_color=g_col, rounded=False)
        add_text_box(s6, Inches(7.05), gy + Inches(0.16), Inches(5.3), Inches(0.36), text=g_head, font_size=16, bold=True, color=NAVY)
        tf = add_text_box(s6, Inches(7.05), gy + Inches(0.6), Inches(5.3), Inches(0.8))
        add_bullets(tf, g_pts, font_size=13.5, space_after=6)

    add_notes(
        s6,
        "On the left is the exact Evidence contract enforced by ExtractorAgent. Every claim requires a verbatim supporting quote and explicit scope tag. "
        "On the right, AnalystAgent builds cross-study matrices, CriticAgent audits plan coverage and caps automated revisions at two cycles, and CitationVerifier validates every DOI and claim link before report writing."
    )

    # =========================================================================
    # SLIDE 7: Human-in-the-Loop & Persistent Checkpointing
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_header_footer(s7, 7, "Oversight & Persistence", "Human Review Gate & SQLite Persistence")

    hitl_steps = [
        ("1. Interrupt", "interrupt(ReviewPackage)", AMBER),
        ("2. Inspect", "Papers, quotes, audit", COBALT),
        ("3. Decide", "Approve / Revise / Reject", TEAL),
        ("4. Resume", "Command(resume=...)", EMERALD),
    ]
    hw = Inches(2.78)
    for idx, (ht, hd, hc) in enumerate(hitl_steps):
        hx = Inches(0.7) + idx * Inches(3.05)
        add_rect(s7, hx, Inches(1.68), hw, Inches(1.38), fill_color=WHITE, border_color=hc, border_pt=1.5)
        add_rect(s7, hx, Inches(1.68), hw, Inches(0.08), fill_color=hc, rounded=False)
        add_text_box(s7, hx + Inches(0.16), Inches(1.94), hw - Inches(0.32), Inches(0.34), text=ht, font_size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        add_text_box(s7, hx + Inches(0.16), Inches(2.38), hw - Inches(0.32), Inches(0.45), text=hd, font_size=12.5, color=CHARCOAL, align=PP_ALIGN.CENTER, font_name=FONT_MONO)
        if idx < 3:
            add_text_box(s7, hx + hw + Inches(0.02), Inches(2.18), Inches(0.25), Inches(0.35), text="->", font_size=16, bold=True, color=COBALT, align=PP_ALIGN.CENTER)

    add_rect(s7, Inches(0.7), Inches(3.45), Inches(5.82), Inches(3.2), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
    add_rect(s7, Inches(0.7), Inches(3.45), Inches(5.82), Inches(0.46), fill_color=COBALT, rounded=False)
    add_text_box(s7, Inches(0.95), Inches(3.52), Inches(5.3), Inches(0.32), text="Domain Database (service.py)", font_size=14.5, bold=True, color=WHITE)
    tf_db = add_text_box(s7, Inches(0.95), Inches(4.18), Inches(5.3), Inches(2.2))
    add_bullets(tf_db, ["0.2s port 5432 socket probe", "Auto fallback to SQLite research.db", "Eager loading via selectinload", "Isolated temp DB for pytest"], font_size=13.5, space_after=14)

    add_rect(s7, Inches(6.81), Inches(3.45), Inches(5.82), Inches(3.2), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
    add_rect(s7, Inches(6.81), Inches(3.45), Inches(5.82), Inches(0.46), fill_color=EMERALD, rounded=False)
    add_text_box(s7, Inches(7.06), Inches(3.52), Inches(5.3), Inches(0.32), text="Graph Checkpointer (checkpointer.py)", font_size=14.5, bold=True, color=WHITE)
    tf_cp = add_text_box(s7, Inches(7.06), Inches(4.18), Inches(5.3), Inches(2.2))
    add_bullets(tf_cp, ["SQLiteMemorySaver (stdlib sqlite3)", "Zero Windows-blocked DLL imports", "Persists paused HITL interrupts", "Scales to PostgresSaver seamlessly"], font_size=13.5, space_after=14)

    add_notes(
        s7,
        "At the top is our four-step Human-in-the-Loop interrupt flow. Below is our dual persistence design: a 0.2 second socket check routes smoothly between PostgreSQL and local SQLite, "
        "and our custom SQLiteMemorySaver persists LangGraph checkpoints on Python's built-in sqlite3 so paused runs survive server restarts even when binary Postgres drivers are blocked."
    )

    # =========================================================================
    # SLIDE 8: Three Interfaces (Minimal Platform Cards)
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_header_footer(s8, 8, "Full-Stack Delivery", "User, API & Classroom Interfaces")

    interfaces = [
        ("Streamlit Dashboard", ":8501  |  Interactive UI", COBALT, [
            "4 synchronized tabs",
            "Live node progress streaming",
            "Human review inspection tabs",
            "Markdown & PDF downloads",
        ]),
        ("FastAPI Backend", ":8000/docs  |  REST API", TEAL, [
            "12 async REST endpoints",
            "Swagger OpenAPI docs",
            "Background task execution",
            "JSON / MD / PDF exports",
        ]),
        ("Classroom Visual App", "interactive demo/  |  Offline SPA", EMERALD, [
            "Pure HTML, CSS, JavaScript",
            "Step-by-step graph simulator",
            "Live Deduplicator & DOI lab",
            "Chart & 4-question quiz",
        ]),
    ]
    iw = Inches(3.82)
    for idx, (ititle, isub, icol, ipts) in enumerate(interfaces):
        ix = Inches(0.7) + idx * Inches(4.056)
        add_rect(s8, ix, Inches(1.72), iw, Inches(4.92), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s8, ix, Inches(1.72), iw, Inches(0.96), fill_color=SOFT_SLATE, border_color=BORDER, border_pt=1.0, rounded=False)
        add_rect(s8, ix, Inches(1.72), iw, Inches(0.08), fill_color=icol, rounded=False)
        add_text_box(s8, ix + Inches(0.24), Inches(1.92), iw - Inches(0.48), Inches(0.36), text=ititle, font_size=17, bold=True, color=NAVY)
        add_text_box(s8, ix + Inches(0.24), Inches(2.28), iw - Inches(0.48), Inches(0.28), text=isub, font_size=11.5, bold=True, color=icol, font_name=FONT_MONO)

        tf = add_text_box(s8, ix + Inches(0.26), Inches(3.02), iw - Inches(0.52), Inches(3.4))
        add_bullets(tf, ipts, font_size=14.5, space_after=18)

    add_notes(
        s8,
        "MAS-RA runs across three clean interfaces: a four-tab Streamlit dashboard for researchers with live progress streaming and PDF export, "
        "a 12-endpoint FastAPI REST service for programmatic pipelines, and our offline HTML/CSS/JS classroom simulator inside interactive demo."
    )

    # =========================================================================
    # SLIDE 9: Evaluation & Benchmarks (Native Chart + Minimal KPI Cards)
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_header_footer(s9, 9, "Evaluation & QA", "Benchmarks & Automated Verification")

    add_rect(s9, Inches(0.7), Inches(1.68), Inches(7.65), Inches(5.0), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
    add_text_box(
        s9, Inches(0.95), Inches(1.86), Inches(7.1), Inches(0.36),
        text="Single-Prompt Baseline vs MAS-RA Pipeline (%)", font_size=15, bold=True, color=NAVY,
    )

    chart_data = CategoryChartData()
    chart_data.categories = ["DOI Validity", "Claim Grounding", "Full-Text Scope", "Tests Passing"]
    chart_data.add_series("Single-Prompt LLM", (40, 25, 10, 0))
    chart_data.add_series("MAS-RA Multi-Agent", (100, 100, 82, 100))

    chart_frame = s9.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.9), Inches(2.28), Inches(7.25), Inches(4.25), chart_data
    )
    chart = chart_frame.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(11)
    chart.legend.font.name = FONT_MAIN

    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(11)
    plot.data_labels.font.bold = True
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = RGBColor(148, 163, 184)
    plot.series[1].format.fill.solid()
    plot.series[1].format.fill.fore_color.rgb = COBALT
    chart.value_axis.maximum_scale = 110.0
    chart.value_axis.minimum_scale = 0.0
    chart.value_axis.tick_labels.font.size = Pt(10.5)
    chart.category_axis.tick_labels.font.size = Pt(10.5)

    kpis = [
        ("54 / 54", "Pytest Tests Passing (48.5s)", EMERALD),
        ("0.85 Score", "Ablation Quality | 100% Grounded", COBALT),
        ("45 to 90s", "Live End-to-End Review Time", TEAL),
    ]
    for idx, (k_val, k_lbl, k_col) in enumerate(kpis):
        ky = Inches(1.68) + idx * Inches(1.74)
        add_rect(s9, Inches(8.62), ky, Inches(4.01), Inches(1.52), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s9, Inches(8.62), ky, Inches(0.12), Inches(1.52), fill_color=k_col, rounded=False)
        add_text_box(s9, Inches(8.94), ky + Inches(0.24), Inches(3.5), Inches(0.5), text=k_val, font_size=26, bold=True, color=k_col)
        add_text_box(s9, Inches(8.94), ky + Inches(0.84), Inches(3.5), Inches(0.45), text=k_lbl, font_size=13.5, bold=True, color=NAVY)

    add_notes(
        s9,
        "Empirically, MAS-RA lifts DOI validity from around 40 percent to 100 percent and achieves 100 percent verbatim claim grounding. "
        "All 54 pytest unit, API, and workflow tests pass in 48.5 seconds using an isolated test database, and our ablation benchmark scores 0.85 overall quality with 45 to 90 second live latency."
    )

    # =========================================================================
    # SLIDE 10: Conclusion & Future Work (Minimal 3 Columns + Q&A Strip)
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    add_header_footer(s10, 10, "Conclusion", "Lessons Learned, Future Work & Q&A")

    cols = [
        ("Engineering Fixes", COBALT, [
            "function_calling schemas",
            "Stdlib sqlite3 checkpoints",
            "15s PDF deadline guard",
            "XML-safe PDF rendering",
        ]),
        ("Future Roadmap", AMBER, [
            "Vision figure & math OCR",
            "PubMed & IEEE connectors",
            "Persistent pgvector memory",
            "Multi-user review teams",
        ]),
        ("Key Takeaways", EMERALD, [
            "State graphs beat prompts",
            "Verbatim quotes stop errors",
            "HITL keeps human control",
            "54/54 verified test suite",
        ]),
    ]
    cw10 = Inches(3.82)
    for idx, (ctitle, ccol, cpts) in enumerate(cols):
        cx = Inches(0.7) + idx * Inches(4.056)
        add_rect(s10, cx, Inches(1.68), cw10, Inches(3.92), fill_color=WHITE, border_color=BORDER, border_pt=1.2)
        add_rect(s10, cx, Inches(1.68), cw10, Inches(0.08), fill_color=ccol, rounded=False)
        add_text_box(s10, cx + Inches(0.24), Inches(1.94), cw10 - Inches(0.48), Inches(0.36), text=ctitle, font_size=16.5, bold=True, color=NAVY)
        tf = add_text_box(s10, cx + Inches(0.26), Inches(2.55), cw10 - Inches(0.52), Inches(2.8))
        add_bullets(tf, cpts, font_size=14, space_after=16)

    add_rect(s10, Inches(0.7), Inches(5.88), Inches(11.933), Inches(0.86), fill_color=NAVY, border_color=COBALT, border_pt=1.2)
    add_text_box(
        s10, Inches(0.95), Inches(6.02), Inches(4.3), Inches(0.58),
        text="Thank You!  Questions?", font_size=20, bold=True, color=WHITE, valign=MSO_ANCHOR.MIDDLE,
    )
    add_text_box(
        s10, Inches(5.2), Inches(6.02), Inches(7.2), Inches(0.58),
        text="UI: :8501   |   API: :8000/docs   |   Simulator: interactive demo/index.html",
        font_size=12.5, color=SKY, font_name=FONT_MONO, align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE,
    )

    add_notes(
        s10,
        "In closing, building MAS-RA taught us essential production AI engineering fixes: function_calling schemas, restart-safe sqlite3 checkpointers, PDF download timeouts, and safe XML PDF exports. "
        "Future additions include multimodal figure parsing, PubMed integration, and cross-project vector memory. Thank you for listening, and I welcome your questions."
    )

    output_path = os.path.abspath("MAS_RA_Academic_Presentation.pptx")
    prs.save(output_path)
    print(f"Minimal presentation built cleanly: {output_path} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build_deck()
