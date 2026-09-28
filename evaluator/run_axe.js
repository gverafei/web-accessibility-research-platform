const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const fs = require("fs");
const { pageRejection } = require('./acquisition_quality');

const AXE_PROFILES = {
  wcag20a: ["wcag2a"],
  wcag20aa: ["wcag2a", "wcag2aa"],
  wcag21a: ["wcag2a", "wcag21a"],
  wcag21aa: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
  wcag22a: ["wcag2a", "wcag21a", "wcag22a"],
  wcag22aa: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]
};

function positiveInteger(name, fallback) {
  const value = Number.parseInt(process.env[name] || "", 10);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}

function loadPolicy(overrides = {}) {
  const configuredInteger = (key, envName, fallback) => {
    const value = Number.parseInt(overrides[key] ?? process.env[envName] ?? "", 10);
    return Number.isFinite(value) && value >= 0 ? value : fallback;
  };
  return {
    page_load_timeout_ms: configuredInteger("page_load_timeout_ms", "PAGE_LOAD_TIMEOUT_MS", 60000),
    axe_hard_timeout_ms: configuredInteger("axe_hard_timeout_ms", "AXE_HARD_TIMEOUT_MS", 240000),
    network_idle_timeout_ms: configuredInteger("network_idle_timeout_ms", "NETWORK_IDLE_TIMEOUT_MS", 15000),
    page_settle_delay_ms: configuredInteger("page_settle_delay_ms", "PAGE_SETTLE_DELAY_MS", 2000),
    dom_stability_window_ms: configuredInteger("dom_stability_window_ms", "DOM_STABILITY_WINDOW_MS", 1500),
    dom_stability_timeout_ms: configuredInteger("dom_stability_timeout_ms", "DOM_STABILITY_TIMEOUT_MS", 10000),
    lazy_load_scroll: String(overrides.enable_lazy_load_scroll ?? process.env.ENABLE_LAZY_LOAD_SCROLL ?? "true").toLowerCase() === "true",
    interaction_activation: true,
    scroll_step_px: configuredInteger("scroll_step_px", "SCROLL_STEP_PX", 700),
    scroll_delay_ms: configuredInteger("scroll_delay_ms", "SCROLL_DELAY_MS", 400),
    max_scroll_steps: configuredInteger("max_scroll_steps", "MAX_SCROLL_STEPS", 30)
  };
}

const MOVED_MARKERS = ["we have moved", "site has moved", "moved permanently"];
const SECURITY_MARKERS = [
  "security verification", "verify you are human", "checking your browser",
  "just a moment", "attention required", "captcha", "access denied"
];

function isMovedNotice(text) {
  const normalized = String(text || "").toLowerCase();
  return MOVED_MARKERS.some(marker => normalized.includes(marker));
}

function isLocalDatasetUrl(url) {
  try {
    return new URL(url).hostname.toLowerCase() === "dataset-server";
  } catch {
    return false;
  }
}

function isSecurityChallenge(url, text) {
  // Uploaded HTML is already the research artifact. Words such as
  // "verification" or "access denied" may legitimately occur in its page
  // content and do not represent a publisher blocking acquisition.
  if (isLocalDatasetUrl(url)) return false;
  const normalized = String(text || "").toLowerCase();
  let path = "";
  try {
    const parsed = new URL(url);
    path = `${parsed.pathname} ${parsed.search}`.toLowerCase();
  } catch {}
  const challengePath = ["verify", "verification", "captcha", "challenge", "blocked"]
    .some(marker => path.includes(marker));
  return challengePath || SECURITY_MARKERS.some(marker => normalized.includes(marker));
}

function acquisitionRejection(metrics, pageTitle = "") {
  const domNodes = Number(metrics?.dom_nodes || 0);
  const visibleTextLength = Number(metrics?.visible_text_length || 0);
  const sameDomainLinks = Number(metrics?.same_domain_links || 0);
  if (domNodes < 10) {
    return "Acquisition excluded: the rendered page contained fewer than 10 HTML elements.";
  }
  if (!String(pageTitle || "").trim() && domNodes <= 20 && visibleTextLength < 80) {
    return "Acquisition excluded: the publisher returned a blank or minimal response.";
  }
  if (sameDomainLinks > 5000) {
    return "Acquisition excluded: the page contained more than 5,000 same-domain links.";
  }
  return null;
}

