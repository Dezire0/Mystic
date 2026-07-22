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
