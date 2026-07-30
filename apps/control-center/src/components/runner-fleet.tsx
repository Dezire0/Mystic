import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Runner } from "../api/contracts";

function RunnerActions({ runner, reload }: { runner: Runner; reload: () => void }) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const actions = runner.quarantined ? ["restore"] as const : runner.maintenance_state ? ["resume"] as const : runner.fleet_state === "draining" ? ["resume", "maintenance", "quarantine"] as const : ["drain", "maintenance", "quarantine"] as const;
  async function perform(action: "drain" | "resume" | "maintenance" | "restore" | "quarantine") {
    if (!window.confirm(`Confirm ${action} for ${runner.runner_id}?`)) return;
    setPending(true); setMessage("");
    try { await api.runnerAction(runner.runner_id, action); setMessage(`${action} requested.`); reload(); }
    catch (error) { setMessage(error instanceof ApiError ? error.message : "The runner action failed."); }
    finally { setPending(false); }
  }
  return <><div className="toolbar-actions">{actions.map((action) => <button key={action} className={action === "quarantine" ? "danger small" : "small"} disabled={pending} onClick={() => void perform(action)}>{action}</button>)}</div>{message && <small role="status">{message}</small>}</>;
}

export function RunnerFleetPage() {
  const fleet = useQuery({ queryKey: ["runner-fleet"], queryFn: api.runners, refetchInterval: 10_000 });
  if (fleet.isLoading) return <p className="panel">Loading runner fleet…</p>;
  if (fleet.error) return <p className="error" role="alert">{fleet.error instanceof ApiError ? fleet.error.message : "Runner fleet data is unavailable."}</p>;
  const data = fleet.data;
  if (!data) return null;
  return <><header className="page-header"><div><p className="eyebrow">MYSTIC LAB / TRUSTED COMPUTE</p><h1>Runner fleet</h1><p>Mode: {data.fleet_mode} · Protocol: {data.protocol_version}</p></div></header><section className="panel"><dl><dt>Registered runners</dt><dd>{data.metrics.registered_runners}</dd><dt>Available slots</dt><dd>{data.metrics.available_slots}</dd><dt>Active jobs</dt><dd>{data.metrics.active_jobs}</dd><dt>Safe failure count</dt><dd>{data.metrics.safe_failure_count}</dd></dl></section><section className="panel table-wrap"><table><thead><tr><th>Runner</th><th>State</th><th>Platform</th><th>Engines</th><th>Slots</th><th>Heartbeat</th><th>Failures</th><th>Actions</th></tr></thead><tbody>{data.runners.map((runner) => <tr key={runner.runner_id}><td><strong>{runner.display_name || runner.runner_id}</strong><small>{runner.runner_id} · {runner.runner_version}</small></td><td><span className={`status ${runner.fleet_state === "online" || runner.fleet_state === "busy" ? "good" : "warn"}`}>{runner.fleet_state}</span></td><td>{runner.operating_system || "—"} {runner.architecture || ""}</td><td>{runner.supported_engines.map((engine) => engine.engine_id).join(", ") || "—"}</td><td>{runner.available_slots}/{runner.max_concurrent_jobs}</td><td>{runner.heartbeat_age_seconds === null ? "unknown" : `${runner.heartbeat_age_seconds}s`}</td><td>{runner.failure_count}</td><td><Link className="small button" to={`/runners/${encodeURIComponent(runner.runner_id)}`}>Inspect</Link><RunnerActions runner={runner} reload={() => void fleet.refetch()} /></td></tr>)}</tbody></table></section></>;
}

export function RunnerDetailPage() {
  const { runnerId = "" } = useParams();
  const runner = useQuery({ queryKey: ["runner", runnerId], queryFn: () => api.runner(runnerId) });
  const jobs = useQuery({ queryKey: ["runner-jobs", runnerId], queryFn: () => api.runnerJobs(runnerId) });
  const attempts = useQuery({ queryKey: ["runner-attempts", runnerId], queryFn: () => api.runnerAttempts(runnerId) });
  const audit = useQuery({ queryKey: ["runner-audit", runnerId], queryFn: () => api.runnerAuditEvents(runnerId) });
  if (runner.isLoading) return <p className="panel">Loading runner…</p>;
  if (runner.error || !runner.data) return <p className="error" role="alert">Runner details are unavailable.</p>;
  const value = runner.data;
  return <><header className="page-header"><div><p className="eyebrow">RUNNER DETAIL</p><h1>{value.display_name || value.runner_id}</h1><p>{value.runner_id} · {value.fleet_state}</p></div><Link className="button" to="/runners">All runners</Link></header><section className="two-column"><section className="panel"><h2>Safe capabilities</h2><dl><dt>Platform</dt><dd>{value.operating_system || "—"} {value.architecture || ""}</dd><dt>Runtime</dt><dd>{value.runtime_version || "—"}</dd><dt>Slots</dt><dd>{value.available_slots}/{value.max_concurrent_jobs}</dd><dt>Heartbeat age</dt><dd>{value.heartbeat_age_seconds === null ? "unknown" : `${value.heartbeat_age_seconds}s`}</dd><dt>Resource classes</dt><dd>{value.resource_classes.join(", ") || "—"}</dd></dl><h3>Supported engines</h3><ul>{value.supported_engines.map((engine) => <li key={engine.engine_id}>{engine.engine_id} · {engine.version}</li>)}</ul></section><section className="panel"><h2>Recent jobs</h2>{jobs.data?.jobs.length ? <ul>{jobs.data.jobs.map((job) => <li key={String(job.job_id)}>{String(job.job_id)} · {String(job.status)}</li>)}</ul> : <p>No assigned jobs.</p>}<h2>Attempt history</h2>{attempts.data?.attempts.length ? <ul>{attempts.data.attempts.map((attempt) => <li key={String(attempt.attempt_id)}>{String(attempt.job_id)} · {String(attempt.state)} · attempt {String(attempt.attempt_number)}</li>)}</ul> : <p>No safe attempt history.</p>}<h2>Audit history</h2>{audit.data?.events.length ? <ul>{audit.data.events.map((event) => <li key={String(event.event_id)}>{String(event.event_type)} · {String(event.created_at)}</li>)}</ul> : <p>No safe audit events.</p>}</section></section></>;
}
