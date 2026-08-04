-- Issue #112: additive multi-host runner fleet state. The existing Phase 2A
-- queue fields remain the compatibility contract while fleet_* fields provide
-- the canonical scheduler and audit state for fleet_shadow/fleet_active.

alter table public.lab_engine_runners
  add column if not exists runtime_version text not null default '',
  add column if not exists display_name text not null default '',
  add column if not exists operating_system text not null default '',
  add column if not exists architecture text not null default '',
  add column if not exists supported_engines jsonb not null default '[]'::jsonb,
  add column if not exists max_concurrent_jobs integer not null default 1 check (max_concurrent_jobs between 1 and 32),
  add column if not exists active_jobs integer not null default 0 check (active_jobs >= 0),
  add column if not exists cpu_count integer not null default 0 check (cpu_count >= 0),
  add column if not exists memory_limit_mb integer not null default 0 check (memory_limit_mb >= 0),
  add column if not exists gpu_type text not null default '',
  add column if not exists region text not null default '',
  add column if not exists priority integer not null default 0,
  add column if not exists fleet_state text not null default 'registering' check (fleet_state in ('registering','online','busy','draining','maintenance','stale','offline','quarantined')),
  add column if not exists maintenance_state boolean not null default false,
  add column if not exists quarantined_at timestamptz,
  add column if not exists failure_count bigint not null default 0,
  add column if not exists latest_heartbeat timestamptz,
  add column if not exists registered_at timestamptz not null default timezone('utc', now()),
  add column if not exists metadata_safe jsonb not null default '{}'::jsonb;

update public.lab_engine_runners
set supported_engines = engine_versions,
    latest_heartbeat = coalesce(latest_heartbeat, last_heartbeat),
    fleet_state = case status when 'ready' then 'online' when 'busy' then 'busy' when 'offline' then 'offline' else 'registering' end,
    failure_count = greatest(failure_count, failed_count)
where latest_heartbeat is null or supported_engines = '[]'::jsonb;

create index if not exists lab_engine_runners_fleet_eligible_idx
  on public.lab_engine_runners(fleet_state, maintenance_state, latest_heartbeat desc, priority desc, runner_id);

create table if not exists public.lab_engine_runner_credentials (
  runner_id text primary key references public.lab_engine_runners(runner_id) on delete cascade,
  credential_version integer not null default 1 check (credential_version > 0),
  credential_verifier text not null check (char_length(credential_verifier) = 64),
  revoked_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  metadata_safe jsonb not null default '{}'::jsonb
);