async function activateLazyContent(page, policy) {
  if (!policy.lazy_load_scroll) return 0;

  // Some lazy loaders and entrance-animation libraries do not initialize from
  // programmatic window.scrollBy() calls alone. Generate trusted pointer and
  // wheel input, similar to a researcher manually exploring the page.
  await page.mouse.move(2, 2);
  await page.mouse.move(720, 450, { steps: 4 });

  let steps = 0;
  let previousHeight = 0;
  while (steps < policy.max_scroll_steps) {
    await page.mouse.move(
      700 + (steps % 2) * 40,
      430 + (steps % 3) * 25,
      { steps: 2 }
    );
    await page.mouse.wheel(0, policy.scroll_step_px);
    await page.waitForTimeout(policy.scroll_delay_ms);

    const state = await page.evaluate(() => ({
        position: window.scrollY + window.innerHeight,
        height: document.documentElement.scrollHeight
      }));
    steps += 1;

    if (state.position >= state.height && state.height === previousHeight) break;
    previousHeight = state.height;
  }

  // Traverse upward as well: several IntersectionObserver animations only
  // finish after an element has entered and then left the viewport.
  for (let returnStep = 0; returnStep < steps; returnStep += 1) {
    const atTop = await page.evaluate(() => window.scrollY <= 0);
    if (atTop) break;
    await page.mouse.move(
      740 - (returnStep % 2) * 40,
      470 - (returnStep % 3) * 25,
      { steps: 2 }
    );
    await page.mouse.wheel(0, -policy.scroll_step_px);
    await page.waitForTimeout(policy.scroll_delay_ms);
  }

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForTimeout(Math.max(500, policy.scroll_delay_ms * 2));
  return steps;
}

async function settleLazyResources(page, policy) {
  try {
    await page.waitForLoadState("networkidle", {
      timeout: Math.min(10000, policy.network_idle_timeout_ms)
    });
  } catch {
    // Long-lived analytics connections must not prevent evaluation.
  }
  await page.evaluate(async () => {
    const images = [...document.images].filter(image => image.currentSrc || image.src);
    const decoded = Promise.all(images.map(async image => {
      try {
        if (!image.complete) {
          await new Promise(resolve => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });
          });
        }
        if (image.decode) await image.decode().catch(() => {});
      } catch {}
    }));
    await Promise.race([decoded, new Promise(resolve => setTimeout(resolve, 8000))]);
  });
}

async function waitForDomStability(page, policy) {
  const startedAt = Date.now();
  let stableSince = Date.now();
  let previousSignature = null;

  while (Date.now() - startedAt < policy.dom_stability_timeout_ms) {
    const signature = await page.evaluate(() =>
      `${document.querySelectorAll("*").length}:${document.documentElement.outerHTML.length}`
    );
    if (signature === previousSignature) {
      if (Date.now() - stableSince >= policy.dom_stability_window_ms) {
        return { stable: true, wait_ms: Date.now() - startedAt };
      }
    } else {
      previousSignature = signature;
      stableSince = Date.now();
    }
    await page.waitForTimeout(Math.min(250, policy.dom_stability_window_ms || 250));
  }
  return { stable: false, wait_ms: Date.now() - startedAt };
}

