# Adaptive RAG-ACT retrieval

ACT stands for **Accessibility Conformance Testing**. W3C ACT Rules describe accessibility checks and their test cases. RAG means **retrieval-augmented generation**: retrieving relevant examples and adding them to a model's context. **RAG-ACT** is the platform's consistent name for retrieval-augmented generation using ACT Rules; it is not a separate W3C standard. It supplies examples to later refinements, under the researcher's control.

Consult the [W3C ACT Rules catalogue](https://www.w3.org/WAI/standards-guidelines/act/rules/),
the [WCAG 2.2 standard](https://www.w3.org/TR/WCAG22/) and
[Understanding WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/)
for the rules, requirements and explanatory guidance. ACT Rules are informative
testing guidance, not an additional set of WCAG conformance requirements.

## What the switch means

In the web remediation form, RAG-ACT grounding is enabled by default. The extension exposes its own optional evidence switch. Enabled means retrieval is **armed**; it does not mean examples were used in every iteration. An unavailable or uninitialized corpus has a muted card; a usable corpus has the orange evidence accent.

The first generation is unchanged by adaptive RAG-ACT retrieval. A later iteration can activate it when actual Axe/Lighthouse findings justify refinement. With the switch off, no RAG-ACT retrieval is used for that run. Zero-shot execution disables it.

The trace records enabled, activated, retrieved and supplied evidence separately. Compare actual use, not just the UI switch, when studying RAG.

## Corpus and provenance

The synchronization routine downloads the upstream W3C ACT repository snapshot and loads approved passed/failed HTML examples. It retains rule/testcase identifiers, source URLs, snapshot digest, retrieval time and license provenance. See the [W3C ACT Rules overview](https://www.w3.org/WAI/standards-guidelines/act/rules/). A separate supplement contains platform-authored pairs grounded in primary guidance; those are explicitly **not official ACT testcases**.

The iteration trace distinguishes W3C material from complementary guidance and links each supplied example to its source.

### Browse saved examples

Open **RAG-ACT** near the bottom of the main sidebar. Synchronization controls
and the saved-example browser share this page; neither is inside Configuration.
Search by rule name, example title, rule/test case ID or WCAG requirement, filter
by source and expected outcome, and choose 5–500 rows per page. **View example**
shows the stored HTML, rule, source links and recorded provenance. HTML is displayed
as escaped text: scripts and external resources are not executed or loaded.
Filters update immediately when changed; search updates as you type. Paging
updates only the list, keeping the controls and scroll position in place.
There is no Apply filters button. A request failure retains the previous rows
and shows an error rather than clearing the list.
There is only one maintenance action: **Initialize/Update knowledge**. Status
refreshes automatically; when a new corpus becomes active, the list, summary
and provenance refresh together without moving the page. **Corpus provenance**
sits below the table. The compact summary combines counts and eligibility: approved
passed/failed cases provide examples of barriers and correct implementations,
whereas unapproved and inapplicable cases are excluded from this repair corpus.
The summary links to the [W3C ACT Rules catalogue](https://www.w3.org/WAI/standards-guidelines/act/rules/) for the upstream rules and their test cases.

The counts refer to the local snapshot, not the whole upstream ACT catalogue.
Synchronization includes approved `passed` and `failed` cases; unapproved and
`inapplicable` cases are not indexed. There is no fixed 125-example corpus limit.
Approval is a **rule status** from the W3C snapshot; `passed`, `failed` and
`inapplicable` are **test-case outcomes**. An inapplicable case contains no
test target for that rule, rather than demonstrating a correct or incorrect
implementation. Excluding it does not remove the rule's passed/failed examples
or mean that the rule is irrelevant to other websites. This eligibility policy
is not a selection based on which sites worked in a pilot.
Retrieval supplies a separate bounded subset to a refinement prompt, not the
entire stored corpus. Newly synchronized manifests also record upstream, approved
and eligible counts; older manifests may not have this coverage metadata.

Browsing does not synchronize, modify examples or make model calls. If the active
snapshot changes while browsing, the explorer reads the new collection automatically,
retaining filters and returning to its first page. Failed reads retain previous results.

## Retrieval implementation

A11yResearch converts each example's descriptive metadata and HTML into a
normalized 384-dimensional vector using `embed()` in
`web/app/remediation_rag.py`. Despite the function name, this is local feature
hashing, not a learned embedding model or an external API call. Qdrant stores
these vectors and performs cosine search; lexical/concept checks then select
relevant evidence. Mappings connect measured Axe rules to ACT concepts.

Retrieved context is bounded. The routine favors complete positive/negative pairs for a matched rule and excludes examples that exceed the context budget. If no relevant complete evidence is available, the trace records an empty retrieval.

## Initialize or update the corpus

Open **RAG-ACT** from the main sidebar.
The panel shows availability, separate official/complementary example counts
and the last recorded synchronization time (older installations may show
"Not recorded"). Use **Initialize knowledge** for an empty corpus, or
**Update knowledge** to request a new snapshot. Updates require confirmation;
the button is unavailable while remediations are queued or running.

The worker downloads and indexes examples in the background. Progress and errors
appear in the panel without reloading the page. A complete new collection is
verified before its pointer is published; failures retain the previous corpus.
Earlier snapshots and saved run evidence are not deleted. No synchronization is
started merely by opening the page or enabling the remediation switch.
After synchronization, the example browser automatically reads the newly activated
snapshot. No separate status-refresh or example-reload button is needed.

The equivalent administrative command is:

```bash
docker compose exec worker python sync_act_rag.py
```

The command queues maintenance and returns immediately; the worker must be running.
Monitor progress on the RAG-ACT page. The queued task downloads the upstream snapshot
and includes the separately attributed supplement. It activates a new corpus for
future retrieval but preserves the old collection. For first-time initialization,
use `docker compose exec worker python sync_act_rag.py --initialize-only`;
it refuses to replace a nonempty corpus.
The CLI shares the maintenance lock and remediation guard with the RAG-ACT page.
Neither operation makes an LLM or paid embedding call. Update between cohorts
to keep the retrieval snapshot consistent within a study. Maintenance state and
the active corpus pointer are persisted in the shared `/data/act-rag` directory;
include it with Qdrant storage in installation backups.

To inspect availability without modifying the corpus, use the application's remediation panel or call `status()` from `web/app/remediation_rag.py` inside the service.

## If retrieval is unavailable

When the vector service or relevant examples are unavailable, remediation can still retain an evaluated candidate. The trace records retrieval availability and the context actually supplied. Check service connectivity and corpus status to diagnose an empty retrieval.

The technical boundaries are covered in [Agent runtime](../technical/agent-runtime.md); the retrieval functions are mapped in the [source reference](../reference/source-map.md).
