import { z } from "zod";
import { sceneDocumentSchema } from "../engine/scene-schema";
export { engineArtifactSchema, engineJobSchema, engineManifestSchema, engineRunSchema, visualizationDescriptorSchema } from "../engine-results/descriptor-schema";

export const safeErrorSchema = z.object({ code: z.string(), message: z.string(), diagnosticId: z.string().optional() });
export const providerSchema = z.object({
  provider_id: z.string(), display_name: z.string().optional(), provider_type: z.string().optional(), auth_method: z.string().optional(), configured: z.boolean().optional(), connected: z.boolean().optional(), ready: z.boolean().optional(), model_list: z.array(z.string()).optional(), model_name: z.string().optional(), last_verified_at: z.string().nullable().optional(), failure_reason: z.string().optional(), execution_location: z.string().optional(), quota_source: z.string().optional(), setup_url: z.string().url().optional(),
}).passthrough();
export const providerListSchema = z.object({ providers: z.array(providerSchema), warnings: z.array(z.string()).optional() });
export const sceneEnvelopeSchema = z.object({ scene: sceneDocumentSchema });
export const campaignSummarySchema = z.object({
  campaign_id: z.string(), title: z.string(), domain: z.string(), phase: z.string(), status: z.string(), revision: z.number(), iteration: z.number(), created_at: z.string(), updated_at: z.string(),
});
const campaignEntitySchema = z.record(z.string(), z.unknown());
export const campaignSchema = z.object({
  campaign_id: z.string(), metadata: campaignEntitySchema, phase: z.string(), status: z.string(), revision: z.number(), created_at: z.string(), updated_at: z.string(),
  goals: z.array(campaignEntitySchema), questions: z.array(campaignEntitySchema), hypotheses: z.array(campaignEntitySchema), evidence: z.array(campaignEntitySchema), experiments: z.array(campaignEntitySchema), models: z.array(campaignEntitySchema), reviews: z.array(campaignEntitySchema), failures: z.array(campaignEntitySchema), decisions: z.array(campaignEntitySchema), artifacts: z.array(campaignEntitySchema), scientific_jobs: z.array(campaignEntitySchema).default([]), scientific_job_attachments: z.array(campaignEntitySchema).default([]), checkpoints: z.array(campaignEntitySchema), graph: campaignEntitySchema, timeline: campaignEntitySchema, budget: campaignEntitySchema, statistics: campaignEntitySchema, runtime: campaignEntitySchema, summary: campaignSummarySchema,
});
export const campaignListSchema = z.object({ campaigns: z.array(campaignSummarySchema), count: z.number() });
export const campaignGraphSchema = z.object({ campaign_id: z.string(), nodes: z.array(campaignEntitySchema), edges: z.array(campaignEntitySchema), graph_hash: z.string() });
export const campaignTimelineSchema = z.object({ campaign_id: z.string(), events: z.array(campaignEntitySchema), count: z.number() });
export const scientificJobSummarySchema = z.object({
  job_id: z.string(), campaign_id: z.string(), engine_name: z.string(), engine_version: z.string(), status: z.string(),
  attempt: z.number(), max_attempts: z.number(), ready_at: z.string(), created_at: z.string(), updated_at: z.string(),
  started_at: z.string().optional(), finished_at: z.string().optional(), lease_owner: z.string().optional(),
  lease_expires_at: z.string().optional(), result_hash: z.string().optional(), failure_class: z.string().optional(),
  error: z.string().optional(), attachment_state: z.string().optional(), attachment_error: z.string().optional(), revision: z.number(),
}).passthrough();
export const scientificJobSchema = scientificJobSummarySchema.extend({
  input_metadata: campaignEntitySchema.optional(), lease: campaignEntitySchema.optional(), result_metadata: campaignEntitySchema.optional(),
  failure: campaignEntitySchema.nullable().optional(), attachment: campaignEntitySchema.nullable().optional(),
  failure_attachment_state: z.string().optional(), failure_attachment_error: z.string().optional(),
  lease_history: z.array(campaignEntitySchema).optional(), outbox: z.array(campaignEntitySchema).optional(), events: z.array(campaignEntitySchema).optional(), provenance: campaignEntitySchema.optional(),
});
export const scientificJobListSchema = z.object({ jobs: z.array(scientificJobSummarySchema), count: z.number() });
export type Provider = z.infer<typeof providerSchema>;
export type SceneEnvelope = z.infer<typeof sceneEnvelopeSchema>;
export type Campaign = z.infer<typeof campaignSchema>;
export type CampaignSummary = z.infer<typeof campaignSummarySchema>;
export type ScientificJob = z.infer<typeof scientificJobSchema>;
export type ScientificJobSummary = z.infer<typeof scientificJobSummarySchema>;
