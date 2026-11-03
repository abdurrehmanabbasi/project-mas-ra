"""Autonomous AI research agents."""

__all__ = ["PlannerAgent", "ExtractorAgent", "AnalystAgent", "CriticAgent", "ReportWriterAgent"]


def __getattr__(name: str):
    if name == "PlannerAgent":
        from app.agents.planner import PlannerAgent
        return PlannerAgent
    if name == "ExtractorAgent":
        from app.agents.extractor import ExtractorAgent
        return ExtractorAgent
    if name == "AnalystAgent":
        from app.agents.analyst import AnalystAgent
        return AnalystAgent
    if name == "CriticAgent":
        from app.agents.critic import CriticAgent
        return CriticAgent
    if name == "ReportWriterAgent":
        from app.agents.writer import ReportWriterAgent
        return ReportWriterAgent
    raise AttributeError(f"module {__name__} has no attribute {name}")
