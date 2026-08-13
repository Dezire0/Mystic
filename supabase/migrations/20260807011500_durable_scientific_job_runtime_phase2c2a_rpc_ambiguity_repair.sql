-- Phase 2C.2A repair: RETURNS TABLE output variables are PL/pgSQL variables.
-- Every table-column reference in these two queue functions is explicitly
-- qualified so PostgreSQL's default variable_conflict=error mode remains
-- fail-closed instead of selecting an arbitrary interpretation.

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
  select * into current_job from public.lab_scientific_jobs as candidate
    where candidate.status = 'READY' and candidate.ready_at <= now_value
      and candidate.attempt < candidate.max_attempts and not candidate.cancellation_requested
    order by candidate.ready_at, candidate.job_id for update skip locked limit 1;
  if not found then return; end if;
  raw_token := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
  token_hash := public.mystic_scientific_job_token_hash(raw_token);
  next_expiry := now_value + make_interval(secs => p_lease_seconds);
  update public.lab_scientific_jobs as target set
    status='LEASED',attempt=target.attempt+1,lease_owner=p_worker_id,lease_token_hash=token_hash,
    lease_acquired_at=now_value,lease_expires_at=next_expiry,revision=target.revision+1,updated_at=now_value
    where target.job_id=current_job.job_id returning * into current_job;
  insert into public.lab_scientific_job_leases(
    lease_id,job_id,lease_owner,token_hash,acquired_at,expires_at
  ) values ('job_lease_' || replace(gen_random_uuid()::text, '-', ''),current_job.job_id,p_worker_id,token_hash,now_value,next_expiry);
  update public.lab_scientific_job_outbox_events as outbox set status='ACKNOWLEDGED',acknowledged_at=now_value,
    revision=outbox.revision+1,updated_at=now_value
    where outbox.job_id=current_job.job_id and outbox.status='DISPATCHED';
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
    select outbox_event.* from public.lab_scientific_job_outbox_events as outbox_event
      join public.lab_scientific_jobs as job on job.job_id=outbox_event.job_id
      where outbox_event.status in ('PENDING','FAILED') and outbox_event.available_at <= now_value
        and job.status='READY'
      order by outbox_event.available_at,outbox_event.event_id for update of outbox_event skip locked limit p_limit
  loop
    update public.lab_scientific_job_outbox_events as target set status='DISPATCHED',attempt=target.attempt+1,
      dispatched_at=now_value,safe_error='',revision=target.revision+1,updated_at=now_value
      where target.event_id=current_event.event_id returning * into current_event;
    insert into public.lab_scientific_job_events(event_id,job_id,event_type,status,revision,summary,metadata)
      select 'job_event_' || replace(gen_random_uuid()::text, '-', ''),job.job_id,'OUTBOX_DISPATCHED',job.status,
        job.revision,'Durable scientific job dispatch intent published.',jsonb_build_object('outbox_event_id',current_event.event_id)
      from public.lab_scientific_jobs as job where job.job_id=current_event.job_id;
    event_id := current_event.event_id;
    job_id := current_event.job_id;
    event_type := current_event.event_type;
    payload_hash := current_event.payload_hash;
    dispatch_attempt := current_event.attempt;
    return next;
  end loop;
end $$;

revoke all on function public.mystic_acquire_scientific_job_lease(text,integer) from public, anon, authenticated;
revoke all on function public.mystic_dispatch_scientific_job_outbox(integer) from public, anon, authenticated;
grant execute on function public.mystic_acquire_scientific_job_lease(text,integer) to service_role;
grant execute on function public.mystic_dispatch_scientific_job_outbox(integer) to service_role;
