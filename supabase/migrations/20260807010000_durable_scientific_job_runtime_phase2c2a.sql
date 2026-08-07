-- Phase 2C.2A: additive durable scientific job runtime.
-- This migration is intentionally not auto-applied.  All job-worker RPCs are
-- service_role-only; public MCP endpoints use constrained operator RPCs only.

-- Supabase installs extensions in this schema. This is required only for
-- SHA-256 hashing of opaque lease tokens; raw lease tokens are never stored.
create extension if not exists pgcrypto with schema extensions;

alter table public.lab_research_campaigns
  add column if not exists scientific_jobs jsonb not null default '[]'::jsonb,
  add column if not exists scientific_job_attachments jsonb not null default '[]'::jsonb;

create table if not exists public.lab_scientific_jobs (
  job_id text primary key check (job_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'),
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete restrict,
  campaign_revision bigint not null check (campaign_revision >= 0),
  attachment_campaign_revision bigint not null check (attachment_campaign_revision >= 0),
  job_type text not null check (char_length(job_type) between 1 and 80),
  engine_name text not null check (engine_name ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'),
  engine_version text not null check (engine_version ~ '^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$'),
  input_payload jsonb not null check (jsonb_typeof(input_payload) = 'object' and octet_length(input_payload::text) <= 131072),
  input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('PENDING','READY','LEASED','RUNNING','SUCCEEDED','FAILED','RETRY_WAIT','CANCELLED','DEAD_LETTER')),
  attempt integer not null default 0 check (attempt >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  ready_at timestamptz not null default timezone('utc', now()),
  lease_owner text not null default '' check (char_length(lease_owner) <= 160),
  lease_token_hash text not null default '' check (lease_token_hash = '' or lease_token_hash ~ '^[0-9a-f]{64}$'),
  lease_acquired_at timestamptz,
  lease_expires_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  completed_lease_owner text not null default '' check (char_length(completed_lease_owner) <= 160),
  completed_lease_token_hash text not null default '' check (completed_lease_token_hash = '' or completed_lease_token_hash ~ '^[0-9a-f]{64}$'),
  result jsonb,
  result_hash text not null default '' check (result_hash = '' or result_hash ~ '^[0-9a-f]{64}$'),
  result_schema_version text not null default '2C.2A' check (result_schema_version = '2C.2A'),
  error text not null default '' check (char_length(error) <= 1000),
  failure_class text not null default '' check (failure_class in ('','VALIDATION','ENGINE_TRANSIENT','ENGINE_PERMANENT','LEASE_EXPIRED','DISPATCH','CAMPAIGN_STALE','RESULT_CONFLICT','CANCELLED','INTERNAL')),
  failure jsonb,
  cancellation_requested boolean not null default false,
  attachment_status text not null default '' check (attachment_status in ('','PENDING','ATTACHED','REJECTED')),
  attachment_key text not null default '' check (char_length(attachment_key) <= 240),
  attachment_error text not null default '' check (char_length(attachment_error) <= 1000),
  failure_attachment_state text not null default '' check (failure_attachment_state in ('','ATTACHED','REJECTED')),
  failure_attachment_error text not null default '' check (char_length(failure_attachment_error) <= 1000),
  idempotency_key text not null default '' check (char_length(idempotency_key) <= 160),
  correlation_id text not null default '' check (char_length(correlation_id) <= 160),
  experiment_id text not null default '' check (char_length(experiment_id) <= 160),
  duplicate_completion_count integer not null default 0 check (duplicate_completion_count >= 0),
  duplicate_completion_rejected_count integer not null default 0 check (duplicate_completion_rejected_count >= 0),
  result_replay_count integer not null default 0 check (result_replay_count >= 0),
  conflicting_result_count integer not null default 0 check (conflicting_result_count >= 0),
  reconciliation_count integer not null default 0 check (reconciliation_count >= 0),
  revision bigint not null default 0 check (revision >= 0),
  schema_version text not null default '2C.2A' check (schema_version = '2C.2A'),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (attempt <= max_attempts),
  check ((status in ('LEASED','RUNNING')) = (lease_owner <> '' and lease_token_hash <> '' and lease_acquired_at is not null and lease_expires_at is not null)),
  check (status <> 'SUCCEEDED' or (result is not null and result_hash <> '')),
  check (status not in ('FAILED','DEAD_LETTER') or failure is not null)
);

create table if not exists public.lab_scientific_job_leases (
  lease_id text primary key,
  job_id text not null references public.lab_scientific_jobs(job_id) on delete restrict,
  lease_owner text not null check (char_length(lease_owner) between 1 and 160),
  token_hash text not null check (token_hash ~ '^[0-9a-f]{64}$'),
  acquired_at timestamptz not null default timezone('utc', now()),
  expires_at timestamptz not null,
  heartbeat_count integer not null default 0 check (heartbeat_count >= 0),
  released_at timestamptz,
  release_reason text not null default '' check (char_length(release_reason) <= 160),
  schema_version text not null default '2C.2A' check (schema_version = '2C.2A')
);

create table if not exists public.lab_scientific_job_outbox_events (
  event_id text primary key,
  job_id text not null references public.lab_scientific_jobs(job_id) on delete restrict,
  event_type text not null default 'SCIENTIFIC_JOB_READY' check (char_length(event_type) between 1 and 80),
  payload_hash text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
  status text not null default 'PENDING' check (status in ('PENDING','DISPATCHED','ACKNOWLEDGED','FAILED')),
  attempt integer not null default 0 check (attempt >= 0),
  available_at timestamptz not null default timezone('utc', now()),
  dispatched_at timestamptz,
  acknowledged_at timestamptz,
  safe_error text not null default '' check (char_length(safe_error) <= 1000),
  revision bigint not null default 0 check (revision >= 0),
  schema_version text not null default '2C.2A' check (schema_version = '2C.2A'),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.lab_scientific_job_attachments (
  job_id text primary key references public.lab_scientific_jobs(job_id) on delete restrict,
  campaign_id text not null references public.lab_research_campaigns(campaign_id) on delete restrict,
  campaign_revision bigint not null check (campaign_revision >= 0),
  attachment_key text not null unique check (char_length(attachment_key) between 1 and 240),
  result_hash text not null check (result_hash ~ '^[0-9a-f]{64}$'),
  artifact_id text not null unique,
  attached_at timestamptz not null default timezone('utc', now()),
  schema_version text not null default '2C.2A' check (schema_version = '2C.2A')
);

create table if not exists public.lab_scientific_job_events (
  event_id text primary key,
  job_id text not null references public.lab_scientific_jobs(job_id) on delete restrict,
  event_type text not null check (char_length(event_type) between 1 and 80),
  status text not null check (status in ('PENDING','READY','LEASED','RUNNING','SUCCEEDED','FAILED','RETRY_WAIT','CANCELLED','DEAD_LETTER')),
  revision bigint not null check (revision >= 0),
  summary text not null check (char_length(summary) between 1 and 1000),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default timezone('utc', now()),
  schema_version text not null default '2C.2A' check (schema_version = '2C.2A')
);

create unique index if not exists lab_scientific_jobs_campaign_idempotency_idx
  on public.lab_scientific_jobs(campaign_id, idempotency_key) where idempotency_key <> '';
create index if not exists lab_scientific_jobs_ready_idx
  on public.lab_scientific_jobs(status, ready_at, job_id) where status = 'READY';
create index if not exists lab_scientific_jobs_lease_expiry_idx
  on public.lab_scientific_jobs(lease_expires_at, job_id) where status in ('LEASED','RUNNING');
create index if not exists lab_scientific_jobs_campaign_idx
  on public.lab_scientific_jobs(campaign_id, created_at desc);
create unique index if not exists lab_scientific_job_leases_one_active_idx
  on public.lab_scientific_job_leases(job_id) where released_at is null;
create index if not exists lab_scientific_job_outbox_pending_idx
  on public.lab_scientific_job_outbox_events(status, available_at, event_id) where status in ('PENDING','FAILED');
create index if not exists lab_scientific_job_outbox_stale_idx
  on public.lab_scientific_job_outbox_events(dispatched_at, event_id) where status = 'DISPATCHED';
create index if not exists lab_scientific_job_events_job_idx
  on public.lab_scientific_job_events(job_id, created_at);

alter table public.lab_scientific_jobs enable row level security;
alter table public.lab_scientific_job_leases enable row level security;
alter table public.lab_scientific_job_outbox_events enable row level security;
alter table public.lab_scientific_job_attachments enable row level security;
alter table public.lab_scientific_job_events enable row level security;
revoke all on public.lab_scientific_jobs, public.lab_scientific_job_leases,
  public.lab_scientific_job_outbox_events, public.lab_scientific_job_attachments,
  public.lab_scientific_job_events from anon, authenticated;
grant select, insert, update, delete on public.lab_scientific_jobs, public.lab_scientific_job_leases,
  public.lab_scientific_job_outbox_events, public.lab_scientific_job_attachments,
  public.lab_scientific_job_events to service_role;

create or replace function public.mystic_scientific_job_token_hash(p_token text)
returns text language sql immutable strict set search_path = public, pg_temp as $$
  select encode(extensions.digest(convert_to(p_token, 'utf8'), 'sha256'), 'hex')
$$;

-- This mirrors Mystic's canonical JSON hash contract: object keys are sorted,
-- arrays preserve order, and no arbitrary serialized object is accepted.
create or replace function public.mystic_scientific_job_canonical_json(p_value jsonb)
returns text language sql immutable strict set search_path = pg_catalog, public, pg_temp as $$
  select case jsonb_typeof(p_value)
    when 'object' then '{' || coalesce((
      select string_agg(to_jsonb(key)::text || ':' || public.mystic_scientific_job_canonical_json(value), ',' order by key collate "C")
      from jsonb_each(p_value)
    ), '') || '}'
    when 'array' then '[' || coalesce((
      select string_agg(public.mystic_scientific_job_canonical_json(value), ',' order by ordinality)
      from jsonb_array_elements(p_value) with ordinality as entry(value, ordinality)
    ), '') || ']'
    else p_value::text
  end
$$;

create or replace function public.mystic_scientific_job_payload_hash(p_value jsonb)
returns text language sql immutable strict set search_path = public, pg_temp as $$
  select encode(extensions.digest(convert_to(public.mystic_scientific_job_canonical_json(p_value), 'utf8'), 'sha256'), 'hex')
$$;

create or replace function public.mystic_create_scientific_job(
  p_job_id text,
  p_campaign_id text,
  p_campaign_revision bigint,
  p_job_type text,
  p_engine_name text,
  p_engine_version text,
  p_input_payload jsonb,
  p_input_hash text,
  p_max_attempts integer default 3,
  p_idempotency_key text default '',
  p_correlation_id text default '',
  p_experiment_id text default '',
  p_schema_version text default '2C.2A'
) returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_campaign public.lab_research_campaigns;
  current_job public.lab_scientific_jobs;
  next_campaign_revision bigint;
  outbox_id text;
begin
  if p_schema_version <> '2C.2A' then raise exception 'scientific_job_schema_version_invalid'; end if;
  if p_job_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
    or p_campaign_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
    or p_engine_name !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
    or p_engine_version !~ '^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$'
    or char_length(p_job_type) not between 1 and 80
    or p_input_hash !~ '^[0-9a-f]{64}$'
    or jsonb_typeof(p_input_payload) <> 'object'
    or octet_length(p_input_payload::text) > 131072
    or p_input_hash <> public.mystic_scientific_job_payload_hash(p_input_payload)
    or p_max_attempts not between 1 and 10
    or char_length(p_idempotency_key) > 160
    or char_length(p_correlation_id) > 160
    or char_length(p_experiment_id) > 160
    or (p_experiment_id <> '' and p_experiment_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$') then
    raise exception 'scientific_job_input_invalid';
  end if;
  if not exists (
    select 1 from public.lab_engine_registry
      where engine_id=p_engine_name and version=p_engine_version and enabled and not deprecated
  ) then
    raise exception 'scientific_job_engine_unavailable';
  end if;

  select * into current_job from public.lab_scientific_jobs where job_id = p_job_id for update;
  if found then
    if current_job.campaign_id = p_campaign_id and current_job.input_hash = p_input_hash
      and current_job.engine_name = p_engine_name and current_job.engine_version = p_engine_version
      and current_job.experiment_id = p_experiment_id and current_job.max_attempts = p_max_attempts
      and current_job.idempotency_key = p_idempotency_key then
      return current_job;
    end if;
    raise exception 'scientific_job_id_conflict';
  end if;
  if p_idempotency_key <> '' then
    select * into current_job from public.lab_scientific_jobs
      where campaign_id = p_campaign_id and idempotency_key = p_idempotency_key for update;
    if found then
      if current_job.input_hash = p_input_hash and current_job.engine_name = p_engine_name
        and current_job.engine_version = p_engine_version and current_job.experiment_id = p_experiment_id
        and current_job.max_attempts = p_max_attempts then return current_job; end if;
      raise exception 'scientific_job_idempotency_conflict';
    end if;
  end if;

  select * into current_campaign from public.lab_research_campaigns
    where campaign_id = p_campaign_id for update;
  if not found then raise exception 'campaign_not_found'; end if;
  if current_campaign.status <> 'ACTIVE' then raise exception 'campaign_not_active'; end if;
  if current_campaign.revision <> p_campaign_revision then raise exception 'campaign_revision_conflict'; end if;
  if p_experiment_id <> '' and not exists (
    select 1 from jsonb_array_elements(coalesce(current_campaign.experiments,'[]'::jsonb)) as experiment(value)
      where experiment.value->>'experiment_id'=p_experiment_id
  ) then
    raise exception 'scientific_job_experiment_not_found';
  end if;

  next_campaign_revision := current_campaign.revision + 1;
  insert into public.lab_scientific_jobs(
    job_id,campaign_id,campaign_revision,attachment_campaign_revision,job_type,engine_name,engine_version,
    input_payload,input_hash,status,max_attempts,ready_at,idempotency_key,correlation_id,experiment_id,schema_version
  ) values (
    p_job_id,p_campaign_id,p_campaign_revision,next_campaign_revision,p_job_type,p_engine_name,p_engine_version,
    p_input_payload,p_input_hash,'READY',p_max_attempts,timezone('utc',now()),p_idempotency_key,
    case when p_correlation_id = '' then p_job_id else p_correlation_id end,p_experiment_id,p_schema_version
  ) returning * into current_job;
  outbox_id := 'job_outbox_' || replace(gen_random_uuid()::text, '-', '');
  insert into public.lab_scientific_job_outbox_events(event_id,job_id,payload_hash)
    values (outbox_id,p_job_id,p_input_hash);
  update public.lab_research_campaigns set
    scientific_jobs = coalesce(scientific_jobs, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
      'reference_id','job_ref_' || replace(gen_random_uuid()::text, '-', ''),'campaign_id',p_campaign_id,
      'job_id',p_job_id,'job_type',p_job_type,'engine_name',p_engine_name,'engine_version',p_engine_version,
      'source_campaign_revision',p_campaign_revision,'attachment_campaign_revision',next_campaign_revision,
      'experiment_id',p_experiment_id,'status','READY','created_at',timezone('utc',now()))),
    statistics=jsonb_set(statistics,'{scientific_job_count}',
      to_jsonb(coalesce((statistics->>'scientific_job_count')::integer,0)+1),true),
    revision = next_campaign_revision,
    updated_at = timezone('utc',now())
    where campaign_id = p_campaign_id;
  insert into public.lab_campaign_timeline(event_id,campaign_id,event_type,phase,status,summary,revision,metadata)
    values ('event_' || replace(gen_random_uuid()::text, '-', ''),p_campaign_id,'SCIENTIFIC_JOB_INTENT_CREATED',
      current_campaign.phase,current_campaign.status,'Scientific engine job intent recorded for durable dispatch.',next_campaign_revision,
      jsonb_build_object('job_id',p_job_id,'engine_name',p_engine_name,'engine_version',p_engine_version,
        'source_campaign_revision',p_campaign_revision));
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_READY','READY',current_job.revision,
      'Scientific job and durable dispatch intent persisted.',jsonb_build_object('outbox_event_id',outbox_id));
  return current_job;
end $$;

create or replace function public.mystic_acquire_scientific_job_lease(
  p_worker_id text,
  p_lease_seconds integer default 60
) returns table(job_id text, lease_token text, lease_expires_at timestamptz, attempt integer, revision bigint)
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  raw_token text;
  token_hash text;
  now_value timestamptz := timezone('utc',now());
  next_expiry timestamptz;
begin
  if char_length(p_worker_id) not between 1 and 160 or p_lease_seconds not between 10 and 300 then
    raise exception 'scientific_job_lease_input_invalid';
  end if;
  select * into current_job from public.lab_scientific_jobs
    where status = 'READY' and ready_at <= now_value and attempt < max_attempts and not cancellation_requested
    order by ready_at, job_id for update skip locked limit 1;
  if not found then return; end if;
  raw_token := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
  token_hash := public.mystic_scientific_job_token_hash(raw_token);
  next_expiry := now_value + make_interval(secs => p_lease_seconds);
  update public.lab_scientific_jobs set
    status='LEASED',attempt=attempt+1,lease_owner=p_worker_id,lease_token_hash=token_hash,
    lease_acquired_at=now_value,lease_expires_at=next_expiry,revision=revision+1,updated_at=now_value
    where job_id=current_job.job_id
    returning * into current_job;
  insert into public.lab_scientific_job_leases(
    lease_id,job_id,lease_owner,token_hash,acquired_at,expires_at
  ) values ('job_lease_' || replace(gen_random_uuid()::text, '-', ''),current_job.job_id,p_worker_id,token_hash,now_value,next_expiry);
  update public.lab_scientific_job_outbox_events set status='ACKNOWLEDGED',acknowledged_at=now_value,
    revision=revision+1,updated_at=now_value where job_id=current_job.job_id and status='DISPATCHED';
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),current_job.job_id,'LEASE_ACQUIRED','LEASED',current_job.revision,
      'Scientific job leased to one worker.',jsonb_build_object('lease_owner',p_worker_id,'attempt',current_job.attempt));
  job_id := current_job.job_id;
  lease_token := raw_token;
  lease_expires_at := next_expiry;
  attempt := current_job.attempt;
  revision := current_job.revision;
  return next;
