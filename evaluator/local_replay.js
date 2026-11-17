// Preserve the supplied research document while allowing its subresources.
function isLocalDatasetUrl(value) {
  try { return new URL(value).hostname.toLowerCase() === 'dataset-server'; }
  catch { return false; }
}

async function protectLocalReplay(context, url) {
  if (!isLocalDatasetUrl(url)) return null;
  const expected = new URL(url); expected.hash = '';
  const evidence = { expected_document_url: expected.href, blocked_navigations: [] };
  await context.route('**/*', async route => {
    const request = route.request();
    const destination = new URL(request.url()); destination.hash = '';
    if (request.isNavigationRequest() && !request.frame().parentFrame()
        && destination.href !== expected.href) {
      evidence.blocked_navigations.push({ url: request.url(), method: request.method() });
      await route.fulfill({ status: 204, body: '', headers: { 'cache-control': 'no-store' } });
      return;
    }
    await route.fallback();
  });
  return evidence;
}

module.exports = { isLocalDatasetUrl, protectLocalReplay };
