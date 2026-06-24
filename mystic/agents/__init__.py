"""Agent registry."""

from mystic.agents.core_agent import CoreAgent
from mystic.agents.discovery import ConjectureAgent, ForgeAgent, PatternAgent, SimulatorAgent
from mystic.agents.memory import ArchiveAgent, EvolutionAgent, KnowledgeGraphAgent
from mystic.agents.pure_math import (
    AlgebraAgent,
    AnalysisAgent,
    GeoAgent,
    LogicAgent,
    PrimeAgent,
    ProbabilityAgent,
)
from mystic.agents.report_agent import ReportAgent
from mystic.agents.science import BioMathAgent, ChemAgent, ComplexityAgent, PhysicsAgent
from mystic.agents.verification import LeanAgent, RavenAgent, SMTAgent

AGENT_TYPES = {
    "prime": PrimeAgent,
    "algebra": AlgebraAgent,
    "geo": GeoAgent,
    "analysis": AnalysisAgent,
    "probability": ProbabilityAgent,
    "logic": LogicAgent,
    "physics": PhysicsAgent,
    "complexity": ComplexityAgent,
    "biomath": BioMathAgent,
    "chem": ChemAgent,
    "forge": ForgeAgent,
    "conjecture": ConjectureAgent,
    "pattern": PatternAgent,
    "simulator": SimulatorAgent,
    "lean": LeanAgent,
    "smt": SMTAgent,
    "raven": RavenAgent,
    "archive": ArchiveAgent,
    "knowledge_graph": KnowledgeGraphAgent,
    "evolution": EvolutionAgent,
    "report": ReportAgent,
}

__all__ = ["AGENT_TYPES", "CoreAgent", "ReportAgent"]

