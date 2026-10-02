importScripts('results.js', 'injection.js');
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
    const state = await chrome.storage.local.get({activeRequestId:null, runTabId:null, runUrl:'', runConfig:null, runReused:false, candidateView:null, locale:'es'});
    if (!state.activeRequestId || Number(state.activeRequestId) !== Number(requestId)) return;
    const response = await fetch(`${API}/requests/${requestId}`);
    const data = await response.json();
    if (!response.ok || !TERMINAL.has(data.status)) return;
    let viewUrl = null;
    let message = data.message || (state.locale === 'es' ? 'La remediación terminó.' : 'The remediation finished.');
    if (data.candidate_url && state.runTabId !== null) {
      try {
        const target = await chrome.tabs.get(state.runTabId);
        if (new URL(target.url).origin !== new URL(state.runUrl).origin) {
          throw new Error('The original tab changed origin; reopen the source page before applying its candidate.');
        }
        const candidateUrl = new URL(data.candidate_url);
        if (candidateUrl.href !== `${API}/requests/${requestId}/candidate`) {
          throw new Error('No safe local candidate URL is available.');
        }
        const candidate = await fetch(candidateUrl.href);
        if (!candidate.ok) throw new Error(`Candidate HTTP ${candidate.status}`);
        const html = await candidate.text();
        await chrome.storage.local.set({candidateView:{tabId:state.runTabId,url:state.runUrl,viewUrl:target.url,mode:'direct'}});
        await chrome.scripting.executeScript({target:{tabId:state.runTabId},world:'MAIN',func:extensionInjection.applyCandidate,args:[html,state.runUrl]});
        viewUrl = target.url;
        message = state.locale === 'es'
          ? 'El candidato guardado se aplicó directamente en la pestaña original, conservando su dirección y origen. El sitio remoto no se modificó.'
          : 'The stored candidate was applied directly to the original tab, keeping its address and origin. The remote website was not modified.';
        if (data.status === 'completed_with_warnings') message += state.locale === 'es' ? ' No se alcanzaron todos los umbrales configurados; consulta los scores del resultado.' : ' Not all configured targets were reached; check the result scores.';
      } catch (error) {
        message = state.locale === 'es' ? `La remediación terminó, pero no se pudo aplicar: ${error.message}` : `The remediation finished, but could not be applied: ${error.message}`;
      }
    }
    if (state.runReused) message = (state.locale === 'es'
      ? 'Resultado guardado recuperado. ' : 'Stored result recovered. ') + message;
    const completion = {url:state.runUrl, tabId:state.runTabId, viewUrl, message, status:data.status, config:state.runConfig, reused:state.runReused,
      ...extensionResults.evidence(data), finishedAt:Date.now()};
    await chrome.storage.local.set({lastCompletion:completion, completedRequestId:requestId});
    await chrome.storage.local.remove(['activeRequestId','runTabId','runUrl','runReused']);
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
