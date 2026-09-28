chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({openPanelOnActionClick: true});
});

const API = 'http://localhost/api/browser-extension';
const TERMINAL = new Set(['accepted', 'completed_with_warnings', 'failed', 'metrics_not_achieved', 'review_not_achieved']);
let checking = false;

async function finishRequest(requestId) {
  if (checking) return;
  checking = true;
  try {
    const state = await chrome.storage.local.get({activeRequestId:null, runTabId:null, runUrl:'', runConfig:null, locale:'es'});
    if (!state.activeRequestId || Number(state.activeRequestId) !== Number(requestId)) return;
    const response = await fetch(`${API}/requests/${requestId}`);
    const data = await response.json();
    if (!response.ok || !TERMINAL.has(data.status)) return;
    let message = data.message || (state.locale === 'es' ? 'La remediación terminó.' : 'The remediation finished.');
    if (data.candidate_url && state.runTabId !== null) {
      try {
        const candidate = await fetch(data.candidate_url);
        if (!candidate.ok) throw new Error(`HTTP ${candidate.status}`);
        const html = await candidate.text();
        await chrome.scripting.executeScript({target:{tabId:state.runTabId},func:documentHtml=>{document.open();document.write(documentHtml);document.close()},args:[html]});
        message = state.locale === 'es' ? 'La versión accesible se aplicó en la pestaña original.' : 'The accessible version was applied to the original tab.';
        if (data.status === 'completed_with_warnings') message += state.locale === 'es' ? ' No se alcanzaron todos los umbrales configurados; consulta los scores del resultado.' : ' Not all configured targets were reached; check the result scores.';
      } catch (error) {
        message = state.locale === 'es' ? `La remediación terminó, pero no se pudo aplicar: ${error.message}` : `The remediation finished, but could not be applied: ${error.message}`;
      }
    }
    const completion = {url:state.runUrl, message, status:data.status, config:state.runConfig, finishedAt:Date.now()};
    await chrome.storage.local.set({lastCompletion:completion, completedRequestId:requestId});
    await chrome.storage.local.remove(['activeRequestId','runTabId','runUrl']);
    await chrome.alarms.clear('warp-remediation-poll');
    chrome.notifications.create(`warp-${completion.finishedAt}`,{type:'basic',iconUrl:'icons/warp-icon-128.png',title:state.locale === 'es' ? 'Remediación terminada' : 'Remediation finished',message});
  } catch (_) {
    // The next alarm retries transient local-backend or browser failures.
  } finally {
    checking = false;
  }
}

async function trackActiveRequest() {
  const {activeRequestId} = await chrome.storage.local.get({activeRequestId:null});
  if (!activeRequestId) return;
  await chrome.alarms.create('warp-remediation-poll',{periodInMinutes:.5});
  await finishRequest(activeRequestId);
}

chrome.runtime.onMessage.addListener(message => {
  if (message?.type === 'TRACK_REMEDIATION') trackActiveRequest();
  if (message?.type === 'FINISH_REMEDIATION') finishRequest(message.requestId);
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'warp-remediation-poll') trackActiveRequest(); });
chrome.runtime.onStartup.addListener(trackActiveRequest);
trackActiveRequest();
