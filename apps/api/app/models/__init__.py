"""ORM model registry — imports all models so Base.metadata is complete."""

from app.models.alert import Alert, AlertRule
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetVersion, TestCase
from app.models.evaluation import EvaluationResult, EvaluationRun
from app.models.experiment import Experiment, Prompt, PromptVersion
from app.models.generation import GeneratedCandidate, GenerationRequest
from app.models.invocation import ModelInvocation
from app.models.organization import Organization, OrganizationMember
from app.models.project import Environment, Project
from app.models.provider import Model, Provider
from app.models.rubric import Rubric
from app.models.trace import Trace, TraceEvent
from app.models.user import User

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
    "Prompt",
    "PromptVersion",
    "Trace",
    "TraceEvent",
    "AlertRule",
    "Alert",
    "AuditLog",
    "ModelInvocation",
    "Rubric",
    "GenerationRequest",
    "GeneratedCandidate",
]