end $$;

create or replace function public.mystic_dispatch_scientific_job_outbox(
  p_limit integer default 100
) returns table(event_id text, job_id text, event_type text, payload_hash text, dispatch_attempt integer)
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_event public.lab_scientific_job_outbox_events;
  now_value timestamptz := timezone('utc',now());
begin
  if p_limit not between 1 and 500 then raise exception 'scientific_job_dispatch_limit_invalid'; end if;
  for current_event in
    select event.* from public.lab_scientific_job_outbox_events event
      join public.lab_scientific_jobs job on job.job_id=event.job_id
      where event.status in ('PENDING','FAILED') and event.available_at <= now_value and job.status='READY'
      order by event.available_at,event.event_id for update of event skip locked limit p_limit
  loop
    update public.lab_scientific_job_outbox_events set status='DISPATCHED',attempt=attempt+1,
      dispatched_at=now_value,safe_error='',revision=revision+1,updated_at=now_value
      where event_id=current_event.event_id returning * into current_event;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
      select 'job_event_' || replace(gen_random_uuid()::text, '-', ''),job.job_id,'OUTBOX_DISPATCHED',job.status,
        job.revision,'Durable scientific job dispatch intent published.',jsonb_build_object('outbox_event_id',current_event.event_id)
      from public.lab_scientific_jobs job where job.job_id=current_event.job_id;
    event_id := current_event.event_id;
    job_id := current_event.job_id;
    event_type := current_event.event_type;
    payload_hash := current_event.payload_hash;
    dispatch_attempt := current_event.attempt;
    return next;
  end loop;
