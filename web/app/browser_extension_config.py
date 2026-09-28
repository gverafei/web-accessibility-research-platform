"""Extension configuration shares the platform's explicit research controls."""
from remediation_approaches import APPROACHES
from remediation_model_choices import model_choice, model_choices, frozen_model_configuration
from remediation_recipes import automatic_recipe, common_conditions

PRIORITIES = (15, 35, 55, 75, 90)
PRESERVATION_COLORS = ('#2f9e66', '#2686c9', '#6558c8', '#9b4fc2', '#c3486b')


def extension_catalog(settings):
    choices = model_choices(settings)
    return {
        "models": choices,
        "default_model": next((c['id'] for c in choices if c.get('is_default')), next((c['id'] for c in choices if c['id'] == 'openai/gpt-6-luna'), choices[0]['id'])),
        "preservation": [
            {"level": level, "name": approach.name, "instruction": approach.instruction,
             "color": PRESERVATION_COLORS[level],
             "priority": priority, "execution_mode": "regenerate_refine" if level >= 3 else "iterative",
             "recipe": automatic_recipe(priority, settings=settings)}
            for level, (priority, approach) in enumerate(zip(PRIORITIES, APPROACHES))
        ],
        "capture_scope": "URL acquisition; not the current tab's DOM or authenticated session",
    }


def extension_configuration(payload, settings):
    # Old numeric model levels cannot identify today's catalogue reliably.
    # Require an explicit choice instead of silently changing experiments.
    choice = model_choice(str(payload.get("selected_model") or ""), settings)
    level = int(payload.get("preservation_level", 2))
    if level not in range(5):
        raise ValueError("Choose a preservation level from 0 to 4.")
    targets = common_conditions(settings)
    configuration = {"selected_model": choice["id"], "model_configuration": frozen_model_configuration(choice), "preservation_level": level,
                     "research_targets": {key: targets[key] for key in ('lighthouse', 'axe')},
                     "use_rag": bool(payload.get("use_rag")), "use_wave": False}
    if choice['model'].startswith('ollama/'):
        from local_llm import local_configuration
        configuration['local_llm_configuration'] = local_configuration(settings)
    return configuration
