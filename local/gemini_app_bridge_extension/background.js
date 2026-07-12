const NATIVE_HOST = "com.mystic.gemini_app_bridge";
const SESSION_KEY = "mysticGeminiBridgeSession";
let nativePort = null;

async function session() {
  const data = await chrome.storage.session.get(SESSION_KEY);
  return data[SESSION_KEY] || { active: false, paused: false, expiresAt: 0, currentJob: "", queueCount: 0, status: "stopped" };
}
async function setSession(patch) {
  const next = { ...(await session()), ...patch };
  await chrome.storage.session.set({ [SESSION_KEY]: next });
  return next;
}
function sendNative(message) { nativePort?.postMessage(message); }
function connectNative() {
  if (nativePort) return nativePort;
  nativePort = chrome.runtime.connectNative(NATIVE_HOST);
  nativePort.onMessage.addListener(handleNativeMessage);
  nativePort.onDisconnect.addListener(async () => { nativePort = null; await setSession({ active: false, status: "native_host_disconnected", currentJob: "" }); });
  sendNative({ operation: "relay_status", extension_id: chrome.runtime.id });
  return nativePort;
}
async function handleNativeMessage(message) {
  if (!message || typeof message !== "object") return;
  if (message.type === "run_job") {
    const current = await session();
    if (!current.active || current.paused || Date.now() >= current.expiresAt) {
      sendNative({ operation: "job_cancel", job_id: message.job?.job_id || "", safe_error: "Mystic session is not active." });
      return;
    }
    await setSession({ currentJob: message.job.job_id, currentRun: message.job.run_id || "", sessionId: message.job.session_id || "", pendingJob: message.job, queueCount: Number(message.queue_count || 0), status: "awaiting_user_submission", complianceLevel: "manual_send" });
    return;
  }
  if (message.type === "relay_state") await setSession(message.state || {});
}
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message?.type === "bridge_status") return sendResponse(await session());
    if (message?.type === "bridge_pending_job") return sendResponse((await session()).pendingJob || null);
    if (message?.type === "bridge_refresh_queue") { sendNative({ operation: "queue_count" }); sendNative({ operation: "job_get" }); return sendResponse(await session()); }
    if (message?.type === "bridge_import_visible_response") {
      const current = await session();
      const output = String(message.output || "").replace(/\r\n/g, "\n").trim();
      if (!current.active || !current.pendingJob?.job_id) return sendResponse({ status: "browser_session_not_started", safe_error: "Start a Mystic session before importing a visible response." });
      if (!output) return sendResponse({ status: "invalid_response", safe_error: "Paste a visible Gemini response before submitting." });
      if (output.length > 120000) return sendResponse({ status: "response_too_large", safe_error: "The visible response exceeds the 120,000 character relay limit." });
      sendNative({ operation: "response_submit", job_id: current.pendingJob.job_id, response_text: output, visible_model_label: String(message.visible_model_label || "").trim().slice(0, 120) });
      return sendResponse(await setSession({ status: "awaiting_upload" }));
    }
    if (message?.type === "bridge_start") { connectNative(); sendNative({ operation: "relay_start", timeout_ms: message.timeout_ms }); return sendResponse(await setSession({ active: true, paused: false, expiresAt: Date.now() + message.timeout_ms, status: "ready" })); }
    if (message?.type === "bridge_pause") { sendNative({ operation: "relay_pause" }); return sendResponse(await setSession({ paused: true, status: "paused" })); }
    if (message?.type === "bridge_resume") { sendNative({ operation: "relay_resume" }); return sendResponse(await setSession({ paused: false, status: "ready" })); }
    if (message?.type === "bridge_cancel_job") { const current = await session(); sendNative({ operation: "job_cancel", job_id: current.pendingJob?.job_id || "" }); return sendResponse(await setSession({ currentJob: "", pendingJob: null, status: "cancelled" })); }
    if (message?.type === "bridge_stop") { sendNative({ operation: "relay_stop" }); nativePort?.disconnect(); nativePort = null; return sendResponse(await setSession({ active: false, paused: false, currentJob: "", pendingJob: null, status: "stopped" })); }
    return sendResponse({ status: "unknown_action" });
  })();
  return true;
});
