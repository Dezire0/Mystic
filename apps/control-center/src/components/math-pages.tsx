import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, type EngineJob } from "../api/client";

const terminal = new Set(["completed", "failed", "cancelled", "timed_out", "expired"]);

function ErrorText({ error }: { error: unknown }) { return <p className="error" role="alert">{error instanceof ApiError ? error.message : "The math engine operation could not be completed."}</p>; }

export function MathEnginesPage() {
  const engines = useQuery({ queryKey:["math-engines"], queryFn:api.engines, refetchInterval:30_000 });
  const runs = useQuery({ queryKey:["math-runs"], queryFn:api.engineRuns, refetchInterval:10_000 });
  const [engineId, setEngineId] = useState("math.linear_algebra");
  const [inputText, setInputText] = useState('{"operation":"rank","matrix":[[1,0],[0,1]]}');
  const [job, setJob] = useState<EngineJob>();
  const [message, setMessage] = useState("");
  if (engines.isLoading) return <p className="panel">Loading trusted math solvers…</p>;
  if (engines.error) return <ErrorText error={engines.error}/>;
  const solvers = (engines.data ?? []).filter((item) => item.domain === "math");
  const selected = solvers.find((item) => item.engine_id === engineId);
  const mathRuns = (runs.data ?? []).filter((item) => item.engine_id.startsWith("math."));
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    let input: Record<string, unknown>;
    try { input = JSON.parse(inputText) as Record<string, unknown>; } catch { setMessage("Problem input must be valid declarative JSON."); return; }
    try { setJob(await api.createEngineJob({ engine_id:engineId, input, requested_visualization:true })); setMessage("Job queued for a compatible trusted runner."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Math job could not be queued."); }
  }
  return <>
    <header className="page-header"><div><p className="eyebrow">MYSTIC LAB / TRUSTED COMPUTE</p><h1>Math engines</h1><p>All calculations run through a registered trusted runner. This console never evaluates solver input.</p></div><Link className="button" to="/math/benchmarks">Benchmarks</Link></header>
    <section className="two-column"><section className="panel"><h2>Solver browser</h2><div className="tree">{solvers.map((solver)=><button key={solver.engine_id} onClick={()=>setEngineId(solver.engine_id)}><strong>{solver.display_name}</strong><small>{solver.engine_id} · {solver.capabilities.join(", ")}</small></button>)}</div></section><section className="panel"><h2>Solver contract</h2>{selected ? <dl><dt>Version</dt><dd>{selected.version}</dd><dt>Capabilities</dt><dd>{selected.capabilities.join(", ")}</dd><dt>Availability</dt><dd>{selected.availability}</dd><dt>Runtime</dt><dd>trusted runner only</dd><dt>Tolerances</dt><dd>Declared per problem; bounded by solver manifest.</dd></dl> : <p>Select a solver.</p>}</section></section>
    <section className="two-column"><form className="panel stack" onSubmit={(event)=>void submit(event)}><h2>Problem editor</h2><label>Solver<select value={engineId} onChange={(event)=>setEngineId(event.target.value)}>{solvers.map((solver)=><option key={solver.engine_id} value={solver.engine_id}>{solver.engine_id}</option>)}</select></label><label>Declarative problem JSON<textarea aria-label="Declarative math problem JSON" value={inputText} onChange={(event)=>setInputText(event.target.value)} /></label><p className="caption">Only documented operation families are accepted. Expressions, code, imports, and URLs are rejected by the runner.</p><button disabled={!engineId}>Queue trusted math job</button>{message && <p role="status">{message}</p>}{job && <p>Job: <code>{job.job_id}</code> · {terminal.has(job.status) ? job.status : "queued"}</p>}</form><section className="panel"><h2>Visualization and convergence</h2><p>Completed runs publish renderer-independent descriptors, convergence information, tolerances, and canonical reproducibility hashes.</p><h3>Sensitivity and uncertainty</h3><p>Only solvers declaring these capabilities emit sensitivity or uncertainty metadata; unavailable fields are not inferred.</p><h3>History</h3>{runs.isLoading ? <p>Loading history…</p> : <ul>{mathRuns.slice(0,10).map((run)=><li key={run.run_id}><Link to={`/runs/${encodeURIComponent(run.run_id)}`}>{run.engine_id} · {run.status}</Link></li>)}</ul>}{!mathRuns.length && !runs.isLoading && <p>No completed math runs have been returned by the backend.</p>}</section></section>
  </>;
}

export function MathBenchmarksPage() {
  const [workload, setWorkload] = useState("matrix"); const [dimension, setDimension] = useState(32); const [message, setMessage] = useState("");
  async function submit(event: React.FormEvent) { event.preventDefault(); try { const job=await api.createEngineJob({engine_id:"math.benchmark",input:{operation:workload,dimension},requested_visualization:true}); setMessage(`Benchmark job ${job.job_id} queued for a trusted runner.`); } catch (error) { setMessage(error instanceof Error ? error.message : "Benchmark could not be queued."); } }
  return <><header className="page-header"><div><p className="eyebrow">MYSTIC LAB / MEASURED COMPUTE</p><h1>Math benchmarks</h1></div><Link className="button" to="/math">Math engines</Link></header><form className="panel stack" onSubmit={(event)=>void submit(event)}><label>Bounded workload<select value={workload} onChange={(event)=>setWorkload(event.target.value)}>{["matrix","ode","optimization","regression","monte_carlo"].map((item)=><option key={item}>{item}</option>)}</select></label><label>Dimension<input type="number" min="2" max="64" value={dimension} onChange={(event)=>setDimension(Number(event.target.value))}/></label><p className="caption">The benchmark returns measured runtime, convergence or error fields where applicable, and a bounded workload summary. It is not a hardware certification.</p><button>Queue benchmark</button>{message && <p role="status">{message}</p>}</form></>;
}
