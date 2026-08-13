import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ScientificWorker } from "../api/contracts";

function Failure({ error }: { error: unknown }) { return <p className="panel error" role="alert">{error instanceof ApiError ? error.message : "Trusted worker status is unavailable."}</p>; }
function timestamp(value: string) { return value ? new Date(value).toLocaleString() : "—"; }
function WorkerSummary({ worker }: { worker: ScientificWorker }) { return <div className="tree"><Link to={`/workers/${encodeURIComponent(worker.worker_id)}`}><strong>{worker.worker_id}</strong><small>{worker.status} · {worker.active_jobs}/{worker.capacity} active · completed {worker.completed_count} · failed {worker.failed_count}</small></Link></div>; }

export function ScientificWorkersPage() {
  const workers=useQuery({queryKey:["scientific-workers"],queryFn:api.scientificWorkers,refetchInterval:10_000});
  if (workers.isLoading) return <p className="panel">Loading trusted worker status…</p>;
  if (workers.error || !workers.data) return <Failure error={workers.error}/>;
  return <><header className="page-header"><div><p className="eyebrow">MYSTIC LAB / TRUSTED EXECUTION</p><h1>Scientific workers</h1><p>Safe observability only. Browser controls cannot acquire, heartbeat, execute, complete, fail, drain, or reconcile jobs.</p></div><button onClick={()=>void workers.refetch()}>Refresh</button></header><section className="metrics"><div className="metric"><span>Workers</span><strong>{workers.data.count}</strong></div><div className="metric"><span>Active jobs</span><strong>{workers.data.workers.reduce((total,worker)=>total+worker.active_jobs,0)}</strong></div><div className="metric"><span>Capacity</span><strong>{workers.data.workers.reduce((total,worker)=>total+worker.capacity,0)}</strong></div></section><section className="panel"><h2>Worker registry</h2>{workers.data.workers.length ? workers.data.workers.map((worker)=><WorkerSummary key={worker.worker_id} worker={worker}/>) : <p className="empty">No trusted worker has published a safe status record.</p>}</section><section className="panel"><h2>Administrative boundary</h2><p>Drain and reconciliation are authenticated worker-service CLI operations. They are intentionally not browser actions and do not expand the public MCP mutation surface.</p></section></>;
}

export function ScientificWorkerDetailPage() {
  const { workerId="" }=useParams(); const worker=useQuery({queryKey:["scientific-worker",workerId],queryFn:()=>api.scientificWorker(workerId),refetchInterval:10_000});
  if (worker.isLoading) return <p className="panel">Loading trusted worker status…</p>;
  if (worker.error || !worker.data) return <Failure error={worker.error}/>;
  const data=worker.data;
  return <><header className="page-header"><div><p className="eyebrow">TRUSTED SCIENTIFIC WORKER</p><h1>{data.worker_id}</h1><p>{data.status} · {data.active_jobs}/{data.capacity} active · uptime {data.uptime_seconds}s</p></div><Link className="button" to="/workers">Workers</Link></header><section className="two-column"><section className="panel"><h2>Safe worker health</h2><dl><dt>Worker version</dt><dd>{data.worker_version}</dd><dt>Runtime version</dt><dd>{data.runtime_version}</dd><dt>Started</dt><dd>{timestamp(data.process_start_time)}</dd><dt>Last backend contact</dt><dd>{timestamp(data.last_successful_backend_contact)}</dd><dt>Last poll</dt><dd>{timestamp(data.last_poll_at)}</dd><dt>Completed / failed / cancelled</dt><dd>{data.completed_count} / {data.failed_count} / {data.cancelled_count}</dd><dt>Lost leases</dt><dd>{data.stale_lease_count}</dd><dt>Reconciliations</dt><dd>{data.reconciliation_count}</dd></dl></section><section className="panel"><h2>Supported execution</h2><pre>{JSON.stringify({engines:data.supported_engines,engine_versions:data.supported_engine_versions,resource_classes:data.resource_classes,safe_last_error:data.safe_last_error || "none"},null,2)}</pre></section></section><section className="panel"><h2>Control boundary</h2><p>This view has no execution, lease, or repair controls. Those operations require the dedicated worker identity and remain outside MCP and the browser.</p></section></>;
}