end $$;

create or replace function public.mystic_start_scientific_job(
  p_job_id text,
  p_worker_id text,
  p_lease_token text
) returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
begin
  if char_length(p_worker_id) not between 1 and 160 or char_length(p_lease_token) not between 1 and 512 then
    raise exception 'scientific_job_lease_input_invalid';
  end if;
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status <> 'LEASED' or current_job.lease_owner <> p_worker_id
    or current_job.lease_token_hash <> public.mystic_scientific_job_token_hash(p_lease_token)
    or current_job.lease_expires_at <= now_value then
    raise exception 'scientific_job_stale_lease';
  end if;
  if current_job.cancellation_requested then
    update public.lab_scientific_jobs set status='CANCELLED',lease_owner='',lease_token_hash='',lease_acquired_at=null,
      lease_expires_at=null,finished_at=now_value,revision=revision+1,updated_at=now_value where job_id=p_job_id
      returning * into current_job;
    update public.lab_scientific_job_leases set released_at=now_value,release_reason='cancelled'
      where job_id=p_job_id and released_at is null;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_CANCELLED','CANCELLED',current_job.revision,
        'Leased job cancellation accepted before execution.');
    return current_job;
  end if;
  update public.lab_scientific_jobs set status='RUNNING',started_at=now_value,revision=revision+1,updated_at=now_value
    where job_id=p_job_id returning * into current_job;
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_STARTED','RUNNING',current_job.revision,
      'Scientific engine execution started.');
  return current_job;
