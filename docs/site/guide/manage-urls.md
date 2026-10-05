# Manage URLs and categories

**Manage URLs** is a reusable catalogue of acquired pages. It shows the latest completed record per normalized URL rather than every copy across all evaluations.

The pagination total is labelled **unique URLs** (or matching unique URLs when
filtered). It is not the number of evaluation records: the dashboard and
Evaluations count stored results, including copies in imported or combined
collections. See [Result counts and unique URLs](reports.md#result-counts-and-unique-urls).

## Navigation and editing

The page starts with five rows and queries the server for the requested page. Filtering searches URL, captured URL, editable name, page title, category and evaluation title. Sorting is restricted to supported columns. The browser does not receive thousands of table rows before pagination begins.

The URL and thumbnail identify the acquisition. The separate editable name lets you assign a reusable label without rewriting the captured source. The category is also editable. Scores stay linked to the underlying evaluation; editing a label is not a remeasurement.

The table uses compact proportional columns and wraps long names and headings.
The category selector fits inside its own cell. All columns remain available;
horizontal scrolling is retained when a narrow window cannot fit the table.

An unavailable thumbnail means there is no readable screenshot for that record. Inspect the evaluation and artifact paths instead of assuming a blank thumbnail is a successful blank website.

## Automatic categorization

The categorization panel offers the local Ollama model saved in Configuration
and the enabled cloud model marked
**Default** in the model catalogue. Labels distinguish local execution without
cloud charges from cloud execution with API costs. The usable cloud default is
preselected; if unavailable, choose an available model explicitly. Loading the
options reads saved configuration and never starts a categorization job.

The classifier labels uncategorized pages using the captured URL and page title
against a closed category vocabulary. It does not browse the site again or
inspect the entire page content.

1. Configure the desired local or cloud provider.
2. Select the classifier shown in the panel.
3. Start **Categorize missing**.
4. Watch the persisted progress and review the categories afterward.

The job continues after navigating away or refreshing. **Stop** requests an end at a batch boundary; validated assignments already saved are retained. One active categorization job is stored for the installation, so check its status before starting another.

The classifier does not silently fall back from local to cloud. A provider error leaves a useful message; malformed categories or unexpected IDs are rejected. Cloud usage is recorded before the response is interpreted, including a paid response that fails category validation.

Each new job freezes the chosen model identifier, server and applicable reasoning
settings. Later edits to Configuration do not switch that job to another model.
Cloud credentials are read at execution time and are not stored in the snapshot.

## Research scope

The normal Manage URLs action covers the catalogue. For an automated study, the categorization endpoint also accepts `experiment_id` to restrict work to a completed evaluation. See the [HTTP examples](../technical/api.md). A scoped job fills categories only within that scope.

Labels can be imperfect, especially where the title/URL provides little context. Review unusual cases manually and keep their category provenance. A category such as “Adult Content” is a label, not an automatic instruction to delete the observation. Content eligibility and exclusions belong to your declared study protocol.
