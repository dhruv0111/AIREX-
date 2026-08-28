"""ORM model registry — imports all models so Base.metadata is complete."""

from app.models.alert import Alert, AlertRule
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetVersion, TestCase
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.models.experiment import (
    Experiment,
    ExperimentComparison,
    ExperimentRun,
    ExperimentVariant,
    Prompt,
    PromptVersion,
    QualityGate,
    QualityGateResult,
    Regression,
)
from app.models.generation import GeneratedCandidate, GenerationRequest
from app.models.invocation import ModelInvocation
from app.models.organization import Organization, OrganizationMember
from app.models.project import Environment, Project
from app.models.provider import Model, Provider
from app.models.rubric import Rubric
from app.models.pricing import ModelPricing
from app.models.trace import Trace, Span
from app.models.ci import CIRun, ServiceToken
from app.models.user import User
from app.models.benchmark import (
    BenchmarkSuite,
    BenchmarkVersion,
    BenchmarkRun,
    BenchmarkResult,
    ReliabilityEvidence,
    FailureCluster,
    RootCauseRecommendation,
)

__all__ = [
    "User",
    "Organization",
    "OrganizationMember",
    "Project",
    "Environment",
    "Provider",
    "Model",
    "Dataset",
    "DatasetVersion",
    "TestCase",
    "EvaluationRun",
    "EvaluationResult",
    "Experiment",
    "ExperimentVariant",
    "ExperimentRun",
    "ExperimentComparison",
    "Regression",
    "QualityGate",
    "QualityGateResult",
    "Prompt",
    "PromptVersion",
    "Trace",
    "Span",
    "ModelPricing",
    "AlertRule",
    "Alert",
    "AuditLog",
    "ModelInvocation",
    "Rubric",
    "GenerationRequest",
    "GeneratedCandidate",
    "ServiceToken",
    "CIRun",
    "BenchmarkSuite",
    "BenchmarkVersion",
    "BenchmarkRun",
    "BenchmarkResult",
    "ReliabilityEvidence",
    "FailureCluster",
    "RootCauseRecommendation",
]
