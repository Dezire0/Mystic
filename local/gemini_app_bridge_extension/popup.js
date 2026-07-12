const status = document.querySelector('#status');
const byId = (id) => document.querySelector(`#${id}`);
function renderState(value = {}) {
  const job = value.pendingJob || null;
  byId('prompt').value = job?.prompt_text || '';
  byId('session-id').textContent = job?.session_id || value.sessionId || '-'; byId('run-id').textContent = job?.run_id || value.currentRun || '-';
  byId('round-role').textContent = job ? `${job.round || '-'} / ${job.agent_role || '-'}` : '-'; byId('queue-count').textContent = String(value.queueCount || 0);
  status.textContent = JSON.stringify({ status: value.status || 'unknown', compliance_mode: 'manual_send', safe_error: value.safe_error || '' }, null, 2);
}
function send(type, extra = {}) { chrome.runtime.sendMessage({ type, ...extra }, (value) => renderState(value || {})); }
byId('start').onclick = () => send('bridge_start', { timeout_ms: 60 * 60 * 1000 }); byId('pause').onclick = () => send('bridge_pause'); byId('resume').onclick = () => send('bridge_resume'); byId('stop').onclick = () => send('bridge_stop'); byId('refresh').onclick = () => send('bridge_refresh_queue'); byId('cancel').onclick = () => send('bridge_cancel_job');
byId('copy').onclick = async () => { await navigator.clipboard.writeText(byId('prompt').value); status.textContent = 'Prompt copied. Paste and send it manually in Gemini.'; };
byId('open-gemini').onclick = () => chrome.tabs.create({ url: 'https://gemini.google.com/' });
byId('preview').onclick = () => { const preview = byId('preview-output'); preview.textContent = byId('output').value; preview.hidden = false; };
byId('import').onclick = () => send('bridge_import_visible_response', { output: byId('output').value, visible_model_label: byId('model').value });
chrome.runtime.sendMessage({ type: 'bridge_status' }, renderState);
