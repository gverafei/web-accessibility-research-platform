"""Keep the packaged skin shared and remediation sliders visually isolated."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "web/app/static/css/theme.css"


class SharedThemeTests(unittest.TestCase):
    def test_extension_mirror_is_identical(self):
        self.assertEqual(CSS.read_bytes(), (ROOT / "browser_extension/theme.css").read_bytes())

    def test_skin_loads_after_page_styles_and_extension_styles(self):
        base = (ROOT / "web/app/templates/base.html").read_text()
        self.assertGreater(base.index("css/theme.css"), base.index("{% block extra_head %}"))
        panel = (ROOT / "browser_extension/sidepanel.html").read_text()
        self.assertGreater(panel.index('href="theme.css"'), panel.index('href="sidepanel.css"'))
        self.assertIn('body class="extension-panel"', panel)

    def test_skin_does_not_redefine_slider_tokens_or_range_widgets(self):
        css = CSS.read_text()
        self.assertNotRegex(css, r"--(?:tier-color|tier-progress|accent|line|surface|muted|uv-blue|uv-green|green|blue)\s*:")
        self.assertNotIn("input[type=range]", css)
        self.assertNotIn("slider-thumb", css)
        self.assertNotIn("slider-runnable-track", css)
        # Protected cards appear only as exclusion selectors, never as targets.
        for selector, _ in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            selector = re.sub(r":not\(\.(?:model-tier-card|slider-card) \*\)", "", selector)
            self.assertNotIn(".model-tier-card", selector)
            self.assertNotIn(".slider-card", selector)

    def test_theme_covers_general_components_and_accessible_states(self):
        css = CSS.read_text()
        for component in (".app-sidebar", ".app-topbar", ".btn", ".research-metric",
                          ".form-control", ".form-select", ".form-switch", ".table",
                          ".alert", ".badge", ".dropdown-menu", ".extension-panel"):
            with self.subTest(component=component):
                self.assertIn(component, css)
        self.assertIn('html[data-theme="dark"]', css)
        self.assertIn(":focus-visible", css)
        self.assertIn(":disabled", css)

    def test_semantic_badges_and_extension_primary_override_keep_their_roles(self):
        css = CSS.read_text()
        self.assertIn(".badge.remediation-status-accept", css)
        self.assertIn(".badge.remediation-status-completed_with_warnings", css)
        self.assertIn(".badge.remediation-status-failed", css)
        self.assertIn(".badge.text-bg-success", css)
        self.assertIn("#start, #newPage", css)
        self.assertIn(".extension-panel .platform-name", css)
        self.assertIn(".toggle input:checked::after", css)
        for action in ("export", "delete", "pause", "resume", "manage"):
            self.assertIn(f".experiment-action-{action}", css)

    def test_main_role_text_has_readable_light_and_dark_contrast(self):
        css = CSS.read_text()
        palettes = re.findall(r"--ui-blue:.*?--ui-shadow:[^;]+;", css, re.S)
        self.assertEqual(len(palettes), 2)

        def luminance(rgb):
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
            return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))

        for palette in palettes:
            colors = dict(re.findall(r"--ui-(\w+): #(\w{6});", palette))
            rgb = {key: tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)) for key, value in colors.items()}
            for role in ("blue", "green", "amber", "red", "violet", "neutral"):
                # Most saturated hover, not just resting/white backgrounds.
                fill = tuple(.18 * a + .82 * b for a, b in zip(rgb[role], rgb["surface"]))
                levels = sorted((luminance(rgb[role]), luminance(fill)))
                with self.subTest(palette=colors["surface"], role=role):
                    self.assertGreaterEqual((levels[1] + .05) / (levels[0] + .05), 4.5)

    def test_navigation_is_darker_than_content_in_both_palettes(self):
        css = CSS.read_text()
        palettes = re.findall(r"--ui-blue:.*?--ui-shadow:[^;]+;", css, re.S)
        for palette in palettes:
            colors = dict(re.findall(r"--ui-(\w+): #(\w{6});", palette))
            def luminance(hex_color):
                rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
                linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
                return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
            self.assertLess(luminance(colors['sidebar']), luminance(colors['paper']))
        topbar = re.search(r"html\[data-theme\] \.app-topbar\s*\{([^}]+)", css).group(1)
        self.assertIn('background: var(--ui-sidebar)', topbar)

    def test_descriptive_cards_are_neutral_and_retention_detail_is_compact(self):
        css = CSS.read_text()
        for selector in ('.research-metric', '.content-retention-summary', '.extension-panel .completion-summary'):
            block = re.search(r'html\[data-theme\] ' + re.escape(selector) + r'\s*\{([^}]+)', css).group(1)
            self.assertNotIn('--ui-green', block)
            self.assertIn('--ui-neutral', block)
        self.assertIn('.research-metric > strong { color: var(--ui-ink); }', css)
        self.assertIn('.retention-detail-table { font-size: .75rem; }', css)
        layout = (ROOT / 'web/app/static/css/remediation_layout.css').read_text()
        self.assertNotIn('.remediation-metric-grid .research-metric{border-top-color:var(--uv-green)}', layout)

    def test_dashboard_creation_actions_use_the_same_unfilled_role(self):
        css = CSS.read_text()
        block = re.search(r'\.dashboard-hero-actions :is\(\.btn-light, \.btn-outline-light\)\s*\{([^}]+)', css).group(1)
        self.assertIn('--ui-role: var(--ui-neutral)', block)
        self.assertIn('--ui-fill: 0%', block)

    def test_inline_category_select_fits_the_padded_table_cell(self):
        css = CSS.read_text()
        block = re.search(
            r'html\[data-theme\] \.measurement-table \.url-category-select\s*\{([^}]+)',
            css,
        ).group(1)
        self.assertIn('width: 100%', block)
        self.assertIn('min-width: 0', block)
        self.assertIn('max-width: 100%', block)
        # Retain the native arrow, shared focus styling and font size.
        for override in ('appearance:', 'background:', 'font-size:', 'overflow:'):
            self.assertNotIn(override, block)

    def test_manage_urls_uses_compact_proportional_columns(self):
        markup = (ROOT / 'web/app/templates/manage_urls.html').read_text()
        css = CSS.read_text()
        self.assertIn('min-width: 1200px', css)
        self.assertIn('width: calc(100% - 1px)', css)
        self.assertIn('#urlCatalogTable :is(th, .sort-button)', css)
        self.assertIn('#urlCatalogTable .sort-button { max-width: 100%; }', css)
        self.assertNotIn('min-width:1650px', markup)
        colgroup = re.search(r'<colgroup>(.*?)</colgroup>', markup).group(1)
        self.assertEqual(len(re.findall(r'<col\b', colgroup)), 8)
        self.assertIn('width:42px', colgroup)
        for width in ('16%', '8%', '10%', '15%', '13%'):
            self.assertIn('width:' + width, colgroup)
        self.assertIn('<col>', colgroup)  # Evaluation uses the remaining width.

    def test_history_tables_share_the_preferred_remediation_hover(self):
        css = CSS.read_text()
        self.assertIn('--bs-table-hover-bg: var(--ui-table-hover)', css)
        self.assertIn('--ui-table-hover: color-mix(in srgb, var(--ui-blue) 8%, var(--ui-surface))', css)
        self.assertIn('--ui-table-hover: #1c2530', css)
        legacy_css = (ROOT / 'web/app/static/css/style.css').read_text()
        self.assertNotIn('.remediation-history-table.table-hover>tbody>tr:hover', legacy_css)
        for template in ('experiments.html', 'remediation_history.html'):
            markup = (ROOT / 'web/app/templates' / template).read_text()
            self.assertIn('table table-hover', markup)
