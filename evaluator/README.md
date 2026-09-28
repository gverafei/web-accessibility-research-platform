# Evaluator process lifecycle

Axe and Lighthouse use the same measurement profiles and output contracts as
before, but each audit executes in its own supervised Node process. Lighthouse
has a 180-second outer deadline; Axe's outer deadline is its configured hard
limit plus a 10-second cleanup allowance. Buffer overflow, tool errors and
timeouts remain failures, never zero-score results.

`isolated_process.js` tracks Linux descendants by PID and `/proc` start time.
Lighthouse registers its independently detached Chromium process over private
IPC. The supervisor closes only owned process groups/descendants on success,
failure or timeout. It also cleans on worker exit rather than waiting forever
for inherited pipes. `run_lighthouse_direct.js` awaits graceful Chrome cleanup.
Both Compose configurations enable `init: true` to reap terminated orphans.

Verification:

```sh
docker compose -f docker-compose-dev.yml run --rm --no-deps evaluator npm test
docker compose -f docker-compose-dev.yml run --rm --no-deps evaluator node tests/browser_cleanup_pilot.js
```

The bounded pilot starts a local HTTP fixture, repeats three actual Axe and
Lighthouse audits, then deliberately fails and times out real Chromium workers.
Every case must return to zero browser processes. It creates no experiment
observations and makes no paid calls. Run it in a dedicated idle container.

Environment metadata records `isolated process supervision v1`. A deployment
must rebuild the evaluator image; restarting an old image is insufficient.
# Dataset evidence and eligibility gates

An optional typed `quality_policy` persists with the evaluation. Dataset
acquisitions can require original response HTML, rendered HTML and a screenshot
and explicitly exclude adult content or named out-of-scope hosts. Missing
required evidence remains an acquisition failure; the response is never
fabricated from the DOM or fetched later as if it were the original response.
HTTP error documents and verified publisher interstitials are rejected before
measurement. Legitimate sparse/login/graphical pages remain supported. These
checks do not depend on an accessibility score. They supplement manual curation,
not a claim that all potentially ineligible sites can be identified by patterns.
