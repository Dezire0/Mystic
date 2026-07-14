import { useEffect, useMemo, useState } from "react";
import { trustedJsonSchema } from "../engine-results/descriptor-schema";

type Schema = Record<string, unknown>;
const MAX_RAW_BYTES = 65_536;
const unsupported = ["oneOf", "anyOf", "allOf", "not", "$ref", "pattern"];

function defaults(schema: Schema): unknown {
  if (schema.default !== undefined) return schema.default;
  if (schema.type === "object") return Object.fromEntries(Object.entries((schema.properties as Record<string, Schema>) ?? {}).map(([key, child]) => [key, defaults(child)]));
  if (schema.type === "array") return [];
  if (schema.type === "boolean") return false;
  if (schema.type === "number" || schema.type === "integer") return 0;
  return "";
}

function validate(schema: Schema, value: unknown, path = "input"): string[] {
  const checked = trustedJsonSchema.safeParse(schema);
  if (!checked.success || unsupported.some((key) => key in schema)) return [`${path}: unsupported schema feature`];
  if (Array.isArray(schema.enum) && !schema.enum.some((item) => Object.is(item, value))) return [`${path}: choose a listed value`];
  if (schema.type === "object") {
    if (!value || typeof value !== "object" || Array.isArray(value)) return [`${path}: must be an object`];
    const record = value as Record<string, unknown>; const properties = (schema.properties as Record<string, Schema>) ?? {}; const issues: string[] = [];
    for (const key of schema.required as string[] ?? []) if (!(key in record)) issues.push(`${path}.${key}: required`);
    if (schema.additionalProperties === false) for (const key of Object.keys(record)) if (!(key in properties)) issues.push(`${path}.${key}: is not allowed`);
    for (const [key, child] of Object.entries(properties)) if (key in record) issues.push(...validate(child, record[key], `${path}.${key}`));
    return issues;
  }
  if (schema.type === "array") {
    if (!Array.isArray(value)) return [`${path}: must be an array`];
    const issues: string[] = []; if (typeof schema.minItems === "number" && value.length < schema.minItems) issues.push(`${path}: has too few items`); if (typeof schema.maxItems === "number" && value.length > schema.maxItems) issues.push(`${path}: has too many items`);
    const item = schema.items as Schema | undefined; if (item) value.forEach((entry, index) => issues.push(...validate(item, entry, `${path}[${index}]`))); return issues;
  }
  if (schema.type === "number" || schema.type === "integer") {
    if (typeof value !== "number" || !Number.isFinite(value) || (schema.type === "integer" && !Number.isInteger(value))) return [`${path}: must be a finite ${schema.type}`];
    if (typeof schema.minimum === "number" && value < schema.minimum) return [`${path}: must be at least ${schema.minimum}`]; if (typeof schema.maximum === "number" && value > schema.maximum) return [`${path}: must be at most ${schema.maximum}`]; return [];
  }
  if (schema.type === "boolean") return typeof value === "boolean" ? [] : [`${path}: must be true or false`];
  if (typeof value !== "string") return [`${path}: must be text`];
  if (typeof schema.minLength === "number" && value.length < schema.minLength) return [`${path}: is too short`]; if (typeof schema.maxLength === "number" && value.length > schema.maxLength) return [`${path}: is too long`]; return [];
}

function Field({ name, schema, value, change }: { name: string; schema: Schema; value: unknown; change: (value: unknown) => void }) {
  const type = String(schema.type ?? "string"); const description = typeof schema.description === "string" ? schema.description : ""; const title = typeof schema.title === "string" ? schema.title : name;
  if (type === "object") return <fieldset><legend>{title}</legend>{description && <small>{description}</small>}{Object.entries((schema.properties as Record<string, Schema>) ?? {}).map(([key, child]) => <Field key={key} name={key} schema={child} value={(value as Record<string, unknown>)?.[key]} change={(next) => change({ ...((value as Record<string, unknown>) ?? {}), [key]: next })} />)}</fieldset>;
  if (type === "array") return <label>{title}<textarea value={JSON.stringify(value ?? [], null, 2)} onChange={(event) => { try { const next = JSON.parse(event.target.value); if (Array.isArray(next) && next.length <= Number(schema.maxItems ?? 128)) change(next); } catch { /* validation is shown before submission */ } }} /><small>{description || "Bounded JSON array"}</small></label>;
  if (Array.isArray(schema.enum)) { const choices = schema.enum as Array<string | number | boolean>; return <label>{title}<select value={String(value ?? "")} onChange={(event) => { const selected = choices.find((item) => String(item) === event.target.value); change(selected); }}>{choices.map((item) => <option key={String(item)} value={String(item)}>{String(item)}</option>)}</select><small>{description}</small></label>; }
  if (type === "boolean") return <label><input type="checkbox" checked={Boolean(value)} onChange={(event) => change(event.target.checked)} /> {title}</label>;
  return <label>{title}<input type={type === "number" || type === "integer" ? "number" : "text"} step={type === "integer" ? "1" : "any"} min={schema.minimum as number | undefined} max={schema.maximum as number | undefined} value={String(value ?? "")} onChange={(event) => change(type === "number" || type === "integer" ? Number(event.target.value) : event.target.value)} /><small>{description}</small></label>;
}

export function EngineSchemaForm({ schema, onSubmit, submitting }: { schema: unknown; onSubmit: (value: Record<string, unknown>) => void; submitting?: boolean }) {
  const safe = trustedJsonSchema.safeParse(schema); const initial = useMemo(() => { const parsed = trustedJsonSchema.safeParse(schema); return parsed.success ? defaults(parsed.data as Schema) as Record<string, unknown> : {}; }, [schema]);
  const [value, setValue] = useState(initial); const [raw, setRaw] = useState(false); const [rawText, setRawText] = useState(JSON.stringify(initial, null, 2)); const [rawError, setRawError] = useState("");
  useEffect(() => { setValue(initial); setRawText(JSON.stringify(initial, null, 2)); setRawError(""); }, [initial]);
  const issues = safe.success ? [...validate(safe.data as Schema, value), ...(rawError ? [rawError] : [])] : ["This engine does not expose a trusted supported input schema."];
  function submit(event: React.FormEvent) { event.preventDefault(); if (!issues.length) onSubmit(value); }
  return <form className="stack" onSubmit={submit}>{raw ? <label>Advanced JSON<textarea value={rawText} onChange={(event) => { const text = event.target.value; setRawText(text); if (new TextEncoder().encode(text).byteLength > MAX_RAW_BYTES) return setRawError("Advanced JSON exceeds its safe size limit."); try { const next = JSON.parse(text); if (!next || typeof next !== "object" || Array.isArray(next)) throw new Error(); setValue(next as Record<string, unknown>); setRawError(""); } catch { setRawError("Advanced JSON must be a valid object."); } }} /></label> : <Field name="input" schema={safe.success ? safe.data as Schema : {}} value={value} change={(next) => setValue(next as Record<string, unknown>)} />}{issues.length > 0 && <div className="error" role="alert">{issues.join("; ")}</div>}<div className="toolbar-actions"><button type="button" className="quiet" onClick={() => setRaw(!raw)}>{raw ? "Use form" : "Advanced JSON"}</button><button type="button" className="quiet" onClick={() => { setValue(initial); setRawText(JSON.stringify(initial, null, 2)); setRawError(""); }}>Reset example</button><button disabled={Boolean(issues.length) || submitting}>{submitting ? "Submitting…" : "Create engine job"}</button></div></form>;
}