end $$;

create or replace function public.mystic_heartbeat_scientific_job_lease(
  p_job_id text,
  p_worker_id text,
  p_lease_token text,
  p_lease_seconds integer default 60
) returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
  next_expiry timestamptz;
  token_hash text;
begin
  if char_length(p_worker_id) not between 1 and 160 or char_length(p_lease_token) not between 1 and 512
    or p_lease_seconds not between 10 and 300 then raise exception 'scientific_job_lease_input_invalid'; end if;
  token_hash := public.mystic_scientific_job_token_hash(p_lease_token);
  next_expiry := now_value + make_interval(secs => p_lease_seconds);
  update public.lab_scientific_jobs set lease_expires_at=next_expiry,revision=revision+1,updated_at=now_value
    where job_id=p_job_id and status in ('LEASED','RUNNING') and not cancellation_requested
      and lease_owner=p_worker_id and lease_token_hash=token_hash and lease_expires_at > now_value
    returning * into current_job;
  if not found then raise exception 'scientific_job_stale_lease'; end if;
  update public.lab_scientific_job_leases set expires_at=next_expiry,heartbeat_count=heartbeat_count+1
    where job_id=p_job_id and lease_owner=p_worker_id and token_hash=token_hash and released_at is null;
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'LEASE_HEARTBEAT',current_job.status,current_job.revision,
      'Scientific job lease renewed.',jsonb_build_object('lease_owner',p_worker_id));
  return current_job;
end $$;

create or replace function public.mystic_complete_scientific_job(
  p_job_id text,
  p_worker_id text,
  p_lease_token text,
  p_engine_name text,
  p_engine_version text,
  p_result jsonb,
  p_result_hash text,
  p_result_schema_version text default '2C.2A'
) returns jsonb
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
  token_hash text;
begin
  if char_length(p_worker_id) not between 1 and 160 or char_length(p_lease_token) not between 1 and 512
    or p_engine_name !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
    or p_engine_version !~ '^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$'
    or p_result_hash !~ '^[0-9a-f]{64}$' or jsonb_typeof(p_result) <> 'object'
    or not (p_result ?& array['job_id','engine_name','engine_version','result_payload','result_hash','runner_version','schema_version','created_at'])
    or p_result - array['job_id','engine_name','engine_version','result_payload','result_hash','runner_version','schema_version','created_at'] <> '{}'::jsonb
    or jsonb_typeof(p_result->'job_id') <> 'string'
    or jsonb_typeof(p_result->'engine_name') <> 'string'
    or jsonb_typeof(p_result->'engine_version') <> 'string'
    or jsonb_typeof(p_result->'result_payload') <> 'object'
    or jsonb_typeof(p_result->'result_hash') <> 'string'
    or jsonb_typeof(p_result->'runner_version') <> 'string'
    or jsonb_typeof(p_result->'schema_version') <> 'string'
    or jsonb_typeof(p_result->'created_at') <> 'string'
    or octet_length((p_result->'result_payload')::text) > 262144
    or p_result->>'job_id' <> p_job_id
    or p_result->>'engine_name' <> p_engine_name
    or p_result->>'engine_version' <> p_engine_version
    or p_result->>'result_hash' <> p_result_hash
    or char_length(coalesce(p_result->>'runner_version','')) > 160
    or p_result->>'schema_version' <> '2C.2A'
    or p_result_schema_version <> '2C.2A' then
    raise exception 'scientific_job_result_invalid';
  end if;
  -- ScientificJobResult.result_hash is deliberately the canonical hash of its
  -- structured result_payload, never of the surrounding transport envelope.
  if p_result_hash <> public.mystic_scientific_job_payload_hash(p_result->'result_payload') then
    raise exception 'scientific_job_result_hash_mismatch';
  end if;
  -- Cast only after the JSON shape has been checked so malformed provenance
  -- fails closed instead of being silently retained as an untyped string.
  perform (p_result->>'created_at')::timestamptz;
  token_hash := public.mystic_scientific_job_token_hash(p_lease_token);
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status = 'SUCCEEDED' then
    if current_job.completed_lease_owner <> p_worker_id or current_job.completed_lease_token_hash <> token_hash then
      raise exception 'scientific_job_stale_lease';
    end if;
    if current_job.result_hash = p_result_hash then
      update public.lab_scientific_jobs set duplicate_completion_count=duplicate_completion_count+1,
        result_replay_count=result_replay_count+1,revision=revision+1,updated_at=now_value where job_id=p_job_id
        returning * into current_job;
      insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
        values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RESULT_REPLAY_IGNORED','SUCCEEDED',current_job.revision,
          'Duplicate scientific job completion replay ignored.');
      return jsonb_build_object('outcome','REPLAY_IGNORED','job',to_jsonb(current_job));
    end if;
    update public.lab_scientific_jobs set conflicting_result_count=conflicting_result_count+1,
      duplicate_completion_rejected_count=duplicate_completion_rejected_count+1,revision=revision+1,updated_at=now_value where job_id=p_job_id
      returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RESULT_CONFLICT_REJECTED','SUCCEEDED',current_job.revision,
        'Conflicting duplicate result rejected.');
    return jsonb_build_object('outcome','CONFLICT_REJECTED','job',to_jsonb(current_job));
  end if;
  if current_job.status <> 'RUNNING' or current_job.lease_owner <> p_worker_id
    or current_job.lease_token_hash <> token_hash or current_job.lease_expires_at <= now_value then
    raise exception 'scientific_job_stale_lease';
  end if;
  if current_job.cancellation_requested then
    update public.lab_scientific_jobs set status='CANCELLED',lease_owner='',lease_token_hash='',lease_acquired_at=null,
      lease_expires_at=null,finished_at=now_value,revision=revision+1,updated_at=now_value where job_id=p_job_id
      returning * into current_job;
    update public.lab_scientific_job_leases set released_at=now_value,release_reason='cancelled'
      where job_id=p_job_id and released_at is null;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RESULT_REJECTED_AFTER_CANCEL','CANCELLED',current_job.revision,
        'Result rejected because cancellation was requested.');
    return jsonb_build_object('outcome','CANCELLED','job',to_jsonb(current_job));
  end if;
  if current_job.engine_name <> p_engine_name or current_job.engine_version <> p_engine_version then
    raise exception 'scientific_job_engine_provenance_conflict';
  end if;
  update public.lab_scientific_jobs set status='SUCCEEDED',result=p_result,result_hash=p_result_hash,
    result_schema_version=p_result_schema_version,finished_at=now_value,completed_lease_owner=p_worker_id,
    completed_lease_token_hash=token_hash,lease_owner='',lease_token_hash='',lease_acquired_at=null,lease_expires_at=null,
    attachment_status='PENDING',attachment_key='scientific-job:' || p_job_id || ':' || p_result_hash,
    revision=revision+1,updated_at=now_value where job_id=p_job_id returning * into current_job;
  update public.lab_scientific_job_leases set released_at=now_value,release_reason='completed'
    where job_id=p_job_id and released_at is null;
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_SUCCEEDED','SUCCEEDED',current_job.revision,
      'Scientific engine result persisted pending campaign attachment.',jsonb_build_object('result_hash',p_result_hash));
  return jsonb_build_object('outcome','ACCEPTED','job',to_jsonb(current_job));
