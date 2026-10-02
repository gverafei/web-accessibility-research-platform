"""User-facing intervention descriptions shared by web and extension controls."""
from remediation_approaches import APPROACHES

PRESENTATION = (
    ('Maximum visual preservation', 'Smallest repairs; preserves native layout and behavior.'),
    ('Preservation first', 'Limited semantic and contrast correction.'),
    ('Accessibility with controlled change', 'Recognizable design with targeted repair.'),
    ('Accessibility first', 'Regenerate from complete HTML, then refine with localized patches.'),
    ('Screen-reader first', 'Regenerate from Markdown with greater design freedom, then refine with localized patches.'),
)


def control_copy(translate=lambda value: value):
    return {
        'tiers': {key: translate(value) for key, value in (
            ('local', 'Local'), ('low', 'Light'), ('medium', 'Medium'),
            ('high', 'High'), ('xhigh', 'Extra high'), ('max', 'Ultra'))},
        'preservation': [
            {'name': translate(approach.name), 'subtitle': translate(subtitle),
             'description': translate(description)}
            for approach, (subtitle, description) in zip(APPROACHES, PRESENTATION)
        ],
        'labels': {key: translate(value) for key, value in (
            ('temperature', 'Temperature'), ('iterations', 'iterations'),
            ('act', 'ACT examples after failure'), ('native', 'Native / scoped components'))},
    }
