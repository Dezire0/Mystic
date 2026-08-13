import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Metric, Status } from "./app";
import { api } from "./api/client";
import { CampaignDetailPage, CampaignsPage } from "./components/campaign-pages";
import { ScientificJobDetailPage, ScientificJobsPage } from "./components/scientific-job-pages";

function providers(children: React.ReactNode, route="/") { const client=new QueryClient({defaultOptions:{queries:{retry:false}}}); return <QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}>{children}</MemoryRouter></QueryClientProvider>; }
const campaign={campaign_id:"campaign-test",metadata:{title:"Durable campaign",domain:"physics"},phase:"PLANNING",status:"ACTIVE",revision:1,created_at:"2026-08-06T00:00:00Z",updated_at:"2026-08-06T00:00:00Z",goals:[],questions:[],hypotheses:[],evidence:[],experiments:[],models:[],reviews:[],failures:[],decisions:[],artifacts:[],checkpoints:[{checkpoint_id:"checkpoint-1",label:"initial",phase:"PLANNING"}],graph:{},timeline:{},budget:{},statistics:{},runtime:{iteration:0},summary:{campaign_id:"campaign-test",title:"Durable campaign",domain:"physics",phase:"PLANNING",status:"ACTIVE",revision:1,iteration:0,created_at:"2026-08-06T00:00:00Z",updated_at:"2026-08-06T00:00:00Z"}};

afterEach(()=>vi.restoreAllMocks());

describe("Control Center status components", () => {
  it("communicates a ready status with text as well as color", () => { render(<Status value="ready" />); expect(screen.getByText("ready")).toHaveClass("good"); });
  it("renders a labeled operational metric", () => { render(<Metric label="Worker health" value="ok" />); expect(screen.getByText("Worker health")).toBeVisible(); expect(screen.getByText("ok")).toBeVisible(); });
});

describe("Campaign Control Center",()=>{
  it("renders the campaign dashboard from authoritative records",async()=>{ vi.spyOn(api,"campaigns").mockResolvedValue({campaigns:[campaign.summary],count:1}); render(providers(<CampaignsPage/>)); expect(await screen.findByText("Campaign dashboard")).toBeVisible(); expect(await screen.findByText("Durable campaign")).toBeVisible(); });
  it("renders all requested campaign inspection views",async()=>{ vi.spyOn(api,"campaign").mockResolvedValue(campaign); vi.spyOn(api,"campaignGraph").mockResolvedValue({campaign_id:"campaign-test",nodes:[],edges:[],graph_hash:"0".repeat(64)}); vi.spyOn(api,"campaignTimeline").mockResolvedValue({campaign_id:"campaign-test",events:[],count:0}); vi.spyOn(api,"campaignStatistics").mockResolvedValue({transition_count:0}); render(providers(<Routes><Route path="/campaigns/:campaignId" element={<CampaignDetailPage/>}/></Routes>,"/campaigns/campaign-test")); for (const heading of ["Campaign timeline","Knowledge graph viewer","Scientific job queue","Accepted job results","Evidence browser","Experiment queue","Model registry","Failure archive","Checkpoint viewer"]) expect(await screen.findByText(heading)).toBeVisible(); expect(screen.getByRole("link",{name:"Job queue"})).toHaveAttribute("href","/jobs?campaign_id=campaign-test"); });
});

describe("Scientific job Control Center",()=>{
  const job={job_id:"job-test",campaign_id:"campaign-test",engine_name:"physics.simple_projectile",engine_version:"2.0.0",status:"DEAD_LETTER",attempt:3,max_attempts:3,ready_at:"2026-08-06T00:00:00Z",created_at:"2026-08-06T00:00:00Z",updated_at:"2026-08-06T00:00:00Z",started_at:"2026-08-06T00:00:00Z",finished_at:"2026-08-06T00:00:01Z",lease_owner:"",lease_expires_at:"",result_hash:"",failure_class:"ENGINE_PERMANENT",error:"bounded failure",attachment_state:"",revision:4};
  it("renders the durable job queue and dead-letter view",async()=>{ vi.spyOn(api,"scientificJobs").mockResolvedValue({jobs:[job],count:1}); vi.spyOn(api,"scientificJobStatistics").mockResolvedValue({ready_jobs:0,leased_jobs:0,running_jobs:0,succeeded_jobs:0,dead_letter_jobs:1}); render(providers(<ScientificJobsPage/>)); expect(await screen.findByText("Scientific job queue")).toBeVisible(); expect(await screen.findByText("Dead-letter / failure archive")).toBeVisible(); expect((await screen.findAllByText("physics.simple_projectile")).length).toBe(2); });
  it("renders provenance, lease history, outbox, and audit on job detail",async()=>{ vi.spyOn(api,"scientificJob").mockResolvedValue({...job,input_metadata:{hash:"a".repeat(64)},lease:{cancellation_requested:false},result_metadata:{},failure:null,attachment:null,lease_history:[],outbox:[],events:[],provenance:{}}); render(providers(<Routes><Route path="/jobs/:jobId" element={<ScientificJobDetailPage/>}/></Routes>,"/jobs/job-test")); for (const heading of ["Execution and lease","Provenance","Failure / retry","Lease history","Dispatch outbox","Audit timeline"]) expect(await screen.findByText(heading)).toBeVisible(); });
});