end $$;

create or replace function public.mystic_fail_scientific_job(
  p_job_id text,
  p_worker_id text,
  p_lease_token text,
  p_failure_class text,
  p_safe_error text,
  p_retryable boolean
) returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
  token_hash text;
begin
  if char_length(p_worker_id) not between 1 and 160 or char_length(p_lease_token) not between 1 and 512
    or p_failure_class not in ('VALIDATION','ENGINE_TRANSIENT','ENGINE_PERMANENT','LEASE_EXPIRED','DISPATCH','CAMPAIGN_STALE','RESULT_CONFLICT','CANCELLED','INTERNAL')
    or char_length(p_safe_error) not between 1 and 1000 then
    raise exception 'scientific_job_failure_invalid';
  end if;
  token_hash := public.mystic_scientific_job_token_hash(p_lease_token);
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status = 'FAILED' and current_job.completed_lease_owner=p_worker_id
    and current_job.completed_lease_token_hash=token_hash then
    if current_job.failure_class=p_failure_class and current_job.error=p_safe_error then return current_job; end if;
    raise exception 'scientific_job_failure_conflict';
  end if;
  if current_job.status <> 'RUNNING' or current_job.lease_owner <> p_worker_id
    or current_job.lease_token_hash <> token_hash or current_job.lease_expires_at <= now_value then
    raise exception 'scientific_job_stale_lease';
  end if;
  if current_job.cancellation_requested or p_failure_class='CANCELLED' then
    update public.lab_scientific_jobs set status='CANCELLED',lease_owner='',lease_token_hash='',lease_acquired_at=null,
      lease_expires_at=null,finished_at=now_value,revision=revision+1,updated_at=now_value where job_id=p_job_id
      returning * into current_job;
    update public.lab_scientific_job_leases set released_at=now_value,release_reason='cancelled'
      where job_id=p_job_id and released_at is null;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_CANCELLED','CANCELLED',current_job.revision,
        'Running job stopped cooperatively after cancellation.');
    return current_job;
  end if;
  update public.lab_scientific_jobs set status='FAILED',failure_class=p_failure_class,error=p_safe_error,
    failure=jsonb_build_object('failure_id','job_failure_' || replace(gen_random_uuid()::text, '-', ''),'job_id',p_job_id,'failure_class',p_failure_class,'safe_error',p_safe_error,
      'retryable',p_retryable,'schema_version','2C.2A','created_at',now_value),finished_at=now_value,
    completed_lease_owner=p_worker_id,completed_lease_token_hash=token_hash,lease_owner='',lease_token_hash='',
    lease_acquired_at=null,lease_expires_at=null,revision=revision+1,updated_at=now_value where job_id=p_job_id
    returning * into current_job;
  update public.lab_scientific_job_leases set released_at=now_value,release_reason='failed'
    where job_id=p_job_id and released_at is null;
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_FAILED','FAILED',current_job.revision,
      'Scientific engine failure persisted for deterministic retry evaluation.',
      jsonb_build_object('failure_class',p_failure_class,'retryable',p_retryable));
  return current_job;
end $$;

create or replace function public.mystic_retry_scientific_job(
  p_job_id text,
  p_retry_base_seconds integer default 5,
  p_retry_max_seconds integer default 3600
) returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
  delay_seconds integer;
begin
  if p_retry_base_seconds not between 1 and 3600 or p_retry_max_seconds not between p_retry_base_seconds and 86400 then
    raise exception 'scientific_job_retry_policy_invalid';
  end if;
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status='RETRY_WAIT' then return current_job; end if;
  if current_job.status <> 'FAILED' then raise exception 'scientific_job_transition_invalid'; end if;
  if coalesce((current_job.failure->>'retryable')::boolean,false) and current_job.attempt < current_job.max_attempts then
    delay_seconds := least(p_retry_max_seconds, p_retry_base_seconds * (2 ^ greatest(0,current_job.attempt-1))::integer);
    update public.lab_scientific_jobs set status='RETRY_WAIT',ready_at=now_value + make_interval(secs => delay_seconds),
      revision=revision+1,updated_at=now_value where job_id=p_job_id returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RETRY_SCHEDULED','RETRY_WAIT',current_job.revision,
        'Retryable scientific job failure entered deterministic retry wait.',jsonb_build_object('ready_at',current_job.ready_at));
  else
    update public.lab_scientific_jobs set status='DEAD_LETTER',revision=revision+1,updated_at=now_value
      where job_id=p_job_id returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_DEAD_LETTERED','DEAD_LETTER',current_job.revision,
        'Scientific job cannot be retried safely.');
  end if;
  return current_job;
end $$;

create or replace function public.mystic_cancel_scientific_job(p_job_id text)
returns public.lab_scientific_jobs
language plpgsql security definer set search_path = public, pg_temp as $$
declare current_job public.lab_scientific_jobs; now_value timestamptz := timezone('utc',now());
begin
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status='CANCELLED' then return current_job; end if;
  if current_job.status in ('SUCCEEDED','DEAD_LETTER') then raise exception 'scientific_job_transition_invalid'; end if;
  if current_job.status in ('LEASED','RUNNING') then
    update public.lab_scientific_jobs set cancellation_requested=true,revision=revision+1,updated_at=now_value
      where job_id=p_job_id returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'CANCELLATION_REQUESTED',current_job.status,current_job.revision,
        'Worker must stop cooperatively before a result can attach.');
    return current_job;
  end if;
  update public.lab_scientific_jobs set status='CANCELLED',lease_owner='',lease_token_hash='',lease_acquired_at=null,
    lease_expires_at=null,finished_at=now_value,revision=revision+1,updated_at=now_value where job_id=p_job_id
    returning * into current_job;
  update public.lab_scientific_job_outbox_events set status='ACKNOWLEDGED',acknowledged_at=now_value,
    revision=revision+1,updated_at=now_value where job_id=p_job_id and status <> 'ACKNOWLEDGED';
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'JOB_CANCELLED','CANCELLED',current_job.revision,
      'Scientific job cancellation accepted.');
  return current_job;
end $$;