async function extractHtmlMetrics(page) {
  return await page.evaluate(() => {
    const getLang = () => document.documentElement.getAttribute("lang") || "";
    const currentHost = location.hostname.replace(/^www\./, "").toLowerCase();
    const links = [...document.querySelectorAll("a[href]")];
    const sameDomainLinks = links.filter(link => {
      try { return new URL(link.href, location.href).hostname.replace(/^www\./, "").toLowerCase() === currentHost; }
      catch { return false; }
    }).length;
    const ariaAttributes = [...document.querySelectorAll("*")].reduce((total, element) =>
      total + [...element.attributes].filter(attribute => attribute.name.startsWith("aria-")).length, 0);
    const skipLinks = links.filter(link => {
      const href = link.getAttribute("href") || "";
      return href.startsWith("#") && href.length > 1;
    });

    return {
      html_size: document.documentElement.outerHTML.length,
      dom_nodes: document.querySelectorAll("*").length,
      images: document.querySelectorAll("img").length,
      images_without_alt: document.querySelectorAll("img:not([alt])").length,
      links: links.length,
      same_domain_links: sameDomainLinks,
      buttons: document.querySelectorAll("button").length,
      forms: document.querySelectorAll("form").length,
      inputs: document.querySelectorAll("input, select, textarea").length,
      headings: document.querySelectorAll("h1, h2, h3, h4, h5, h6").length,
      h1_count: document.querySelectorAll("h1").length,
      language_declared: getLang(),
      visible_text_length: (document.body?.innerText || "").trim().length,
      aria_attributes: ariaAttributes,
      uses_aria: ariaAttributes > 0 || document.querySelector("[role]") !== null,
      skip_links: skipLinks.length,
      broken_skip_links: skipLinks.filter(link => {
        const id = decodeURIComponent((link.getAttribute("href") || "").slice(1));
        return id && !document.getElementById(id) && !document.querySelector(`[name="${CSS.escape(id)}"]`);
      }).length,
      ambiguous_links: links.filter(link => {
        const imageAlt = [...link.querySelectorAll("img")].map(image => image.alt || "").join(" ");
        const text = `${link.innerText || ""} ${link.getAttribute("aria-label") || ""} ${imageAlt}`
          .trim().replace(/\s+/g, " ").toLowerCase();
        const exact = new Set(["here", "more", "more...", "details", "more details", "link",
          "this page", "continue", "continue reading", "read more", "button"]);
        return text.includes("click here") || text.includes("click") || exact.has(text);
      }).length,
      doctype: document.doctype ? `<!DOCTYPE ${document.doctype.name}>` : "",
      valid_html5_doctype: Boolean(document.doctype && document.doctype.name.toLowerCase() === "html"),
      has_main_landmark: document.querySelector("main, [role='main']") !== null,
      has_nav_landmark: document.querySelector("nav, [role='navigation']") !== null,
      has_header_landmark: document.querySelector("header, [role='banner']") !== null,
      has_footer_landmark: document.querySelector("footer, [role='contentinfo']") !== null
    };
  });
}

function summarizeAxeResults(results, standard, includeBestPractices, tags) {
  const countNodes = entries => entries.reduce((total, entry) => total + entry.nodes.length, 0);
  const nodesByImpact = (entries, impact) => countNodes(entries.filter(entry => entry.impact === impact));
  const rulesByImpact = (entries, impact) => entries.filter(entry => entry.impact === impact).length;
  const bestPracticeViolations = results.violations.filter(entry =>
    Array.isArray(entry.tags) && entry.tags.includes("best-practice")
  );
  const wcagViolations = results.violations.filter(entry => !bestPracticeViolations.includes(entry));
  const bestPracticeIncomplete = results.incomplete.filter(entry =>
    Array.isArray(entry.tags) && entry.tags.includes("best-practice")
  );
  const wcagIncomplete = results.incomplete.filter(entry => !bestPracticeIncomplete.includes(entry));

  return {
    violations: countNodes(results.violations),
    critical: nodesByImpact(results.violations, "critical"),
    serious: nodesByImpact(results.violations, "serious"),
    moderate: nodesByImpact(results.violations, "moderate"),
    minor: nodesByImpact(results.violations, "minor"),
    failed_rules: results.violations.length,
    critical_rules: rulesByImpact(results.violations, "critical"),
    serious_rules: rulesByImpact(results.violations, "serious"),
    moderate_rules: rulesByImpact(results.violations, "moderate"),
    minor_rules: rulesByImpact(results.violations, "minor"),
    needs_review: countNodes(results.incomplete),
    needs_review_rules: results.incomplete.length,
    best_practice_issues: countNodes(bestPracticeViolations),
    best_practice_rules: bestPracticeViolations.length,
    wcag_violations: countNodes(wcagViolations),
    wcag_critical: nodesByImpact(wcagViolations, "critical"),
    wcag_serious: nodesByImpact(wcagViolations, "serious"),
    wcag_moderate: nodesByImpact(wcagViolations, "moderate"),
    wcag_minor: nodesByImpact(wcagViolations, "minor"),
    wcag_failed_rules: wcagViolations.length,
    wcag_needs_review: countNodes(wcagIncomplete),
    standard,
    include_best_practices: includeBestPractices,
    tags
  };
}

