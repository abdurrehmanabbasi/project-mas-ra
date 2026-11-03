"""Evaluation metrics computation engine for literature review benchmarks."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from app.schemas.evidence import Evidence
from app.schemas.papers import Paper
from app.schemas.report import CitationCheck, ResearchReport


@dataclass
class CitationEvaluationResult:
    """Metrics assessing citation validity and claim support."""

    total_citations: int
    valid_dois_count: int
    accessible_urls_count: int
    supported_claims_count: int
    doi_validity_rate: float
    url_accessibility_rate: float
    claim_support_rate: float


@dataclass
class EvidenceEvaluationResult:
    """Metrics assessing empirical evidence grounding and extraction fidelity."""

    total_evidence_records: int
    full_text_count: int
    abstract_only_count: int
    full_text_ratio: float
    average_confidence: float
    grounded_passage_ratio: float


@dataclass
class CoverageEvaluationResult:
    """Metrics assessing topic coverage relative to target benchmark dimensions."""

    target_topics_count: int
    covered_topics_count: int
    coverage_score: float
    missing_topics: List[str]


@dataclass
class SystemBenchmarkScore:
    """Comprehensive multi-dimensional evaluation score for an autonomous research run."""

    citation_metrics: CitationEvaluationResult
    evidence_metrics: EvidenceEvaluationResult
    coverage_metrics: CoverageEvaluationResult
    composite_quality_score: float
    execution_latency_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCalculator:
    """Computes quantitative evaluation scores from execution artifacts and benchmarks."""

    @staticmethod
    def evaluate_citations(checks: List[CitationCheck]) -> CitationEvaluationResult:
        """Calculate DOI validity, URL accessibility, and claim grounding percentages."""
        if not checks:
            return CitationEvaluationResult(
                total_citations=0,
                valid_dois_count=0,
                accessible_urls_count=0,
                supported_claims_count=0,
                doi_validity_rate=1.0,
                url_accessibility_rate=1.0,
                claim_support_rate=1.0,
            )

        total = len(checks)
        valid_dois = sum(1 for c in checks if c.doi_valid)
        acc_urls = sum(1 for c in checks if c.url_accessible)
        supported = sum(1 for c in checks if c.claim_supported)

        return CitationEvaluationResult(
            total_citations=total,
            valid_dois_count=valid_dois,
            accessible_urls_count=acc_urls,
            supported_claims_count=supported,
            doi_validity_rate=round(valid_dois / total, 4),
            url_accessibility_rate=round(acc_urls / total, 4),
            claim_support_rate=round(supported / total, 4),
        )

    @staticmethod
    def evaluate_evidence(evidence_records: List[Evidence]) -> EvidenceEvaluationResult:
        """Measure evidence grounding and content provenance."""
        if not evidence_records:
            return EvidenceEvaluationResult(
                total_evidence_records=0,
                full_text_count=0,
                abstract_only_count=0,
                full_text_ratio=0.0,
                average_confidence=0.0,
                grounded_passage_ratio=0.0,
            )

        total = len(evidence_records)
        ft_count = sum(1 for e in evidence_records if e.content_scope == "full_text")
        abs_count = sum(1 for e in evidence_records if e.content_scope == "abstract_only")
        avg_conf = sum(e.extraction_confidence for e in evidence_records) / total
        grounded = sum(1 for e in evidence_records if e.supporting_passage and len(e.supporting_passage.strip()) > 10)

        return EvidenceEvaluationResult(
            total_evidence_records=total,
            full_text_count=ft_count,
            abstract_only_count=abs_count,
            full_text_ratio=round(ft_count / total, 4),
            average_confidence=round(avg_conf, 4),
            grounded_passage_ratio=round(grounded / total, 4),
        )

    @staticmethod
    def evaluate_coverage(report_content: str, target_topics: List[str]) -> CoverageEvaluationResult:
        """Check presence of benchmark target topics in the final literature review."""
        if not target_topics:
            return CoverageEvaluationResult(
                target_topics_count=0,
                covered_topics_count=0,
                coverage_score=1.0,
                missing_topics=[],
            )

        content_lower = report_content.lower()
        covered = []
        missing = []

        for topic in target_topics:
            keywords = [w.lower() for w in topic.split() if len(w) > 3]
            match_count = sum(1 for kw in keywords if kw in content_lower)
            # If at least 50% of distinctive topic words appear, count as covered
            if match_count >= max(1, len(keywords) // 2):
                covered.append(topic)
            else:
                missing.append(topic)

        coverage_ratio = len(covered) / len(target_topics)
        return CoverageEvaluationResult(
            target_topics_count=len(target_topics),
            covered_topics_count=len(covered),
            coverage_score=round(coverage_ratio, 4),
            missing_topics=missing,
        )

    @classmethod
    def calculate_system_score(
        cls,
        report: ResearchReport,
        target_topics: List[str],
        evidence_records: List[Evidence],
        latency_seconds: float = 0.0,
    ) -> SystemBenchmarkScore:
        """Compute holistic system quality score combining citations, evidence, and coverage."""
        cit_res = cls.evaluate_citations(report.citation_checks)
        ev_res = cls.evaluate_evidence(evidence_records)
        report_text = report.abstract + " " + report.introduction + " " + report.comparative_analysis
        for s in report.sections:
            report_text += " " + s.content
        cov_res = cls.evaluate_coverage(report_text, target_topics)

        # Composite quality score: 40% claim support, 35% topic coverage, 25% evidence grounding
        composite = (
            0.40 * cit_res.claim_support_rate
            + 0.35 * cov_res.coverage_score
            + 0.25 * ev_res.grounded_passage_ratio
        )

        return SystemBenchmarkScore(
            citation_metrics=cit_res,
            evidence_metrics=ev_res,
            coverage_metrics=cov_res,
            composite_quality_score=round(composite, 4),
            execution_latency_seconds=round(latency_seconds, 2),
        )

