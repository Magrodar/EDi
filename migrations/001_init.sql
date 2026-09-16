-- Ultimate EDI reference schema (Phase 0+1 core).
-- UUID PKs, UTC timestamps, idempotency keys, row-scoped by user_id (single user today,
-- schema is ready for household/family multi-user later).

create extension if not exists pgcrypto;
create extension if not exists vector;

create table users (
  user_id uuid primary key default gen_random_uuid(),
  email text not null unique,
  api_key_hash text not null,
  display_name text,
  created_at timestamptz not null default now()
);

create table people (
  person_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  name text not null,
  role text,
  org text,
  relationship text,
  trust_level text,
  contact_refs jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table projects (
  project_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  name text not null,
  objective text,
  owner_person_id uuid references people(person_id),
  status text not null default 'active',
  mission_tier smallint,                 -- 0=redline, 1=Glowin/Planning/Investing, 2=learning
  milestones jsonb not null default '[]'::jsonb,
  critical_path jsonb not null default '[]'::jsonb,
  success_criteria text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table events (
  event_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  source_type text not null check (source_type in ('voice','email','calendar','file','web','manual')),
  source_ref text,
  occurred_at timestamptz,
  observed_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  actor_person_ids uuid[] not null default '{}',
  project_ids uuid[] not null default '{}',
  raw_content_ref text,
  normalized_text text,
  classifications text[] not null default '{}',
  sensitivity text not null default 'personal'
    check (sensitivity in ('public','personal','confidential','restricted')),
  confidence numeric(4,3),
  provenance jsonb not null default '{}'::jsonb,
  retention_policy_id text,
  supersedes_event_id uuid references events(event_id),
  idempotency_key text not null,
  content_hash text,
  status text not null default 'received'
    check (status in ('received','validated','normalized','extracted','evaluated',
                       'stored_ephemeral','promoted','rejected','quarantined')),
  unique (user_id, idempotency_key)
);

create table facts (
  fact_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  subject_type text not null,          -- e.g. 'project','person','material','forecast'
  subject_id uuid,
  subject_label text not null,         -- human-readable subject when subject_id has no FK target
  predicate text not null,
  value_json jsonb not null,
  effective_from timestamptz,
  effective_to timestamptz,
  recorded_at timestamptz not null default now(),
  confidence numeric(4,3) not null,
  status text not null default 'provisional'
    check (status in ('provisional','canonical','conflicted','superseded','deleted')),
  sensitivity text not null default 'personal'
    check (sensitivity in ('public','personal','confidential','restricted')),
  promotion_score numeric(4,3),
  source_event_id uuid references events(event_id),
  superseded_by uuid references facts(fact_id),
  embedding vector(1536),
  deleted_at timestamptz
);

create table commitments (
  commitment_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  project_id uuid references projects(project_id),
  owner_person_id uuid references people(person_id),
  title text not null,
  description text,
  due_at timestamptz,
  status text not null default 'open'
    check (status in ('open','in_progress','blocked','done','cancelled')),
  priority smallint,
  cost_of_delay numeric(5,2),
  dependency_ids uuid[] not null default '{}',
  source_event_id uuid references events(event_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table decisions (
  decision_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  project_id uuid references projects(project_id),
  question text not null,
  options_json jsonb not null default '[]'::jsonb,
  selected_option jsonb,
  assumptions jsonb not null default '[]'::jsonb,
  rationale text,
  review_at timestamptz,
  status text not null default 'open'
    check (status in ('open','decided','reviewed','reversed')),
  source_event_id uuid references events(event_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table risks (
  risk_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  project_id uuid references projects(project_id),
  title text not null,
  description text,
  probability numeric(4,3),
  impact numeric(4,3),
  exposure numeric(6,3),
  status text not null default 'open'
    check (status in ('open','mitigating','accepted','closed')),
  trigger_json jsonb not null default '{}'::jsonb,
  mitigation_json jsonb not null default '{}'::jsonb,
  owner_person_id uuid references people(person_id),
  source_event_id uuid references events(event_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table alerts (
  alert_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(user_id) on delete cascade,
  level text not null check (level in ('info','advisory','warning','command_alert')),
  reason text not null,
  evidence jsonb not null default '[]'::jsonb,
  recommended_action text,
  related_type text,                    -- 'commitment' | 'risk' | 'fact' | ...
  related_id uuid,
  dedup_key text not null,
  intervention_score numeric(4,3) not null,
  status text not null default 'candidate'
    check (status in ('candidate','suppressed','brief_queue','advisory_sent','warning_sent',
                       'command_alert_sent','acknowledged','actioned','resolved')),
  acknowledged_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table audit_log (
  audit_id uuid primary key default gen_random_uuid(),
  user_id uuid references users(user_id) on delete set null,
  actor text not null,                  -- 'user' | 'system' | 'rule:<name>' | 'model:<name>'
  action text not null,                 -- e.g. 'create','update','delete','ack'
  entity_type text not null,
  entity_id uuid,
  before_json jsonb,
  after_json jsonb,
  created_at timestamptz not null default now()
);

create index idx_facts_subject_predicate on facts(user_id, subject_type, subject_id, predicate);
create index idx_facts_status on facts(user_id, status);
create index idx_commitments_due on commitments(user_id, status, due_at);
create index idx_risks_active on risks(user_id, status, exposure desc);
create index idx_events_project on events using gin(project_ids);
create index idx_alerts_dedup on alerts(user_id, dedup_key, status);
create index idx_audit_entity on audit_log(user_id, entity_type, entity_id);
