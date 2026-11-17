const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { runAxe } = require('../run_axe');
const { runLighthouseDirect } = require('../run_lighthouse_direct');

for (const engine of ['axe', 'lighthouse']) {
  test(`${engine} keeps a local input through redirect attempts and address changes`, async () => {
    let replaced = 0, assets = 0;
    const server = http.createServer((request, response) => {
      if (request.url === '/replacement') {
        replaced++;
        response.end('<h1>Incorrect replacement</h1>');
      } else if (request.url === '/asset.css') {
        assets++;
        response.setHeader('content-type', 'text/css');
        response.end('body { color: black; background: white; }');
      } else {
        response.setHeader('content-type', 'text/html');
        response.end(`<!doctype html><html lang="en"><head><title>Frozen input</title>
          <link rel="stylesheet" href="/asset.css"></head><body>
          <main><h1>Frozen input</h1><button>Continue</button></main>
          <script>setTimeout(()=>{history.replaceState({},'', '/display-address');location.href='/replacement';},100);</script></body></html>`);
      }
    });
    await new Promise(resolve => server.listen(0, '0.0.0.0', resolve));
    const url = `http://dataset-server:${server.address().port}/input.html`;
    try {
      const result = engine === 'axe'
        ? await runAxe(url, null, { runtimeConfig: { network_idle_timeout_ms: 1500,
            page_settle_delay_ms: 100, dom_stability_window_ms: 100,
            dom_stability_timeout_ms: 1000, enable_lazy_load_scroll: false } })
        : await runLighthouseDirect(url);
      const evidence = engine === 'axe' ? result.acquisition.local_replay : result.raw.localReplay;
      assert.equal(evidence.expected_document_url, url);
      assert.ok(evidence.blocked_navigations.some(item => item.url.endsWith('/replacement')));
      assert.equal(replaced, 0);
      assert.ok(assets > 0);
      if (engine === 'axe') {
        assert.match(result.html, /Frozen input/);
        assert.match(result.response_html, /Frozen input/);
        assert.equal(result.acquisition.page_title, 'Frozen input');
      } else {
        assert.equal(result.raw.mainDocumentUrl || result.raw.finalUrl, url);
        assert.match(result.raw.finalDisplayedUrl, /display-address$/);
        assert.equal(result.summary.accessibility_score, 100);
      }
    } finally {
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
  });
}

test('Axe does not score content interrupted by an early local redirect', async () => {
  const server = http.createServer((request, response) => {
    response.setHeader('content-type', 'text/html');
    response.end(`<!doctype html><html lang="en"><head><title>Interrupted</title>
      <script>location.href='/replacement';</script></head>
      <body><main><h1>Late content</h1></main></body></html>`);
  });
  await new Promise(resolve => server.listen(0, '0.0.0.0', resolve));
  try {
    const url = `http://dataset-server:${server.address().port}/input.html`;
    await assert.rejects(runAxe(url, null, { runtimeConfig: {
      page_load_timeout_ms: 1500, axe_hard_timeout_ms: 10000,
      network_idle_timeout_ms: 100, page_settle_delay_ms: 100,
      dom_stability_window_ms: 100, dom_stability_timeout_ms: 300,
      enable_lazy_load_scroll: false
    } }), /Local replay|Timeout/);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});

test('page console hooks cannot interrupt Axe preload error handling', async () => {
  const server = http.createServer((request, response) => {
    if (request.url === '/pending.mp3') {
      response.writeHead(200, { 'content-type': 'audio/mpeg' });
      response.flushHeaders();
      return;
    }
    response.setHeader('content-type', 'text/html');
    response.end(`<!doctype html><html lang="en"><head><title>Console hook</title>
      <script>console.warn=function brokenPageHook(){return console.warn.apply(console,arguments);};</script>
      </head><body><main><h1>Console hook</h1><p>Preserved content</p>
      <audio autoplay src="/pending.mp3"></audio></main></body></html>`);
  });
  await new Promise(resolve => server.listen(0, '0.0.0.0', resolve));
  try {
    const result = await runAxe(`http://dataset-server:${server.address().port}/input.html`, null,
      { standard: 'wcag22aa', runtimeConfig: {
        page_load_timeout_ms: 3000, axe_hard_timeout_ms: 25000,
        network_idle_timeout_ms: 100, page_settle_delay_ms: 100,
        dom_stability_window_ms: 100, dom_stability_timeout_ms: 300,
        enable_lazy_load_scroll: false
      } });
    assert.match(result.response_html, /brokenPageHook/);
    assert.equal(result.load_metadata.axe_execution_context.version, 'native-console-v1');
    assert.ok(result.raw.incomplete.some(rule => rule.id === 'no-autoplay-audio'));
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
