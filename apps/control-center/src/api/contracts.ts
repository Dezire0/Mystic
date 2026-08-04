import { z } from "zod";
import { sceneDocumentSchema } from "../engine/scene-schema";
export { engineArtifactSchema, engineJobSchema, engineManifestSchema, engineRunSchema, visualizationDescriptorSchema } from "../engine-results/descriptor-schema";

export const safeErrorSchema = z.object({ code: z.string(), message: z.string(), diagnosticId: z.string().optional() });
export const providerSchema = z.object({
  provider_id: z.string(), display_name: z.string().optional(), provider_type: z.string().optional(), auth_method: z.string().optional(), configured: z.boolean().optional(), connected: z.boolean().optional(), ready: z.boolean().optional(), model_list: z.array(z.string()).optional(), model_name: z.string().optional(), last_verified_at: z.string().nullable().optional(), failure_reason: z.string().optional(), execution_location: z.string().optional(), quota_source: z.string().optional(), setup_url: z.string().url().optional(),
}).passthrough();
export const providerListSchema = z.object({ providers: z.array(providerSchema), warnings: z.array(z.string()).optional() });
export const sceneEnvelopeSchema = z.object({ scene: sceneDocumentSchema });
export type Provider = z.infer<typeof providerSchema>;
export type SceneEnvelope = z.infer<typeof sceneEnvelopeSchema>;

export const runnerSchema = z.object({
  runner_id: z.string(), display_name: z.string(), runner_version: z.string(), runtime_version: z.string(), operating_system: z.string(), architecture: z.string(),
  fleet_state: z.string(), supported_engines: z.array(z.object({ engine_id: z.string(), version: z.string() })), resource_classes: z.array(z.string()),
  max_concurrent_jobs: z.number(), active_jobs: z.number(), available_slots: z.number(), cpu_count: z.number(), memory_limit_mb: z.number(), gpu_type: z.string(), region: z.string(), priority: z.number(),
  latest_heartbeat: z.string().nullable(), heartbeat_age_seconds: z.number().nullable(), maintenance_state: z.boolean(), quarantined: z.boolean(), failure_count: z.number(), completed_count: z.number(), safe_last_error: z.string(),
}).strict();
export const runnerFleetSchema = z.object({ fleet_mode: z.string(), protocol_version: z.string(), runners: z.array(runnerSchema), metrics: z.object({ runner_counts: z.record(z.string(), z.number()), registered_runners: z.number(), active_jobs: z.number(), available_slots: z.number(), safe_failure_count: z.number() }) }).strict();
export type Runner = z.infer<typeof runnerSchema>;
export type RunnerFleet = z.infer<typeof runnerFleetSchema>;
