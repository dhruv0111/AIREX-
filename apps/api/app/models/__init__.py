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
from app.models.release_decision import (
    ReleasePolicy,
    ReleaseDecision,
    ReleaseEvidence,
    ReleaseCheck,
)
from app.models.agent import (
    ToolDefinition,
    AgentDefinition,
    AgentRun,
    AgentTrajectoryStep,
)
from app.models.session import UserSession
from app.models.worker import WorkerHeartbeat, TaskFailure
from app.models.identity import IdentityProvider, OrganizationDomain
from app.models.team import Team, TeamMember, TeamProjectAccess, UserProjectAccess
from app.models.governance import (
    GovernancePolicy,
    ApprovalRequest,
    ApprovalStep,
    ApprovalDecision,
    AccessReview,
    AccessReviewItem,
)
from app.models.compliance import (
    ComplianceFramework,
    ComplianceControl,
    ComplianceEvidence,
    RetentionPolicy,
    LegalHold,
    ComplianceAssessment,
    ComplianceAssessmentItem,
    ComplianceRemediation,
)

__all__ = [
    "ComplianceFramework",
    "ComplianceControl",
    "ComplianceEvidence",
    "RetentionPolicy",
    "LegalHold",
    "ComplianceAssessment",
    "ComplianceAssessmentItem",
    "ComplianceRemediation",
    "User",
    "UserSession",
    "WorkerHeartbeat",
    "TaskFailure",
    "IdentityProvider",
    "OrganizationDomain",
    "Team",
    "TeamMember",
    "TeamProjectAccess",
    "UserProjectAccess",
    "GovernancePolicy",
    "ApprovalRequest",
    "ApprovalStep",
    "ApprovalDecision",
    "AccessReview",
    "AccessReviewItem",
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
    "ReleasePolicy",
    "ReleaseDecision",
    "ReleaseEvidence",
    "ReleaseCheck",
    "ToolDefinition",
    "AgentDefinition",
    "AgentRun",
    "AgentTrajectoryStep",
]
