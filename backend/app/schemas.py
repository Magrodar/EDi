import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["voice", "email", "calendar", "file", "web", "manual"]
Sensitivity = Literal["public", "personal", "confidential", "restricted"]


class EventCreate(BaseModel):
    source_type: SourceType
    source_ref: str | None = None
    occurred_at: datetime | None = None
    observed_at: datetime | None = None  # defaults to now() if omitted
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    actor_person_ids: list[uuid.UUID] = Field(default_factory=list)
    normalized_text: str
    sensitivity: Sensitivity = "personal"
    idempotency_key: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    event_id: uuid.UUID
    source_type: str
    occurred_at: datetime | None
    observed_at: datetime
    normalized_text: str | None
    classifications: list[str]
    sensitivity: str
    confidence: float | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class CaptureTranscriptIn(BaseModel):
    text: str
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    occurred_at: datetime | None = None
    idempotency_key: str | None = None


class FactOut(BaseModel):
    fact_id: uuid.UUID
    subject_type: str
    subject_label: str
    predicate: str
    value_json: Any
    confidence: float
    status: str
    promotion_score: float | None
    effective_from: datetime | None
    effective_to: datetime | None
    source_event_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class CaptureTranscriptOut(BaseModel):
    event: EventOut
    facts: list[FactOut]
    commitments: list["CommitmentOut"]
    risks: list["RiskOut"]
    alerts_created: int


class CommitmentCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: uuid.UUID | None = None
    owner_person_id: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: int | None = None
    cost_of_delay: float | None = None
    dependency_ids: list[uuid.UUID] = Field(default_factory=list)
    source_event_id: uuid.UUID | None = None


class CommitmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    status: Literal["open", "in_progress", "blocked", "done", "cancelled"] | None = None
    priority: int | None = None
    cost_of_delay: float | None = None


class CommitmentOut(BaseModel):
    commitment_id: uuid.UUID
    title: str
    description: str | None
    project_id: uuid.UUID | None
    owner_person_id: uuid.UUID | None
    due_at: datetime | None
    status: str
    priority: int | None
    cost_of_delay: float | None
    source_event_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionCreate(BaseModel):
    question: str
    project_id: uuid.UUID | None = None
    options_json: list[Any] = Field(default_factory=list)
    selected_option: dict[str, Any] | None = None
    assumptions: list[Any] = Field(default_factory=list)
    rationale: str | None = None
    review_at: datetime | None = None
    source_event_id: uuid.UUID | None = None


class DecisionOut(BaseModel):
    decision_id: uuid.UUID
    question: str
    project_id: uuid.UUID | None
    options_json: Any
    selected_option: Any
    assumptions: Any
    rationale: str | None
    review_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: uuid.UUID | None = None
    probability: float | None = None
    impact: float | None = None
    owner_person_id: uuid.UUID | None = None
    trigger_json: dict[str, Any] = Field(default_factory=dict)
    mitigation_json: dict[str, Any] = Field(default_factory=dict)
    source_event_id: uuid.UUID | None = None


class RiskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    probability: float | None = None
    impact: float | None = None
    status: Literal["open", "mitigating", "accepted", "closed"] | None = None
    mitigation_json: dict[str, Any] | None = None


class RiskOut(BaseModel):
    risk_id: uuid.UUID
    title: str
    description: str | None
    project_id: uuid.UUID | None
    probability: float | None
    impact: float | None
    exposure: float | None
    status: str
    owner_person_id: uuid.UUID | None
    source_event_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
    alert_id: uuid.UUID
    level: str
    reason: str
    evidence: Any
    recommended_action: str | None
    related_type: str | None
    related_id: uuid.UUID | None
    intervention_score: float
    status: str
    acknowledged_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyBrief(BaseModel):
    generated_at: datetime
    priority_1: dict[str, Any] | None
    critical_tasks: list[dict[str, Any]]
    decisions_needed: list[dict[str, Any]]
    risks_changed: list[dict[str, Any]]
    waiting_on: list[dict[str, Any]]
    commitments_due_soon: list[dict[str, Any]]
    deep_work_recommendation: str | None
    edi_observation: str | None


class AuditLogOut(BaseModel):
    audit_id: uuid.UUID
    actor: str
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


CaptureTranscriptOut.model_rebuild()
