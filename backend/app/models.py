import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, ForeignKey, Numeric, SmallInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    api_key_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Person(Base):
    __tablename__ = "people"

    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    org: Mapped[str | None] = mapped_column(Text)
    relationship_: Mapped[str | None] = mapped_column("relationship", Text)
    trust_level: Mapped[str | None] = mapped_column(Text)
    contact_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.person_id"))
    status: Mapped[str] = mapped_column(Text, default="active")
    mission_tier: Mapped[int | None] = mapped_column(SmallInteger)
    milestones: Mapped[list] = mapped_column(JSONB, default=list)
    critical_path: Mapped[list] = mapped_column(JSONB, default=list)
    success_criteria: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None]
    observed_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    actor_person_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    project_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    raw_content_ref: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    classifications: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    sensitivity: Mapped[str] = mapped_column(Text, default="personal")
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    retention_policy_id: Mapped[str | None] = mapped_column(Text)
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.event_id"))
    idempotency_key: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="received")


class Fact(Base):
    __tablename__ = "facts"

    fact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    subject_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_label: Mapped[str] = mapped_column(Text)
    predicate: Mapped[str] = mapped_column(Text)
    value_json: Mapped[dict] = mapped_column(JSONB)
    effective_from: Mapped[datetime | None]
    effective_to: Mapped[datetime | None]
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(Text, default="provisional")
    sensitivity: Mapped[str] = mapped_column(Text, default="personal")
    promotion_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.event_id"))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facts.fact_id"))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    deleted_at: Mapped[datetime | None]


class Commitment(Base):
    __tablename__ = "commitments"

    commitment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.project_id"))
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.person_id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(Text, default="open")
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    cost_of_delay: Mapped[float | None] = mapped_column(Numeric(5, 2))
    dependency_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.event_id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.project_id"))
    question: Mapped[str] = mapped_column(Text)
    options_json: Mapped[list] = mapped_column(JSONB, default=list)
    selected_option: Mapped[dict | None] = mapped_column(JSONB)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text)
    review_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(Text, default="open")
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.event_id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Risk(Base):
    __tablename__ = "risks"

    risk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.project_id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[float | None] = mapped_column(Numeric(4, 3))
    impact: Mapped[float | None] = mapped_column(Numeric(4, 3))
    exposure: Mapped[float | None] = mapped_column(Numeric(6, 3))
    status: Mapped[str] = mapped_column(Text, default="open")
    trigger_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    mitigation_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.person_id"))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.event_id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    related_type: Mapped[str | None] = mapped_column(Text)
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    dedup_key: Mapped[str] = mapped_column(Text)
    intervention_score: Mapped[float] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(Text, default="candidate")
    acknowledged_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
