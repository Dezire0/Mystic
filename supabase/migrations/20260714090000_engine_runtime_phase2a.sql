-- Phase 2A trusted engine runtime. Browser/anon roles receive no direct access.
create table if not exists public.lab_engine_registry (
  engine_id text primary key, display_name text not null, version text not null, domain text not null,
  capabilities jsonb not null default '[]'::jsonb, manifest jsonb not null default '{}'::jsonb,
  enabled boolean not null default true, deprecated boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()), updated_at timestamptz not null default timezone('utc', now())
);
create table if not exists public.lab_engine_jobs (
  job_id text primary key, session_id text not null default '', experiment_id text not null default '', scene_id text not null default '',
  engine_id text not null references public.lab_engine_registry(engine_id), requested_by text not null default '',
  input_payload jsonb not null default '{}'::jsonb, normalized_input jsonb not null default '{}'::jsonb,
  status text not null check (status in ('pending','running','completed','failed','cancelled','timed_out')),
  priority integer not null default 0, claimed_by text not null default '', lease_expires_at timestamptz, heartbeat_at timestamptz,
  cancellation_requested boolean not null default false, attempts integer not null default 0, max_attempts integer not null default 1,
  safe_error text not null default '', metadata_safe jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()), started_at timestamptz, completed_at timestamptz
);
create table if not exists public.lab_engine_runs (
  run_id text primary key, job_id text not null unique references public.lab_engine_jobs(job_id) on delete restrict,
  session_id text not null default '', experiment_id text not null default '', scene_id text not null default '', engine_id text not null,
  engine_version text not null, status text not null check (status in ('completed','failed','cancelled','timed_out')),
  result jsonb not null default '{}'::jsonb, summary jsonb not null default '{}'::jsonb, visualization jsonb not null default '{}'::jsonb,
  reproducibility jsonb not null default '{}'::jsonb, input_hash text not null default '', output_hash text not null default '',
  duration_ms bigint not null default 0, warnings jsonb not null default '[]'::jsonb, safe_error text not null default '',
  created_at timestamptz not null default timezone('utc', now()), completed_at timestamptz, metadata_safe jsonb not null default '{}'::jsonb
);
create table if not exists public.lab_engine_artifacts (
  artifact_id text primary key, run_id text not null references public.lab_engine_runs(run_id) on delete cascade,
  artifact_type text not null, mime_type text not null, storage_key text not null, byte_size bigint not null check (byte_size >= 0),
  checksum text not null, display_name text not null, created_at timestamptz not null default timezone('utc', now()), metadata_safe jsonb not null default '{}'::jsonb
);
create index if not exists lab_engine_jobs_status_priority_idx on public.lab_engine_jobs(status, priority desc, created_at);
create index if not exists lab_engine_jobs_session_idx on public.lab_engine_jobs(session_id, created_at desc);
create index if not exists lab_engine_jobs_engine_idx on public.lab_engine_jobs(engine_id, created_at desc);
create index if not exists lab_engine_jobs_lease_idx on public.lab_engine_jobs(lease_expires_at) where status = 'running';
create index if not exists lab_engine_runs_session_idx on public.lab_engine_runs(session_id, created_at desc);
create index if not exists lab_engine_runs_scene_idx on public.lab_engine_runs(scene_id, created_at desc);
create index if not exists lab_engine_runs_engine_idx on public.lab_engine_runs(engine_id, created_at desc);
create index if not exists lab_engine_artifacts_run_idx on public.lab_engine_artifacts(run_id, created_at);

alter table public.lab_engine_registry enable row level security;
alter table public.lab_engine_jobs enable row level security;
alter table public.lab_engine_runs enable row level security;
alter table public.lab_engine_artifacts enable row level security;
revoke all on public.lab_engine_registry, public.lab_engine_jobs, public.lab_engine_runs, public.lab_engine_artifacts from anon, authenticated;
grant select, insert, update, delete on public.lab_engine_registry, public.lab_engine_jobs, public.lab_engine_runs, public.lab_engine_artifacts to service_role;

-- All mutating queue operations are service-role RPCs; claim uses SKIP LOCKED to give one live owner.
create or replace function public.mystic_claim_next_engine_job(p_runner_id text, p_lease_seconds integer default 60)
returns setof public.lab_engine_jobs language plpgsql security definer set search_path = public as $$
declare claimed public.lab_engine_jobs;
begin
  select * into claimed from public.lab_engine_jobs
   where status = 'pending' and cancellation_requested = false and attempts < max_attempts
   order by priority desc, created_at for update skip locked limit 1;
  if not found then return; end if;
  update public.lab_engine_jobs set status='running', claimed_by=p_runner_id, attempts=attempts+1,
    started_at=coalesce(started_at, timezone('utc', now())), heartbeat_at=timezone('utc', now()),
    lease_expires_at=timezone('utc', now()) + make_interval(secs => greatest(10, least(p_lease_seconds, 300)))
   where job_id=claimed.job_id returning * into claimed;
  return next claimed;
