import { Html, Line } from "@react-three/drei";
import type { EngineRun, VisualizationLayer } from "./descriptor-schema";
import { normalizeDescriptor } from "./descriptor-normalizer";

type Point = [number, number, number];
const safeNumber = (value: unknown) => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 1_000_000 ? value : undefined;
function point(value: unknown): Point | undefined {
  if (Array.isArray(value) && value.length >= 3) { const numbers = value.slice(0, 3).map(safeNumber); return numbers.every((entry) => entry !== undefined) ? numbers as Point : undefined; }
  if (!value || typeof value !== "object") return undefined; const data = value as Record<string, unknown>; const numbers = [safeNumber(data.x), safeNumber(data.y), safeNumber(data.z)]; return numbers.every((entry) => entry !== undefined) ? numbers as Point : undefined;
}
function points(value: unknown): Point[] { return Array.isArray(value) ? value.map(point).filter((entry): entry is Point => Boolean(entry)) : []; }
function color(layer: VisualizationLayer, fallback: string) { const value = (layer.style as Record<string, unknown> | undefined)?.color; return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value) ? value : fallback; }
function linePoints(layer: VisualizationLayer): Point[] { const data = layer.data as Record<string, unknown>; const direct = points(data.points); if (direct.length > 1) return direct; const endpoints = [point(data.start), point(data.end)].filter((entry): entry is Point => Boolean(entry)); return endpoints.length > 1 ? endpoints : []; }

function Markers({ layer, color: markerColor }: { layer: VisualizationLayer; color: string }) { const data = layer.data as Record<string, unknown>; const values = layer.type === "point" ? [data.point ?? data.position ?? data] : data.points; return <>{points(values).map((value, index) => <mesh key={`${layer.id}-${index}`} position={value}><sphereGeometry args={[0.06, 10, 8]} /><meshStandardMaterial color={markerColor} emissive={markerColor} emissiveIntensity={0.25} /></mesh>)}</>; }
function Vectors({ layer, color: vectorColor }: { layer: VisualizationLayer; color: string }) { const data = layer.data as { vectors?: unknown[] }; return <>{(data.vectors ?? []).slice(0, 4000).map((entry, index) => { const vector = entry as Record<string, unknown>; const origin = point(vector.origin) ?? [0, index * 0.12, 0] as Point; const direction = point(vector.direction) ?? point(vector) ?? [0, 0, 0] as Point; const end: Point = [origin[0] + direction[0], origin[1] + direction[1], origin[2] + direction[2]]; return <Line key={`${layer.id}-${index}`} points={[origin, end]} color={vectorColor} lineWidth={1.5} />; })}</>; }
function ObjectStates({ layer, color: objectColor }: { layer: VisualizationLayer; color: string }) { const data = layer.data as Record<string, unknown>; const values = Array.isArray(data.objects) ? data.objects : [data]; return <>{values.slice(0, 1000).map((value, index) => { const record = value as Record<string, unknown>; const position = point(record.position ?? record); return position ? <mesh key={`${layer.id}-${index}`} position={position}><boxGeometry args={[0.14, 0.14, 0.14]} /><meshStandardMaterial color={objectColor} wireframe /></mesh> : null; })}</>; }
function Labels({ layer }: { layer: VisualizationLayer }) { const data = layer.data as Record<string, unknown>; const values = Array.isArray(data.labels) ? data.labels : [data]; return <>{values.slice(0, 256).map((value, index) => { const record = value as Record<string, unknown>; const position = point(record.position ?? record); const text = typeof record.label === "string" ? record.label : typeof record.value === "number" ? String(record.value) : "value"; return position ? <Html key={`${layer.id}-${index}`} position={position} center distanceFactor={10}><span className="result-label">{text.slice(0, 120)}</span></Html> : null; })}</>; }

export function SpatialResultLayers({ runs }: { runs: EngineRun[] }) {
  return <>{runs.flatMap((run) => (normalizeDescriptor(run.visualization).descriptor?.layers ?? []).map((layer) => ({ key: `${run.run_id}:${layer.id}`, layer }))).filter(({ layer }) => layer.visible).map(({ key, layer }) => {
    const layerColor = color(layer, "#ffb454");
    if (["line", "polyline", "trajectory"].includes(layer.type)) { const values = linePoints(layer); return values.length > 1 ? <Line key={key} points={values} color={layerColor} lineWidth={2} /> : null; }
    if (layer.type === "point" || layer.type === "point_set" || layer.type === "heatmap_points") return <Markers key={key} layer={layer} color={layerColor} />;
    if (layer.type === "vector" || layer.type === "vector_field") return <Vectors key={key} layer={layer} color={layerColor} />;
    if (layer.type === "object_state") return <ObjectStates key={key} layer={layer} color={layerColor} />;
    if (layer.type === "scalar_label") return <Labels key={key} layer={layer} />;
    return null;
  })}</>;
}