create or replace function public.mystic_attach_scientific_job_result(
  p_job_id text,
  p_expected_campaign_revision bigint
) returns jsonb
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  current_campaign public.lab_research_campaigns;
  existing_attachment public.lab_scientific_job_attachments;
  artifact_id text;
  next_jobs jsonb;
  next_campaign_revision bigint;
  rejection text := '';
  attachment_exists boolean := false;
  campaign_exists boolean := false;
begin
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status <> 'SUCCEEDED' or current_job.result_hash = '' then
    raise exception 'scientific_job_attachment_invalid_state';
  end if;
  select * into existing_attachment from public.lab_scientific_job_attachments where job_id=p_job_id for update;
  attachment_exists := found;
  select * into current_campaign from public.lab_research_campaigns where campaign_id=current_job.campaign_id for update;
  campaign_exists := found;
  if attachment_exists then
    if existing_attachment.result_hash=current_job.result_hash and existing_attachment.attachment_key=current_job.attachment_key then
      if not campaign_exists then
        rejection := 'Campaign was not found.';
      elsif not exists (
        select 1 from jsonb_array_elements(coalesce(current_campaign.scientific_job_attachments,'[]'::jsonb)) as existing(value)
        where existing.value->>'job_id'=p_job_id and existing.value->>'result_hash'=current_job.result_hash
          and existing.value->>'attachment_key'=current_job.attachment_key
      ) then
        rejection := 'Scientific job attachment was superseded by campaign rollback.';
      elsif current_job.attachment_status <> 'ATTACHED' then
        update public.lab_scientific_jobs set attachment_status='ATTACHED',attachment_error='',revision=revision+1,
          updated_at=timezone('utc',now()) where job_id=p_job_id returning * into current_job;
      end if;
      if rejection = '' then
        return jsonb_build_object('outcome','REPLAY_IGNORED','attachment',to_jsonb(existing_attachment));
      end if;
    else
      rejection := 'Conflicting scientific job result attachment was rejected.';
    end if;
  elsif current_job.attachment_campaign_revision <> p_expected_campaign_revision then
    rejection := 'Scientific job attachment revision does not match its campaign intent.';
  else
    if not campaign_exists then rejection := 'Campaign was not found.';
    elsif current_campaign.status <> 'ACTIVE' then rejection := 'Campaign is not active.';
    elsif current_campaign.revision <> p_expected_campaign_revision then rejection := 'Scientific job result is stale for the campaign revision.';
    elsif not exists (
      select 1 from jsonb_array_elements(coalesce(current_campaign.scientific_jobs,'[]'::jsonb)) as ref(value)
      where ref.value->>'job_id'=p_job_id
        and coalesce((ref.value->>'attachment_campaign_revision')::bigint,-1)=p_expected_campaign_revision
    ) then rejection := 'Scientific job is not referenced by the current campaign revision.';
    end if;
  end if;
  if rejection <> '' then
    update public.lab_scientific_jobs set attachment_status='REJECTED',attachment_error=rejection,
      revision=revision+1,updated_at=timezone('utc',now()) where job_id=p_job_id returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RESULT_ATTACHMENT_REJECTED','SUCCEEDED',current_job.revision,rejection);
    return jsonb_build_object('outcome','REJECTED','job',to_jsonb(current_job));
  end if;
  artifact_id := 'artifact_' || replace(gen_random_uuid()::text, '-', '');
  select coalesce(jsonb_agg(case when value->>'job_id'=p_job_id
    then jsonb_set(value,'{status}','"SUCCEEDED"'::jsonb,true) else value end order by ordinality),'[]'::jsonb)
    into next_jobs from jsonb_array_elements(current_campaign.scientific_jobs) with ordinality as ref(value, ordinality);
  next_campaign_revision := current_campaign.revision + 1;
  insert into public.lab_scientific_job_attachments(
    job_id,campaign_id,campaign_revision,attachment_key,result_hash,artifact_id
  ) values (
    p_job_id,current_job.campaign_id,next_campaign_revision,current_job.attachment_key,current_job.result_hash,artifact_id
  ) returning * into existing_attachment;
  update public.lab_research_campaigns set
    scientific_jobs=next_jobs,
    scientific_job_attachments=coalesce(scientific_job_attachments,'[]'::jsonb) || jsonb_build_array(jsonb_build_object(
      'job_id',p_job_id,'attachment_key',current_job.attachment_key,'result_hash',current_job.result_hash,
      'artifact_id',artifact_id,'attached_campaign_revision',next_campaign_revision,'status','ATTACHED')),
    artifacts=coalesce(artifacts,'[]'::jsonb) || jsonb_build_array(jsonb_build_object(
      'artifact_id',artifact_id,'artifact_type','scientific_job_result','name','Scientific job ' || p_job_id || ' result',
      'uri','mystic://scientific-jobs/' || p_job_id || '/result','content_hash',current_job.result_hash,'media_type','application/json')),
    statistics=jsonb_set(statistics,'{scientific_job_attachment_count}',
      to_jsonb(coalesce((statistics->>'scientific_job_attachment_count')::integer,0)+1),true),
    revision=next_campaign_revision,updated_at=timezone('utc',now())
    where campaign_id=current_job.campaign_id;
  insert into public.lab_campaign_timeline(event_id,campaign_id,event_type,phase,status,summary,revision,metadata)
    values ('event_' || replace(gen_random_uuid()::text, '-', ''),current_job.campaign_id,'SCIENTIFIC_JOB_RESULT_ATTACHED',
      current_campaign.phase,current_campaign.status,'Scientific job result attached exactly once to campaign state.',
      next_campaign_revision,jsonb_build_object('job_id',p_job_id,'result_hash',current_job.result_hash,'artifact_id',artifact_id));
  update public.lab_scientific_jobs set attachment_status='ATTACHED',attachment_error='',revision=revision+1,
    updated_at=timezone('utc',now()) where job_id=p_job_id returning * into current_job;
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'RESULT_ATTACHED','SUCCEEDED',current_job.revision,
      'Scientific job result attached exactly once to campaign state.',jsonb_build_object('artifact_id',artifact_id));
  return jsonb_build_object('outcome','ATTACHED','attachment',to_jsonb(existing_attachment));
end $$;

create or replace function public.mystic_attach_scientific_job_failure(
  p_job_id text,
  p_expected_campaign_revision bigint
) returns jsonb
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  current_campaign public.lab_research_campaigns;
  existing_failure jsonb;
  failure_payload jsonb;
  next_jobs jsonb;
  next_campaign_revision bigint;
  rejection text := '';
  campaign_exists boolean := false;
  now_value timestamptz := timezone('utc',now());
