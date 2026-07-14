import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Grid, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

type BenchmarkMetrics = {
  objectCount: number;
  triangleCount: number;
  drawCalls: number;
  frameCount: number;
  averageFrameMs: number;
  p50FrameMs: number;
  p95FrameMs: number;
  approximateFps: number;
  initializationMs: number;
  selectionLatencyMs?: number;
  layerToggleLatencyMs?: number;
  resultLayerCount: number;
  resultPointCount: number;
};

const objectTypes = ["box", "sphere", "cylinder", "cone", "plane"] as const;
const colors = ["#45d6a8", "#5ca8ff", "#ffb454", "#ff7a59", "#b48cff"];
const percentile = (values: number[], ratio: number) => values[Math.min(values.length - 1, Math.max(0, Math.ceil(values.length * ratio) - 1))] ?? 0;

function Primitive({ index, selected, onSelect }: { index: number; selected: boolean; onSelect: (index: number) => void }) {
  const type = objectTypes[index % objectTypes.length];
  const x = (index % 10) - 4.5;
  const z = Math.floor(index / 10) - 4.5;
  const geometry = useMemo(() => {
    if (type === "sphere") return new THREE.SphereGeometry(0.34, 16, 12);
    if (type === "cylinder") return new THREE.CylinderGeometry(0.3, 0.3, 0.72, 16);
    if (type === "cone") return new THREE.ConeGeometry(0.34, 0.72, 16);
    if (type === "plane") return new THREE.PlaneGeometry(0.72, 0.72);
    return new THREE.BoxGeometry(0.64, 0.64, 0.64);
  }, [type]);
  return <mesh position={[x, type === "plane" ? 0.02 : 0.36, z]} geometry={geometry} onClick={(event) => { event.stopPropagation(); onSelect(index); }}><meshStandardMaterial color={selected ? "#ffffff" : colors[index % colors.length]} roughness={0.58} metalness={0.08} /></mesh>;
}

function Collector({ startedAt, onReady }: { startedAt: number; onReady: (metrics: BenchmarkMetrics) => void }) {
  const prior = useRef<number | undefined>(undefined);
  const initializedAt = useRef<number | undefined>(undefined);
  const frames = useRef<number[]>([]);
  const reported = useRef(false);
  useFrame(({ gl }) => {
    const now = performance.now();
    initializedAt.current ??= now;
    const previous = prior.current ?? now;
    prior.current = now;
    const elapsed = now - startedAt;
    if (elapsed < 3_000 || reported.current) return;
    frames.current.push(now - previous);
    if (elapsed < 13_000) return;
    reported.current = true;
    const samples = frames.current.slice().sort((a, b) => a - b);
    const average = samples.reduce((total, value) => total + value, 0) / Math.max(1, samples.length);
    onReady({ objectCount: 100, resultLayerCount: 5, resultPointCount: 359, triangleCount: gl.info.render.triangles, drawCalls: gl.info.render.calls, frameCount: samples.length, averageFrameMs: average, p50FrameMs: percentile(samples, 0.5), p95FrameMs: percentile(samples, 0.95), approximateFps: average ? 1_000 / average : 0, initializationMs: initializedAt.current - startedAt });
  });
  return null;
}

function ResultLayerFixtures({ visible }: { visible: boolean }) {
  const projectile = useMemo(() => Array.from({ length: 60 }, (_, index) => [-4 + index * 0.12, 0.2 + index * 0.1 - index * index * 0.0015, -3] as [number, number, number]), []);
  const nBody = useMemo(() => Array.from({ length: 3 }, (_, body) => Array.from({ length: 50 }, (_, index) => [Math.cos(index / 8 + body * 2) * (1 + body * 0.25), 0.5 + body * 0.2, Math.sin(index / 8 + body * 2) * (1 + body * 0.25)] as [number, number, number])), []);
  const heatmap = useMemo(() => Array.from({ length: 64 }, (_, index) => [((index % 8) - 3.5) * 0.22, 0.03, (Math.floor(index / 8) - 3.5) * 0.22 + 3] as [number, number, number]), []);
  if (!visible) return null;
  return <>{<Line points={projectile} color="#ffb454" lineWidth={2} />}{nBody.map((points, index) => <Line key={index} points={points} color={["#5ca8ff", "#b48cff", "#45d6a8"][index]} lineWidth={1.5} />)}{Array.from({ length: 40 }, (_, index) => <Line key={`vector-${index}`} points={[[3, index * 0.06, -2 + (index % 8) * 0.18], [3.25, index * 0.06 + 0.1, -2 + (index % 8) * 0.18]]} color="#ff7a59" lineWidth={1} />)}{heatmap.map((position, index) => <mesh key={`heat-${index}`} position={position}><sphereGeometry args={[0.035, 6, 4]} /><meshBasicMaterial color="#ffb454" /></mesh>)}{Array.from({ length: 5 }, (_, index) => <mesh key={`scalar-${index}`} position={[-2 + index, 0.05, 3]}><sphereGeometry args={[0.045, 6, 4]} /><meshBasicMaterial color="#ffffff" /></mesh>)}</>;
}

export default function LabBenchmark() {
  const startedAt = useRef(performance.now()).current;
  const [selected, setSelected] = useState<number>();
  const [metrics, setMetrics] = useState<BenchmarkMetrics>(); const [layersVisible, setLayersVisible] = useState(true);
  const select = (index: number) => { const started = performance.now(); setSelected(index); requestAnimationFrame(() => setMetrics((current) => current ? { ...current, selectionLatencyMs: performance.now() - started } : current)); };
  const toggleLayers = () => { const started = performance.now(); setLayersVisible((current) => !current); requestAnimationFrame(() => setMetrics((current) => current ? { ...current, layerToggleLatencyMs: performance.now() - started } : current)); };
  return <div className="lab-page" data-testid="benchmark-page"><header className="lab-toolbar"><div><p className="eyebrow">MYSTIC LAB / REPRODUCIBLE BENCHMARK</p><h1>100 primitive renderer benchmark</h1></div><div className="toolbar-actions"><button onClick={() => select(0)}>Select benchmark object</button><button onClick={toggleLayers}>{layersVisible ? "Hide result layers" : "Show result layers"}</button></div></header><p className="caption">Fixed 10×10 primitive baseline plus five deterministic Phase 2A result-layer groups (projectile, vectors, N-body, scalar markers, and heatmap points). Postprocessing is intentionally disabled.</p><section className="viewport-wrap" style={{ minHeight: 640 }}><Canvas camera={{ position: [8, 8, 10], fov: 45 }} dpr={[1, 2]}><color attach="background" args={["#101315"]} /><ambientLight intensity={0.75} /><directionalLight position={[5, 8, 4]} intensity={1.4} /><Grid infiniteGrid cellSize={1} sectionSize={5} cellColor="#263036" sectionColor="#3a464a" /><axesHelper args={[2]} />{Array.from({ length: 100 }, (_, index) => <Primitive key={index} index={index} selected={selected === index} onSelect={select} />)}<ResultLayerFixtures visible={layersVisible} /><Collector startedAt={startedAt} onReady={setMetrics} /><OrbitControls makeDefault /></Canvas></section><section className="panel"><h2>Measured browser metrics</h2>{metrics ? <pre data-testid="benchmark-metrics">{JSON.stringify({ browser: navigator.userAgent, viewport: { width: window.innerWidth, height: window.innerHeight }, devicePixelRatio: window.devicePixelRatio, ...metrics }, null, 2)}</pre> : <p data-testid="benchmark-warming">Warming for 3 seconds, then measuring 10 seconds…</p>}</section></div>;
}