end $$;
create or replace function public.mystic_heartbeat_engine_job(p_job_id text, p_runner_id text, p_lease_seconds integer default 60)
returns boolean language plpgsql security definer set search_path = public as $$
begin
 update public.lab_engine_jobs set heartbeat_at=timezone('utc',now()), lease_expires_at=timezone('utc',now())+make_interval(secs=>greatest(10,least(p_lease_seconds,300)))
 where job_id=p_job_id and status='running' and claimed_by=p_runner_id and cancellation_requested=false;
 return found;
end $$;
create or replace function public.mystic_complete_engine_job(p_job_id text, p_runner_id text, p_run_id text, p_engine_version text, p_result jsonb, p_summary jsonb, p_visualization jsonb, p_reproducibility jsonb, p_input_hash text, p_output_hash text, p_duration_ms bigint, p_warnings jsonb default '[]'::jsonb)
returns boolean language plpgsql security definer set search_path = public as $$
begin
 if not exists(select 1 from public.lab_engine_jobs where job_id=p_job_id and status='running' and claimed_by=p_runner_id and cancellation_requested=false) then return false; end if;
 insert into public.lab_engine_runs(run_id,job_id,session_id,experiment_id,scene_id,engine_id,engine_version,status,result,summary,visualization,reproducibility,input_hash,output_hash,duration_ms,warnings,completed_at)
 select p_run_id,job_id,session_id,experiment_id,scene_id,engine_id,p_engine_version,'completed',p_result,p_summary,p_visualization,p_reproducibility,p_input_hash,p_output_hash,p_duration_ms,p_warnings,timezone('utc',now()) from public.lab_engine_jobs where job_id=p_job_id
 on conflict (job_id) do nothing;
 update public.lab_engine_jobs set status='completed', completed_at=timezone('utc',now()), lease_expires_at=null where job_id=p_job_id and status='running' and claimed_by=p_runner_id;
 return found;
end $$;
create or replace function public.mystic_fail_engine_job(p_job_id text, p_runner_id text, p_status text, p_safe_error text)
returns boolean language plpgsql security definer set search_path = public as $$
begin
 if p_status not in ('failed','cancelled','timed_out') then raise exception 'invalid final status'; end if;
 update public.lab_engine_jobs set status=p_status, safe_error=left(p_safe_error,1000), completed_at=timezone('utc',now()), lease_expires_at=null
 where job_id=p_job_id and status='running' and claimed_by=p_runner_id; return found;
end $$;
create or replace function public.mystic_request_engine_job_cancellation(p_job_id text)
returns boolean language plpgsql security definer set search_path = public as $$
begin update public.lab_engine_jobs set cancellation_requested=true, status=case when status='pending' then 'cancelled' else status end where job_id=p_job_id and status in ('pending','running'); return found; end $$;
create or replace function public.mystic_release_expired_engine_leases()
returns integer language plpgsql security definer set search_path = public as $$ declare released integer; begin
 update public.lab_engine_jobs set status=case when cancellation_requested then 'cancelled' when attempts >= max_attempts then 'timed_out' else 'pending' end, claimed_by='', lease_expires_at=null
 where status='running' and lease_expires_at < timezone('utc',now()); get diagnostics released=row_count; return released; end $$;
revoke all on function public.mystic_claim_next_engine_job(text,integer), public.mystic_heartbeat_engine_job(text,text,integer), public.mystic_complete_engine_job(text,text,text,text,jsonb,jsonb,jsonb,jsonb,text,text,bigint,jsonb), public.mystic_fail_engine_job(text,text,text,text), public.mystic_request_engine_job_cancellation(text), public.mystic_release_expired_engine_leases() from public;
grant execute on function public.mystic_claim_next_engine_job(text,integer), public.mystic_heartbeat_engine_job(text,text,integer), public.mystic_complete_engine_job(text,text,text,text,jsonb,jsonb,jsonb,jsonb,text,text,bigint,jsonb), public.mystic_fail_engine_job(text,text,text,text), public.mystic_request_engine_job_cancellation(text), public.mystic_release_expired_engine_leases() to service_role;