begin
  select * into current_job from public.lab_scientific_jobs where job_id=p_job_id for update;
  if not found then raise exception 'scientific_job_not_found'; end if;
  if current_job.status <> 'DEAD_LETTER' or current_job.failure is null then
    raise exception 'scientific_job_failure_attachment_invalid_state';
  end if;
  select * into current_campaign from public.lab_research_campaigns where campaign_id=current_job.campaign_id for update;
  campaign_exists := found;
  if campaign_exists then
    select value into existing_failure
      from jsonb_array_elements(coalesce(current_campaign.failures,'[]'::jsonb)) as archived(value)
      where archived.value->>'source_id'=p_job_id limit 1;
  end if;
  if existing_failure is not null then
    if existing_failure->>'failure_type'=current_job.failure_class and existing_failure->>'summary'=current_job.error then
      update public.lab_scientific_jobs set failure_attachment_state='ATTACHED',failure_attachment_error='',revision=revision+1,
        updated_at=timezone('utc',now()) where job_id=p_job_id and failure_attachment_state <> 'ATTACHED'
        returning * into current_job;
      return jsonb_build_object('outcome','REPLAY_IGNORED','failure',existing_failure);
    end if;
    rejection := 'Conflicting scientific job failure attachment was rejected.';
  elsif not campaign_exists then
    rejection := 'Campaign was not found.';
  elsif current_job.attachment_campaign_revision <> p_expected_campaign_revision then
    rejection := 'Scientific job failure revision does not match its campaign intent.';
  elsif current_campaign.status <> 'ACTIVE' then
    rejection := 'Campaign is not active.';
  elsif current_campaign.revision <> p_expected_campaign_revision then
    rejection := 'Scientific job failure is stale for the campaign revision.';
  elsif not exists (
    select 1 from jsonb_array_elements(coalesce(current_campaign.scientific_jobs,'[]'::jsonb)) as ref(value)
    where ref.value->>'job_id'=p_job_id
      and coalesce((ref.value->>'attachment_campaign_revision')::bigint,-1)=p_expected_campaign_revision
  ) then
    rejection := 'Scientific job is not referenced by the current campaign revision.';
  end if;
  if rejection <> '' then
    update public.lab_scientific_jobs set failure_attachment_state='REJECTED',failure_attachment_error=rejection,
      revision=revision+1,updated_at=timezone('utc',now()) where job_id=p_job_id returning * into current_job;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
      values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'FAILURE_ATTACHMENT_REJECTED',
        'DEAD_LETTER',current_job.revision,rejection);
    return jsonb_build_object('outcome','REJECTED','job',to_jsonb(current_job));
  end if;
  failure_payload := jsonb_build_object(
    'failure_id',coalesce(current_job.failure->>'failure_id','job_failure_' || replace(gen_random_uuid()::text, '-', '')),
    'campaign_id',current_job.campaign_id,'failure_type',current_job.failure_class,'summary',current_job.error,
    'source_id',p_job_id,'retryable',coalesce((current_job.failure->>'retryable')::boolean,false),'archived',true,
    'created_at',coalesce(current_job.failure->>'created_at',now_value::text)
  );
  select coalesce(jsonb_agg(case when value->>'job_id'=p_job_id
    then jsonb_set(value,'{status}','"FAILED"'::jsonb,true) else value end order by ordinality),'[]'::jsonb)
    into next_jobs from jsonb_array_elements(current_campaign.scientific_jobs) with ordinality as ref(value, ordinality);
  next_campaign_revision := current_campaign.revision + 1;
  update public.lab_research_campaigns set
    scientific_jobs=next_jobs,
    failures=coalesce(failures,'[]'::jsonb) || jsonb_build_array(failure_payload),
    statistics=jsonb_set(statistics,'{failure_count}',to_jsonb(coalesce((statistics->>'failure_count')::integer,0)+1),true),
    revision=next_campaign_revision,updated_at=timezone('utc',now())
    where campaign_id=current_job.campaign_id;
  update public.lab_scientific_jobs set failure_attachment_state='ATTACHED',failure_attachment_error='',revision=revision+1,
    updated_at=timezone('utc',now()) where job_id=p_job_id returning * into current_job;
  insert into public.lab_campaign_timeline(event_id,campaign_id,event_type,phase,status,summary,revision,metadata)
    values ('event_' || replace(gen_random_uuid()::text, '-', ''),current_job.campaign_id,'SCIENTIFIC_JOB_FAILURE_ARCHIVED',
      current_campaign.phase,current_campaign.status,'Terminal scientific job failure archived through the campaign runtime.',
      next_campaign_revision,jsonb_build_object('job_id',p_job_id,'failure_class',current_job.failure_class));
  insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary)
    values ('job_event_' || replace(gen_random_uuid()::text, '-', ''),p_job_id,'FAILURE_ATTACHED','DEAD_LETTER',
      current_job.revision,'Terminal scientific job failure archived in campaign state.');
  return jsonb_build_object('outcome','ATTACHED','failure',failure_payload);
end $$;

create or replace function public.mystic_reconcile_scientific_jobs(
  p_limit integer default 500,
  p_retry_base_seconds integer default 5,
  p_retry_max_seconds integer default 3600,
  p_outbox_stale_seconds integer default 60
) returns jsonb
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  current_job public.lab_scientific_jobs;
  now_value timestamptz := timezone('utc',now());
  delay_seconds integer;
  expired_count integer := 0;
  retry_scheduled_count integer := 0;
  retry_released_count integer := 0;
  terminal_outbox_count integer := 0;
  stale_outbox_count integer := 0;
  result_attachment_completed_count integer := 0;
  result_attachment_rejected_count integer := 0;
  failure_attachment_completed_count integer := 0;
  attachment_outcome jsonb;