async function runAxe(url, screenshotPath = null, options = {}) {
  const policy = loadPolicy(options.runtimeConfig || {});
  const standard = Object.hasOwn(AXE_PROFILES, options.standard) ? options.standard : "wcag22aa";
  const includeBestPractices = options.includeBestPractices === true;
  const browser = await chromium.launch({
    headless: true,
    executablePath: "/usr/bin/chromium",
    args: ["--no-sandbox", "--disable-dev-shm-usage"]
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();
  let hardTimedOut = false;
  const hardTimeout = setTimeout(() => {
    hardTimedOut = true;
    // Most Playwright operations reject when their browser is closed. A
    // whole-page limit prevents one hostile or pathological page from holding
    // the single-URL worker for the HTTP client's 15-minute timeout.
    browser.close().catch(() => {});
  }, policy.axe_hard_timeout_ms);

  try {
    const readHtmlResponse = async response => {
      try {
        if (!response) return null;
        // Some otherwise valid home pages omit or misdeclare Content-Type.
        // Playwright has already committed this response as the main document,
        // so retain any non-empty textual body and validate it against the
        // rendered HTML document below instead of trusting the header alone.
        const body = await response.text();
        if (body && body.trim()) return body;
      } catch {
        // A navigation can complete even when Chromium cannot retain its body.
      }
      return null;
    };
    // Retain a bounded main-document network buffer. Heavy dynamic pages can
    // otherwise evict the original body before Playwright reads it. Never
    // fabricate a response from the rendered DOM or a second HTTP request.
    const network = await context.newCDPSession(page);
    await network.send('Network.enable', {
      maxTotalBufferSize: 200 * 1024 * 1024,
      maxResourceBufferSize: 100 * 1024 * 1024
    });
    let navigationResponse = await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: policy.page_load_timeout_ms
    });
    // Read the main-document body before scrolling, stabilization and Axe can
    // evict it from Chromium's network cache. The rendered DOM is stored later.
    let responseHtml = await readHtmlResponse(navigationResponse);

    const stabilizePage = async () => {
      let networkIdleReached = true;
      try {
        await page.waitForLoadState("networkidle", {
          timeout: policy.network_idle_timeout_ms
        });
      } catch {
        networkIdleReached = false;
      }
      const scrollSteps = await activateLazyContent(page, policy);
      await settleLazyResources(page, policy);
      const domStability = await waitForDomStability(page, policy);
      await page.waitForTimeout(policy.page_settle_delay_ms);
      return { networkIdleReached, scrollSteps, domStability };
    };

    let stabilization = await stabilizePage();
    let pageTitle = await page.title().catch(() => "");
    let bodyText = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
    let reviewText = `${pageTitle}\n${bodyText.slice(0, 4000)}`.toLowerCase();
    const localDataset = isLocalDatasetUrl(url);
    if (!localDataset && isMovedNotice(reviewText)) {
      const relocationUrl = await page.locator("a[href]").evaluateAll((links, currentUrl) => {
        const currentHost = new URL(currentUrl).hostname.replace(/^www\./, "");
        const candidates = links.map(link => {
          try {
            const target = new URL(link.href, currentUrl);
            const targetHost = target.hostname.replace(/^www\./, "");
            return { href: target.href, external: targetHost !== currentHost, text: (link.textContent || "").trim() };
          } catch { return null; }
        }).filter(Boolean).filter(item => item.href.startsWith("http"));
        return (candidates.find(item => item.external && !/privacy|terms|contact/i.test(item.text)) || candidates.find(item => item.external))?.href || null;
      }, page.url()).catch(() => null);
      if (relocationUrl) {
        navigationResponse = await page.goto(relocationUrl, {
          waitUntil: "domcontentloaded",
          timeout: policy.page_load_timeout_ms
        });
        responseHtml = await readHtmlResponse(navigationResponse);
        stabilization = await stabilizePage();
        pageTitle = await page.title().catch(() => "");
        bodyText = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
        reviewText = `${pageTitle}\n${bodyText.slice(0, 4000)}`.toLowerCase();
      }
    }

    if (!localDataset && isSecurityChallenge(page.url(), reviewText)) {
      throw new Error("Acquisition blocked by a security challenge; the publisher page was not evaluated.");
    }
    if (!localDataset) {
      const rejection = pageRejection({url: page.url(), title: pageTitle,
        body: bodyText, httpStatus: navigationResponse?.status() || 200}, options.qualityPolicy);
      if (rejection) throw new Error(rejection);
    }

    const capturedUrl = page.url();
    const acquisitionSignals = [];
    if (!responseHtml) acquisitionSignals.push('original_response_missing');
    const requestedHost = new URL(url).hostname.replace(/^www\./, "");
    const capturedHost = new URL(capturedUrl).hostname.replace(/^www\./, "");
    if (requestedHost !== capturedHost) acquisitionSignals.push("cross_domain_redirect");

    let screenshotMode = null;
    if (screenshotPath) {
      const writeScreenshot = async (fullPage, quality) => {
        const image = await page.screenshot({
          type: "jpeg",
          quality,
          fullPage,
          animations: "disabled"
        });
        if (!image || image.length === 0) return false;
        fs.writeFileSync(screenshotPath, image);
        return fs.statSync(screenshotPath).size > 0;
      };

      try {
        if (await writeScreenshot(true, 76)) screenshotMode = "full_page";
      } catch {
        // Some very tall archived pages cannot be captured as one bitmap.
      }

      if (!screenshotMode) {
        try {
          if (await writeScreenshot(false, 78)) screenshotMode = "viewport_fallback";
        } catch {
          // Screenshot evidence is optional; Axe and Lighthouse remain usable.
        }
      }

      if (!screenshotMode) {
        try { fs.unlinkSync(screenshotPath); } catch {}
      }
    }

    const html = await page.content();
    const resourceQuality = await page.evaluate(() => ({
      images_total: document.images.length,
      broken_image_urls: [...document.images].filter(image => image.complete && image.naturalWidth === 0 && (image.currentSrc || image.src)).map(image => image.currentSrc || image.src),
      pending_image_urls: [...document.images].filter(image => !image.complete).map(image => image.currentSrc || image.src),
      scroll_height: document.documentElement.scrollHeight,
      iframe_count: document.querySelectorAll('iframe').length
    }));
    const htmlMetrics = await extractHtmlMetrics(page);
    const rejection = localDataset ? null : acquisitionRejection(htmlMetrics, pageTitle);
    if (rejection) throw new Error(rejection);
    const tags = [...AXE_PROFILES[standard]];
    if (!tags.includes("best-practice")) tags.push("best-practice");
    const results = await new AxeBuilder({ page }).withTags(tags).analyze();

    // Diagnostic evidence only: do not alter Axe findings or its score. Nested
    // frame/shadow targets remain explicitly unresolved instead of being guessed.
    for (const violation of results.violations || []) {
      for (const node of (violation.nodes || []).slice(0, 12)) {
        if (!Array.isArray(node.target) || node.target.length !== 1 || typeof node.target[0] !== 'string') continue;
        const diagnostic = await page.evaluate(selector => {
          let element;
          try { element = document.querySelector(selector); } catch { return null; }
          if (!element) return null;
          const styles = target => {
            const css = getComputedStyle(target);
            return { color: css.color, background: css.backgroundColor, opacity: css.opacity,
              display: css.display, visibility: css.visibility, font_size: css.fontSize };
          };
          const ancestors = [];
          for (let parent = element.parentElement; parent && ancestors.length < 4; parent = parent.parentElement) {
            ancestors.push({ element: parent.tagName.toLowerCase(), id: parent.id, ...styles(parent) });
          }
          return { computed_style: styles(element), ancestor_styles: ancestors };
        }, node.target[0]).catch(() => null);
        if (diagnostic) Object.assign(node, diagnostic);
      }
    }

    const summary = summarizeAxeResults(results, standard, includeBestPractices, tags);
    if (summary.violations === 0) acquisitionSignals.push("zero_axe_issues");
    if (!screenshotMode) acquisitionSignals.push("screenshot_missing");

    return {
      summary,
      html,
      response_html: responseHtml,
      html_metrics: htmlMetrics,
      load_metadata: {
        policy,
        network_idle_reached: stabilization.networkIdleReached,
        scroll_steps: stabilization.scrollSteps,
        dom_stable: stabilization.domStability.stable,
        dom_stability_wait_ms: stabilization.domStability.wait_ms,
        resource_quality: resourceQuality
      },
      screenshot_path: screenshotMode ? screenshotPath : null,
      screenshot_mode: screenshotMode,
      acquisition: {
        captured_url: capturedUrl,
        page_title: pageTitle,
        signals: acquisitionSignals
      },
      raw: results
    };

  } catch (error) {
    if (hardTimedOut) {
      throw new Error(`Axe hard timeout after ${policy.axe_hard_timeout_ms} ms`, { cause: error });
    }
    throw error;
  } finally {
    clearTimeout(hardTimeout);
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

module.exports = {
  AXE_PROFILES, acquisitionRejection, activateLazyContent, isLocalDatasetUrl, isMovedNotice, isSecurityChallenge,
  loadPolicy, runAxe, settleLazyResources, summarizeAxeResults, waitForDomStability
};
