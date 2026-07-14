create index if not exists lab_activity_events_session_id_idx
  on public.lab_activity_events (session_id, created_at desc);
;