begin
  if p_limit not between 1 and 500 or p_retry_base_seconds not between 1 and 3600
    or p_retry_max_seconds not between p_retry_base_seconds and 86400 or p_outbox_stale_seconds not between 10 and 86400 then
    raise exception 'scientific_job_reconciliation_input_invalid';
  end if;
  for current_job in
    select * from public.lab_scientific_jobs
    where (status in ('LEASED','RUNNING') and lease_expires_at <= now_value)
       or status in ('FAILED','RETRY_WAIT','SUCCEEDED','CANCELLED','DEAD_LETTER')
    order by updated_at, job_id for update skip locked limit p_limit
  loop
    if current_job.status in ('LEASED','RUNNING') and current_job.lease_expires_at <= now_value then
      if current_job.cancellation_requested then
        update public.lab_scientific_jobs set status='CANCELLED',lease_owner='',lease_token_hash='',lease_acquired_at=null,
          lease_expires_at=null,finished_at=now_value,reconciliation_count=reconciliation_count+1,revision=revision+1,updated_at=now_value
          where job_id=current_job.job_id;
      elsif current_job.attempt >= current_job.max_attempts then
        update public.lab_scientific_jobs set status='DEAD_LETTER',lease_owner='',lease_token_hash='',lease_acquired_at=null,
          lease_expires_at=null,finished_at=now_value,failure_class='LEASE_EXPIRED',
          error='Scientific job lease expired before the worker completed the operation.',
          failure=jsonb_build_object('failure_id','job_failure_' || replace(gen_random_uuid()::text, '-', ''),'job_id',current_job.job_id,'failure_class','LEASE_EXPIRED','safe_error',
            'Scientific job lease expired before the worker completed the operation.','retryable',false,'schema_version','2C.2A','created_at',now_value),
          reconciliation_count=reconciliation_count+1,revision=revision+1,updated_at=now_value where job_id=current_job.job_id;
      else
        delay_seconds := least(p_retry_max_seconds, p_retry_base_seconds * (2 ^ greatest(0,current_job.attempt-1))::integer);
        update public.lab_scientific_jobs set status='RETRY_WAIT',ready_at=now_value + make_interval(secs => delay_seconds),
          lease_owner='',lease_token_hash='',lease_acquired_at=null,lease_expires_at=null,finished_at=now_value,
          failure_class='LEASE_EXPIRED',error='Scientific job lease expired before the worker completed the operation.',
          failure=jsonb_build_object('failure_id','job_failure_' || replace(gen_random_uuid()::text, '-', ''),'job_id',current_job.job_id,'failure_class','LEASE_EXPIRED','safe_error',
            'Scientific job lease expired before the worker completed the operation.','retryable',true,'schema_version','2C.2A','created_at',now_value),
          reconciliation_count=reconciliation_count+1,revision=revision+1,updated_at=now_value where job_id=current_job.job_id;
      end if;
      update public.lab_scientific_job_leases set released_at=now_value,release_reason='expired'
        where job_id=current_job.job_id and released_at is null;
      expired_count := expired_count + 1;
    elsif current_job.status='FAILED' then
      perform public.mystic_retry_scientific_job(current_job.job_id,p_retry_base_seconds,p_retry_max_seconds);
      retry_scheduled_count := retry_scheduled_count + 1;
    elsif current_job.status='RETRY_WAIT' and current_job.ready_at <= now_value then
      update public.lab_scientific_jobs set status='READY',revision=revision+1,updated_at=now_value where job_id=current_job.job_id;
      retry_released_count := retry_released_count + 1;
    end if;
    select * into current_job from public.lab_scientific_jobs where job_id=current_job.job_id;
    if current_job.status='SUCCEEDED' and current_job.attachment_status='PENDING' then
      select public.mystic_attach_scientific_job_result(current_job.job_id,current_job.attachment_campaign_revision)
        into attachment_outcome;
      if attachment_outcome->>'outcome'='ATTACHED' then
        result_attachment_completed_count := result_attachment_completed_count + 1;
      elsif attachment_outcome->>'outcome'='REJECTED' then
        result_attachment_rejected_count := result_attachment_rejected_count + 1;
      end if;
      select * into current_job from public.lab_scientific_jobs where job_id=current_job.job_id;
    end if;
    if current_job.status='DEAD_LETTER' and current_job.failure_attachment_state='' then
      select public.mystic_attach_scientific_job_failure(current_job.job_id,current_job.attachment_campaign_revision)
        into attachment_outcome;
      if attachment_outcome->>'outcome'='ATTACHED' then
        failure_attachment_completed_count := failure_attachment_completed_count + 1;
      end if;
      select * into current_job from public.lab_scientific_jobs where job_id=current_job.job_id;
    end if;
    if current_job.status in ('SUCCEEDED','CANCELLED','DEAD_LETTER') then
      update public.lab_scientific_job_outbox_events set status='ACKNOWLEDGED',acknowledged_at=now_value,
        revision=revision+1,updated_at=now_value where job_id=current_job.job_id and status <> 'ACKNOWLEDGED';
      if found then terminal_outbox_count := terminal_outbox_count + 1; end if;
    end if;
  end loop;
  update public.lab_scientific_job_outbox_events set status='PENDING',available_at=now_value,safe_error='',revision=revision+1,
    updated_at=now_value where status='DISPATCHED' and dispatched_at <= now_value - make_interval(secs => p_outbox_stale_seconds);
  get diagnostics stale_outbox_count = row_count;
  return jsonb_build_object(
    'expired_leases_recovered',expired_count,'retry_scheduled',retry_scheduled_count,
    'retry_released',retry_released_count,'terminal_outbox_acknowledged',terminal_outbox_count,
    'stale_outbox_requeued',stale_outbox_count,
    'result_attachments_completed',result_attachment_completed_count,
    'result_attachments_rejected',result_attachment_rejected_count,
    'failure_attachments_completed',failure_attachment_completed_count,
    'result_attachment_candidates',(select count(*) from public.lab_scientific_jobs where status='SUCCEEDED' and attachment_status='PENDING')
  );
end $$;

revoke all on function public.mystic_scientific_job_token_hash(text) from public, anon, authenticated;
revoke all on function public.mystic_scientific_job_canonical_json(jsonb) from public, anon, authenticated;
revoke all on function public.mystic_scientific_job_payload_hash(jsonb) from public, anon, authenticated;
revoke all on function public.mystic_create_scientific_job(text,text,bigint,text,text,text,jsonb,text,integer,text,text,text,text) from public, anon, authenticated;
revoke all on function public.mystic_acquire_scientific_job_lease(text,integer) from public, anon, authenticated;
revoke all on function public.mystic_dispatch_scientific_job_outbox(integer) from public, anon, authenticated;
revoke all on function public.mystic_start_scientific_job(text,text,text) from public, anon, authenticated;
revoke all on function public.mystic_heartbeat_scientific_job_lease(text,text,text,integer) from public, anon, authenticated;
revoke all on function public.mystic_complete_scientific_job(text,text,text,text,text,jsonb,text,text) from public, anon, authenticated;
revoke all on function public.mystic_fail_scientific_job(text,text,text,text,text,boolean) from public, anon, authenticated;
revoke all on function public.mystic_retry_scientific_job(text,integer,integer) from public, anon, authenticated;
revoke all on function public.mystic_cancel_scientific_job(text) from public, anon, authenticated;
revoke all on function public.mystic_attach_scientific_job_result(text,bigint) from public, anon, authenticated;
revoke all on function public.mystic_attach_scientific_job_failure(text,bigint) from public, anon, authenticated;
revoke all on function public.mystic_reconcile_scientific_jobs(integer,integer,integer,integer) from public, anon, authenticated;
grant execute on function public.mystic_create_scientific_job(text,text,bigint,text,text,text,jsonb,text,integer,text,text,text,text) to service_role;
grant execute on function public.mystic_acquire_scientific_job_lease(text,integer) to service_role;
grant execute on function public.mystic_dispatch_scientific_job_outbox(integer) to service_role;
grant execute on function public.mystic_start_scientific_job(text,text,text) to service_role;
grant execute on function public.mystic_heartbeat_scientific_job_lease(text,text,text,integer) to service_role;
grant execute on function public.mystic_complete_scientific_job(text,text,text,text,text,jsonb,text,text) to service_role;
grant execute on function public.mystic_fail_scientific_job(text,text,text,text,text,boolean) to service_role;
grant execute on function public.mystic_retry_scientific_job(text,integer,integer) to service_role;
grant execute on function public.mystic_cancel_scientific_job(text) to service_role;
grant execute on function public.mystic_attach_scientific_job_result(text,bigint) to service_role;
grant execute on function public.mystic_attach_scientific_job_failure(text,bigint) to service_role;
grant execute on function public.mystic_reconcile_scientific_jobs(integer,integer,integer,integer) to service_role;
