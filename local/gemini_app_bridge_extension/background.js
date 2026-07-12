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

function connectNative() {
  if (nativePort) return nativePort;
  nativePort = chrome.runtime.connectNative(NATIVE_HOST);
  nativePort.onMessage.addListener(handleNativeMessage);
  nativePort.onDisconnect.addListener(async () => {
    nativePort = null;
    await setSession({ active: false, status: "native_host_disconnected", currentJob: "" });
  });
  nativePort.postMessage({ type: "session_start", extension_id: chrome.runtime.id });
  return nativePort;
}

async function handleNativeMessage(message) {
  if (!message || message.type !== "run_job") return;
  const current = await session();
  if (!current.active || current.paused || Date.now() >= current.expiresAt) {
    nativePort?.postMessage({ type: "job_result", job_id: message.job?.job_id || "", status: "paused", safe_error: "Mystic session is not active." });
    return;
  }
  await setSession({ currentJob: message.job.job_id, status: "awaiting_manual_send", pendingJob: message.job, complianceLevel: "manual_send" });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message?.type === "bridge_status") return sendResponse(await session());
    if (message?.type === "bridge_pending_job") return sendResponse((await session()).pendingJob || null);
    if (message?.type === "bridge_import_visible_response") {
      const current = await session();
      if (!current.active || !current.pendingJob?.job_id) return sendResponse({ status: "paused", safe_error: "Start a Mystic session before importing a visible response." });
      nativePort?.postMessage({ type: "job_result", job_id: current.pendingJob.job_id, status: "ok", output: String(message.output || "").slice(0, 12000), visible_model_label: String(message.visible_model_label || "").slice(0, 120) });
      return sendResponse(await setSession({ currentJob: "", pendingJob: null, status: "ready" }));
    }
    if (message?.type === "bridge_start") {
      connectNative();
      return sendResponse(await setSession({ active: true, paused: false, expiresAt: Date.now() + message.timeout_ms, status: "ready" }));
    }
    if (message?.type === "bridge_pause") return sendResponse(await setSession({ paused: true, status: "paused" }));
    if (message?.type === "bridge_resume") return sendResponse(await setSession({ paused: false, status: "ready" }));
    if (message?.type === "bridge_stop") {
      nativePort?.postMessage({ type: "session_stop" });
      nativePort?.disconnect();
      nativePort = null;
      return sendResponse(await setSession({ active: false, paused: false, currentJob: "", status: "stopped" }));
    }
    return sendResponse({ status: "unknown_action" });
  })();
  return true;
});