create table if not exists public.lab_engine_job_attempts (
  attempt_id text primary key,
  job_id text not null references public.lab_engine_jobs(job_id) on delete restrict,
  attempt_number integer not null check (attempt_number > 0),
  runner_id text not null default '',
  state text not null check (state in ('claimed','running','lease_renewed','lease_expired','retry_scheduled','completed','failed','cancelled','dead_letter')),
  lease_started_at timestamptz,
  lease_expires_at timestamptz,
  input_hash text not null default '',
  output_hash text not null default '',
  safe_reason text not null default '',
  scheduler_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists lab_engine_job_attempts_job_attempt_state_idx
  on public.lab_engine_job_attempts(job_id, attempt_number, state, runner_id);
create index if not exists lab_engine_job_attempts_runner_idx on public.lab_engine_job_attempts(runner_id, created_at desc);

create table if not exists public.lab_engine_runner_audit_events (
  event_id text primary key,
  event_type text not null check (event_type in (
    'runner_registered','runner_updated','runner_online','runner_busy','runner_draining','runner_maintenance',
    'runner_stale','runner_offline','runner_quarantined','runner_restored','runner_credential_rotated',
    'job_assigned','job_reassigned','job_completed','job_failed','job_cancelled','lease_renewed','lease_expired','retry_scheduled','job_dead_lettered'
  )),
  runner_id text not null default '',
  job_id text not null default '',
  actor_type text not null default 'system' check (actor_type in ('system','runner','control_center')),
  safe_reason text not null default '',
  metadata_safe jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);
create index if not exists lab_engine_runner_audit_events_runner_idx on public.lab_engine_runner_audit_events(runner_id, created_at desc);
create index if not exists lab_engine_runner_audit_events_job_idx on public.lab_engine_runner_audit_events(job_id, created_at desc);

alter table public.lab_engine_jobs
  add column if not exists assigned_runner_id text not null default '',
  add column if not exists lease_owner text not null default '',
  add column if not exists lease_started_at timestamptz,
  add column if not exists last_job_heartbeat timestamptz,
  add column if not exists attempt_number integer not null default 0,
  add column if not exists maximum_attempts integer not null default 3 check (maximum_attempts between 1 and 10),
  add column if not exists retry_after timestamptz,
  add column if not exists terminal_reason text not null default '',
  add column if not exists dead_lettered_at timestamptz,
  add column if not exists fleet_state text not null default 'queued' check (fleet_state in ('queued','claimed','running','cancellation_requested','completed','failed','cancelled','lease_expired','retry_wait','dead_letter')),
  add column if not exists scheduler_metadata jsonb not null default '{}'::jsonb;

update public.lab_engine_jobs
set assigned_runner_id = claimed_by,
    lease_owner = claimed_by,
    lease_started_at = case when status = 'running' then coalesce(heartbeat_at, started_at, created_at) else lease_started_at end,
    last_job_heartbeat = coalesce(heartbeat_at, last_job_heartbeat),
    attempt_number = greatest(attempt_number, attempts),
    maximum_attempts = greatest(maximum_attempts, max_attempts),
    fleet_state = case status
      when 'pending' then 'queued' when 'running' then 'running' when 'completed' then 'completed'
      when 'cancelled' then 'cancelled' when 'failed' then 'failed' when 'timed_out' then 'dead_letter'
      else 'queued' end
where attempt_number = 0 or assigned_runner_id = '';

alter table public.lab_engine_jobs alter column max_attempts set default 3;

create index if not exists lab_engine_jobs_fleet_queue_idx
  on public.lab_engine_jobs(status, fleet_state, retry_after, priority desc, created_at);
create index if not exists lab_engine_jobs_fleet_lease_idx
  on public.lab_engine_jobs(lease_expires_at) where status = 'running';

-- Active-mode transitions append history inside the same transaction that owns
-- the queue state. The Worker never writes active-mode history after a RPC.
create or replace function public.mystic_fleet_append_engine_attempt(p_job_id text, p_attempt_number integer, p_runner_id text, p_state text, p_lease_started_at timestamptz default null, p_lease_expires_at timestamptz default null, p_input_hash text default '', p_output_hash text default '', p_safe_reason text default '', p_scheduler_metadata jsonb default '{}'::jsonb)
returns void language sql security definer set search_path = public as $$
  insert into public.lab_engine_job_attempts(attempt_id,job_id,attempt_number,runner_id,state,lease_started_at,lease_expires_at,input_hash,output_hash,safe_reason,scheduler_metadata)
  values ('attempt-' || gen_random_uuid()::text,p_job_id,greatest(1,p_attempt_number),p_runner_id,p_state,p_lease_started_at,p_lease_expires_at,left(coalesce(p_input_hash,''),256),left(coalesce(p_output_hash,''),256),left(coalesce(p_safe_reason,''),1000),coalesce(p_scheduler_metadata,'{}'::jsonb));
$$;

create or replace function public.mystic_fleet_append_audit_event(p_event_type text, p_runner_id text default '', p_job_id text default '', p_safe_reason text default '', p_metadata_safe jsonb default '{}'::jsonb, p_actor_type text default 'system')
returns void language sql security definer set search_path = public as $$
  insert into public.lab_engine_runner_audit_events(event_id,event_type,runner_id,job_id,actor_type,safe_reason,metadata_safe)
  values ('runner-audit-' || gen_random_uuid()::text,p_event_type,p_runner_id,p_job_id,p_actor_type,left(coalesce(p_safe_reason,''),1000),coalesce(p_metadata_safe,'{}'::jsonb));
$$;

-- The Worker computes the complete deterministic ranking and this RPC repeats
-- the non-bypassable eligibility checks inside the atomic claim transaction.
create or replace function public.mystic_fleet_claim_next_engine_job(p_runner_id text, p_lease_seconds integer default 60)
returns setof public.lab_engine_jobs language plpgsql security definer set search_path = public as $$
declare claimed public.lab_engine_jobs;
begin
  select job.* into claimed
  from public.lab_engine_jobs job
  join public.lab_engine_registry engine on engine.engine_id = job.engine_id
  where job.status = 'pending'
    and job.cancellation_requested = false
    and job.attempts < job.max_attempts
    and (job.retry_after is null or job.retry_after <= timezone('utc', now()))
    and exists (
      select 1 from public.lab_engine_runners runner
      where runner.runner_id = p_runner_id
        and runner.fleet_state in ('online','busy')
        and runner.maintenance_state = false
        and runner.quarantined_at is null
        and coalesce(runner.latest_heartbeat, runner.last_heartbeat) >= timezone('utc', now()) - interval '90 seconds'
        and runner.active_jobs < runner.max_concurrent_jobs
        and runner.resource_classes ? coalesce(engine.manifest->>'expected_resource_class', 'tiny')
        and runner.supported_engines @> jsonb_build_array(jsonb_build_object('engine_id', engine.engine_id, 'version', engine.version))
    )
    and not exists (
      select 1 from public.lab_engine_runners preferred
      where preferred.fleet_state in ('online','busy')
        and preferred.maintenance_state = false
        and preferred.quarantined_at is null
        and coalesce(preferred.latest_heartbeat, preferred.last_heartbeat) >= timezone('utc', now()) - interval '90 seconds'
        and preferred.active_jobs < preferred.max_concurrent_jobs
        and preferred.resource_classes ? coalesce(engine.manifest->>'expected_resource_class', 'tiny')
        and preferred.supported_engines @> jsonb_build_array(jsonb_build_object('engine_id', engine.engine_id, 'version', engine.version))
        and (preferred.priority > (select priority from public.lab_engine_runners where runner_id = p_runner_id)
          or (preferred.priority = (select priority from public.lab_engine_runners where runner_id = p_runner_id)
            and (preferred.active_jobs::numeric / preferred.max_concurrent_jobs) < ((select active_jobs::numeric / max_concurrent_jobs from public.lab_engine_runners where runner_id = p_runner_id)))
          or (preferred.priority = (select priority from public.lab_engine_runners where runner_id = p_runner_id)
            and (preferred.active_jobs::numeric / preferred.max_concurrent_jobs) = ((select active_jobs::numeric / max_concurrent_jobs from public.lab_engine_runners where runner_id = p_runner_id))
            and preferred.runner_id < p_runner_id)
    )
  order by job.priority desc, job.created_at
  for update of job skip locked limit 1;
  if not found then return; end if;

  update public.lab_engine_jobs
  set status = 'running', fleet_state = 'running', claimed_by = p_runner_id, assigned_runner_id = p_runner_id,
      lease_owner = p_runner_id, attempts = attempts + 1, attempt_number = greatest(attempt_number, attempts + 1),
      started_at = coalesce(started_at, timezone('utc', now())), lease_started_at = timezone('utc', now()),
      heartbeat_at = timezone('utc', now()), last_job_heartbeat = timezone('utc', now()),
      lease_expires_at = timezone('utc', now()) + make_interval(secs => greatest(10, least(p_lease_seconds, 300))), retry_after = null
  where job_id = claimed.job_id returning * into claimed;

  update public.lab_engine_runners
  set active_jobs = active_jobs + 1, status = 'busy', fleet_state = 'busy', current_job_id = claimed.job_id,
      latest_heartbeat = timezone('utc', now()), last_heartbeat = timezone('utc', now()), updated_at = timezone('utc', now())
  where runner_id = p_runner_id;
  perform public.mystic_fleet_append_engine_attempt(claimed.job_id,claimed.attempt_number,p_runner_id,'claimed',claimed.lease_started_at,claimed.lease_expires_at,'','','',jsonb_build_object('mode','fleet_active','selected_runner_id',p_runner_id));
  perform public.mystic_fleet_append_audit_event(case when claimed.attempt_number > 1 then 'job_reassigned' else 'job_assigned' end,p_runner_id,claimed.job_id,'',jsonb_build_object('mode','fleet_active'));
  return next claimed;
end $$;

create or replace function public.mystic_fleet_renew_engine_job_lease(p_job_id text, p_runner_id text, p_lease_seconds integer default 60)
returns boolean language plpgsql security definer set search_path = public as $$
declare renewed public.lab_engine_jobs;
begin
  update public.lab_engine_jobs
  set heartbeat_at = timezone('utc', now()), last_job_heartbeat = timezone('utc', now()),
      lease_expires_at = timezone('utc', now()) + make_interval(secs => greatest(10, least(p_lease_seconds, 300)))
  where job_id = p_job_id and status = 'running' and lease_owner = p_runner_id
    and assigned_runner_id = p_runner_id and cancellation_requested = false
    and lease_expires_at >= timezone('utc', now())
  returning * into renewed;
  if not found then return false; end if;
  perform public.mystic_fleet_append_engine_attempt(renewed.job_id,renewed.attempt_number,p_runner_id,'lease_renewed',renewed.lease_started_at,renewed.lease_expires_at);
  perform public.mystic_fleet_append_audit_event('lease_renewed',p_runner_id,renewed.job_id);
  return true;
end $$;

create or replace function public.mystic_fleet_recover_expired_engine_leases()
returns integer language plpgsql security definer set search_path = public as $$
declare recovered integer := 0;
declare expired public.lab_engine_jobs;
declare next_state text;
begin
  for expired in
    select * from public.lab_engine_jobs
    where status = 'running' and lease_expires_at < timezone('utc', now())
    for update skip locked
  loop
    next_state := case when expired.cancellation_requested then 'cancelled' when expired.attempts >= expired.max_attempts then 'dead_letter' else 'retry_wait' end;
    update public.lab_engine_jobs
    set status = case when next_state = 'cancelled' then 'cancelled' when next_state = 'dead_letter' then 'timed_out' else 'pending' end,
        fleet_state = next_state,
        terminal_reason = case when next_state = 'dead_letter' then 'lease_expired_retry_limit' else terminal_reason end,
        dead_lettered_at = case when next_state = 'dead_letter' then timezone('utc', now()) else dead_lettered_at end,
        retry_after = case when next_state = 'retry_wait' then timezone('utc', now()) + make_interval(secs => least(300, 5 * power(2::numeric, greatest(0, expired.attempts - 1))::integer) + floor(random() * 3)::integer) else null end,
        claimed_by = '', lease_owner = '', lease_expires_at = null
    where job_id = expired.job_id;
    update public.lab_engine_runners
    set active_jobs = greatest(0, active_jobs - 1), current_job_id = '',
        fleet_state = case when fleet_state = 'draining' then 'draining' else 'online' end, status = 'ready', updated_at = timezone('utc', now())
    where runner_id = expired.assigned_runner_id and expired.assigned_runner_id <> '';
    perform public.mystic_fleet_append_engine_attempt(expired.job_id,expired.attempt_number,expired.assigned_runner_id,'lease_expired',expired.lease_started_at,expired.lease_expires_at,'','','lease_expired');
    if next_state = 'retry_wait' then
      perform public.mystic_fleet_append_engine_attempt(expired.job_id,expired.attempt_number,expired.assigned_runner_id,'retry_scheduled',null,null,'','','lease_expired_retry');
      perform public.mystic_fleet_append_audit_event('retry_scheduled',expired.assigned_runner_id,expired.job_id,'lease_expired_retry');
    elsif next_state = 'dead_letter' then
      perform public.mystic_fleet_append_engine_attempt(expired.job_id,expired.attempt_number,expired.assigned_runner_id,'dead_letter',null,null,'','','lease_expired_retry_limit');
      perform public.mystic_fleet_append_audit_event('job_dead_lettered',expired.assigned_runner_id,expired.job_id,'lease_expired_retry_limit');
    end if;
    perform public.mystic_fleet_append_audit_event('lease_expired',expired.assigned_runner_id,expired.job_id);
    recovered := recovered + 1;
  end loop;
  return recovered;
end $$;

create or replace function public.mystic_fleet_complete_engine_job(p_job_id text, p_runner_id text, p_run_id text, p_engine_version text, p_result jsonb, p_summary jsonb, p_visualization jsonb, p_reproducibility jsonb, p_input_hash text, p_output_hash text, p_duration_ms bigint, p_warnings jsonb default '[]'::jsonb)
returns boolean language plpgsql security definer set search_path = public as $$
declare completed public.lab_engine_jobs;
begin
  select * into completed from public.lab_engine_jobs
  where job_id=p_job_id and status='running' and assigned_runner_id=p_runner_id and lease_owner=p_runner_id
    and cancellation_requested=false and lease_expires_at >= timezone('utc',now())
  for update;
  if not found then return false; end if;
  insert into public.lab_engine_runs(run_id,job_id,session_id,experiment_id,scene_id,engine_id,engine_version,status,result,summary,visualization,reproducibility,input_hash,output_hash,duration_ms,warnings,completed_at)
    values (p_run_id,completed.job_id,completed.session_id,completed.experiment_id,completed.scene_id,completed.engine_id,p_engine_version,'completed',p_result,p_summary,p_visualization,p_reproducibility,p_input_hash,p_output_hash,p_duration_ms,p_warnings,timezone('utc',now()))
    on conflict (job_id) do nothing;
  update public.lab_engine_jobs set status='completed',fleet_state='completed',completed_at=timezone('utc',now()),lease_expires_at=null,lease_owner=''
    where job_id=completed.job_id;
  update public.lab_engine_runners set active_jobs=greatest(0,active_jobs-1),current_job_id='',fleet_state=case when fleet_state='draining' then 'draining' else 'online' end,status='ready',completed_count=completed_count+1,latest_heartbeat=timezone('utc',now()),last_heartbeat=timezone('utc',now()),updated_at=timezone('utc',now()) where runner_id=p_runner_id;
  perform public.mystic_fleet_append_engine_attempt(completed.job_id,completed.attempt_number,p_runner_id,'completed',completed.lease_started_at,completed.lease_expires_at,p_input_hash,p_output_hash);
  perform public.mystic_fleet_append_audit_event('job_completed',p_runner_id,completed.job_id,'',jsonb_build_object('mode','fleet_active'));
  return true;
end $$;

create or replace function public.mystic_fleet_request_engine_job_cancellation(p_job_id text)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  update public.lab_engine_jobs set cancellation_requested=true,
    status=case when status='pending' then 'cancelled' else status end,
    fleet_state=case when status='pending' then 'cancelled' else 'cancellation_requested' end,
    terminal_reason=case when status='pending' then 'cancelled_before_claim' else terminal_reason end
  where job_id=p_job_id and status in ('pending','running');
  return found;
end $$;

create or replace function public.mystic_fleet_fail_engine_job(p_job_id text, p_runner_id text, p_status text, p_safe_error text, p_retryable boolean default false)
returns boolean language plpgsql security definer set search_path = public as $$
declare retrying boolean;
declare failed public.lab_engine_jobs;
begin
  if p_status not in ('failed','cancelled','timed_out') then raise exception 'invalid final status'; end if;
  select * into failed from public.lab_engine_jobs where job_id=p_job_id and status='running' and assigned_runner_id=p_runner_id and lease_owner=p_runner_id for update;
  if not found then return false; end if;
  retrying := p_retryable and failed.attempts < failed.max_attempts and not failed.cancellation_requested;
  update public.lab_engine_jobs set status=case when retrying then 'pending' else p_status end,
    fleet_state=case when cancellation_requested or p_status='cancelled' then 'cancelled' when retrying then 'retry_wait' when attempts >= max_attempts then 'dead_letter' else 'failed' end,
    retry_after=case when retrying then timezone('utc',now()) + make_interval(secs => least(300, 5 * power(2::numeric, greatest(0, attempts - 1))::integer) + floor(random() * 3)::integer) else null end,
    terminal_reason=case when retrying then '' when attempts >= max_attempts then 'retry_limit_reached' else left(p_safe_error,1000) end,
    dead_lettered_at=case when not retrying and not cancellation_requested and p_status <> 'cancelled' and attempts >= max_attempts then timezone('utc',now()) else dead_lettered_at end,
    safe_error=left(p_safe_error,1000),completed_at=case when retrying then null else timezone('utc',now()) end,lease_expires_at=null,lease_owner='',claimed_by=''
  where job_id=failed.job_id;
  update public.lab_engine_runners set active_jobs=greatest(0,active_jobs-1),current_job_id='',fleet_state=case when fleet_state='draining' then 'draining' else 'online' end,status='ready',failure_count=failure_count+1,failed_count=failed_count+1,latest_heartbeat=timezone('utc',now()),last_heartbeat=timezone('utc',now()),updated_at=timezone('utc',now()) where runner_id=p_runner_id;
  if retrying then
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'failed',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'retry_scheduled',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_audit_event('retry_scheduled',p_runner_id,failed.job_id,p_safe_error);
  elsif failed.cancellation_requested or p_status='cancelled' then
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'cancelled',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_audit_event('job_cancelled',p_runner_id,failed.job_id,p_safe_error);
  elsif failed.attempts >= failed.max_attempts then
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'failed',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'dead_letter',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_audit_event('job_dead_lettered',p_runner_id,failed.job_id,p_safe_error);
  else
    perform public.mystic_fleet_append_engine_attempt(failed.job_id,failed.attempt_number,p_runner_id,'failed',failed.lease_started_at,failed.lease_expires_at,'','',p_safe_error);
    perform public.mystic_fleet_append_audit_event('job_failed',p_runner_id,failed.job_id,p_safe_error);
  end if;
  return true;
end $$;

alter table public.lab_engine_runner_credentials enable row level security;
alter table public.lab_engine_job_attempts enable row level security;
alter table public.lab_engine_runner_audit_events enable row level security;

create or replace function public.mystic_reject_fleet_history_mutation()
returns trigger language plpgsql set search_path = public as $$
begin
  raise exception 'runner fleet history is append-only';
end $$;

create trigger lab_engine_job_attempts_append_only
before update or delete on public.lab_engine_job_attempts
for each row execute function public.mystic_reject_fleet_history_mutation();

create trigger lab_engine_runner_audit_events_append_only
before update or delete on public.lab_engine_runner_audit_events
for each row execute function public.mystic_reject_fleet_history_mutation();

revoke all on public.lab_engine_runner_credentials, public.lab_engine_job_attempts, public.lab_engine_runner_audit_events from anon, authenticated;
grant select, insert, update on public.lab_engine_runner_credentials to service_role;
grant select, insert on public.lab_engine_job_attempts, public.lab_engine_runner_audit_events to service_role;
revoke all on function public.mystic_fleet_append_engine_attempt(text,integer,text,text,timestamptz,timestamptz,text,text,text,jsonb), public.mystic_fleet_append_audit_event(text,text,text,text,jsonb,text), public.mystic_reject_fleet_history_mutation() from public;
revoke all on function public.mystic_fleet_claim_next_engine_job(text,integer), public.mystic_fleet_renew_engine_job_lease(text,text,integer), public.mystic_fleet_recover_expired_engine_leases(), public.mystic_fleet_complete_engine_job(text,text,text,text,jsonb,jsonb,jsonb,jsonb,text,text,bigint,jsonb), public.mystic_fleet_request_engine_job_cancellation(text), public.mystic_fleet_fail_engine_job(text,text,text,text,boolean) from public;
grant execute on function public.mystic_fleet_claim_next_engine_job(text,integer), public.mystic_fleet_renew_engine_job_lease(text,text,integer), public.mystic_fleet_recover_expired_engine_leases(), public.mystic_fleet_complete_engine_job(text,text,text,text,jsonb,jsonb,jsonb,jsonb,text,text,bigint,jsonb), public.mystic_fleet_request_engine_job_cancellation(text), public.mystic_fleet_fail_engine_job(text,text,text,text,boolean) to service_role;
