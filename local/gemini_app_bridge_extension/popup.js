const status = document.querySelector('#status');
const send = (type, extra = {}) => chrome.runtime.sendMessage({ type, ...extra }, (value) => { status.textContent = JSON.stringify(value, null, 2); });
document.querySelector('#start').onclick = () => send('bridge_start', { timeout_ms: 60 * 60 * 1000 });
document.querySelector('#pause').onclick = () => send('bridge_pause');
document.querySelector('#resume').onclick = () => send('bridge_resume');
document.querySelector('#stop').onclick = () => send('bridge_stop');
document.querySelector('#import').onclick = () => send('bridge_import_visible_response', { output: document.querySelector('#output').value, visible_model_label: document.querySelector('#model').value });
chrome.runtime.sendMessage({ type: 'bridge_pending_job' }, (job) => { document.querySelector('#prompt').value = job?.prompt_text || ''; });
send('bridge_status');
