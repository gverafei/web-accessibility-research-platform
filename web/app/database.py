import os
import time
import mysql.connector
from mysql.connector import Error
from flask import current_app


def remediation_builtin_templates():
    head='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous"><style>.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:1rem;top:1rem;z-index:2000}.required::after{content:" (required)";font-weight:400}</style></head><body><a class="skip-link btn btn-primary" href="#main">Skip to main content</a>'''
    foot='''<footer class="border-top mt-5 py-4"><div class="container">{{ footer }}</div></footer><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script></body></html>'''
    templates = [
      ("Bootstrap accessible homepage","homepage","Responsive navigation, hero, landmark regions and content cards using Bootstrap 5.3.",head+'''<header><nav class="navbar navbar-expand-lg bg-body-tertiary" aria-label="Primary"><div class="container"><a class="navbar-brand" href="#">{{ brand }}</a><button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#primaryNav" aria-controls="primaryNav" aria-expanded="false" aria-label="Toggle navigation"><span class="navbar-toggler-icon"></span></button><div class="collapse navbar-collapse" id="primaryNav"><ul class="navbar-nav">{{ navigation_items }}</ul></div></div></nav></header><main id="main"><section class="py-5 bg-light" aria-labelledby="page-heading"><div class="container"><h1 id="page-heading">{{ heading }}</h1><p class="lead">{{ introduction }}</p>{{ primary_action }}</div></section><section class="container py-5" aria-labelledby="content-heading"><h2 id="content-heading">{{ section_heading }}</h2><div class="row g-4">{{ content_cards }}</div></section></main>'''+foot),
      ("Bootstrap accessible form","form","Validated form pattern with instructions, explicit labels, errors and grouped controls.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><div class="col-lg-8"><h1>{{ heading }}</h1><p id="form-help">{{ instructions }}</p><div class="alert alert-danger" role="alert" tabindex="-1" hidden>{{ error_summary }}</div><form aria-describedby="form-help" novalidate>{{ form_fields }}<button class="btn btn-primary" type="submit">{{ submit_label }}</button></form></div></main>'''+foot),
      ("Bootstrap accessible search","search","Search landmark, status announcements, filters and semantic result list.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><h1>{{ heading }}</h1><form class="row g-2" role="search"><div class="col"><label class="visually-hidden" for="query">Search terms</label><input class="form-control" id="query" name="q" type="search" value="{{ query }}"></div><div class="col-auto"><button class="btn btn-primary" type="submit">Search</button></div></form><p class="mt-4" role="status" aria-live="polite">{{ result_count }}</p><section aria-labelledby="results-heading"><h2 id="results-heading">Results</h2><ol class="list-group list-group-numbered">{{ results }}</ol></section></main>'''+foot),
      ("Bootstrap accessible article","article","Readable article layout with metadata, table of contents and related content.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><div class="row"><article class="col-lg-8"><header><h1>{{ heading }}</h1><p class="text-body-secondary">{{ metadata }}</p></header>{{ content }}</article><aside class="col-lg-4" aria-labelledby="related-heading"><h2 id="related-heading" class="h4">Related content</h2>{{ related }}</aside></div></main>'''+foot),
      ("Bootstrap accessible product","product","Product detail, media alternatives, price, variants and clear purchase action.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><div class="row g-5"><section class="col-md-6" aria-label="Product media">{{ product_media }}</section><section class="col-md-6"><h1>{{ product_name }}</h1><p class="fs-3" aria-label="Price">{{ price }}</p>{{ description }}<form>{{ variants }}<button class="btn btn-primary btn-lg" type="submit">Add to cart</button></form><div aria-live="polite">{{ cart_status }}</div></section></div></main>'''+foot),
      ("Bootstrap accessible authentication","authentication","Sign-in pattern with autocomplete, recovery path and accessible errors.",head+'''<main id="main" class="container py-5"><div class="card mx-auto" style="max-width:32rem"><div class="card-body p-4"><h1 class="h2">{{ heading }}</h1><p id="signin-help">{{ instructions }}</p><form aria-describedby="signin-help" novalidate><div class="mb-3"><label class="form-label" for="username">Email or username</label><input class="form-control" id="username" name="username" autocomplete="username" required></div><div class="mb-3"><label class="form-label" for="password">Password</label><input class="form-control" id="password" name="password" type="password" autocomplete="current-password" required></div><button class="btn btn-primary w-100" type="submit">Sign in</button></form>{{ recovery_links }}</div></div></main>'''+foot),
      ("Bootstrap accessible listing","listing","Filterable directory or category listing with result status and pagination.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><h1>{{ heading }}</h1><div class="row"><aside class="col-lg-3" aria-labelledby="filters-heading"><h2 id="filters-heading" class="h4">Filters</h2>{{ filters }}</aside><section class="col-lg-9" aria-labelledby="items-heading"><h2 id="items-heading" class="h4">{{ result_count }}</h2><div class="row g-3">{{ items }}</div>{{ pagination }}</section></div></main>'''+foot),
      ("Bootstrap accessible media","media","Audio/video page with transcript, captions guidance and related content.",head+'''<header class="border-bottom"><div class="container py-3">{{ navigation }}</div></header><main id="main" class="container py-5"><h1>{{ heading }}</h1><figure>{{ media_player }}<figcaption>{{ media_description }}</figcaption></figure><section aria-labelledby="transcript-heading"><h2 id="transcript-heading">Transcript</h2>{{ transcript }}</section><section aria-labelledby="related-heading"><h2 id="related-heading">Related media</h2>{{ related }}</section></main>'''+foot)
    ]
    tw_head='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script><style>.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:1rem;top:1rem;z-index:50}</style></head><body class="min-h-screen bg-white text-slate-900 antialiased"><a class="skip-link rounded bg-blue-700 px-4 py-2 font-semibold text-white focus:outline-none focus:ring-4 focus:ring-blue-300" href="#main">Skip to main content</a>'''
    tw_foot='''<footer class="mt-16 border-t border-slate-200"><div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{{ footer }}</div></footer></body></html>'''
    templates.extend([
      ("Tailwind accessible homepage","homepage","Responsive landmarks, hero, navigation and content cards using Tailwind CSS.",tw_head+'''<header class="border-b border-slate-200"><nav class="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8" aria-label="Primary"><a class="text-xl font-bold focus:outline-none focus:ring-4 focus:ring-blue-300" href="#">{{ brand }}</a><ul class="flex flex-wrap gap-5">{{ navigation_items }}</ul></nav></header><main id="main"><section class="bg-slate-50 py-16" aria-labelledby="page-heading"><div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8"><h1 id="page-heading" class="text-4xl font-bold tracking-tight">{{ heading }}</h1><p class="mt-4 max-w-3xl text-xl text-slate-700">{{ introduction }}</p><div class="mt-8">{{ primary_action }}</div></div></section><section class="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8" aria-labelledby="content-heading"><h2 id="content-heading" class="text-2xl font-bold">{{ section_heading }}</h2><div class="mt-6 grid gap-6 md:grid-cols-2 lg:grid-cols-3">{{ content_cards }}</div></section></main>'''+tw_foot),
      ("Tailwind accessible form","form","Form pattern with instructions, explicit labels, errors, groups and strong focus styles.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto max-w-3xl px-4 py-12 sm:px-6"><h1 class="text-3xl font-bold">{{ heading }}</h1><p id="form-help" class="mt-3 text-slate-700">{{ instructions }}</p><div class="mt-6 rounded border-l-4 border-red-700 bg-red-50 p-4 text-red-950" role="alert" tabindex="-1" hidden>{{ error_summary }}</div><form class="mt-8 space-y-6" aria-describedby="form-help" novalidate>{{ form_fields }}<button class="rounded bg-blue-700 px-5 py-3 font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300" type="submit">{{ submit_label }}</button></form></main>'''+tw_foot),
      ("Tailwind accessible search","search","Named search, live result status, filters and a semantic results list.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto max-w-5xl px-4 py-12 sm:px-6"><h1 class="text-3xl font-bold">{{ heading }}</h1><form class="mt-6 flex gap-3" role="search"><label class="sr-only" for="query">Search terms</label><input class="min-w-0 flex-1 rounded border border-slate-400 px-4 py-3 focus:outline-none focus:ring-4 focus:ring-blue-300" id="query" name="q" type="search" value="{{ query }}"><button class="rounded bg-blue-700 px-5 py-3 font-semibold text-white focus:outline-none focus:ring-4 focus:ring-blue-300" type="submit">Search</button></form><p class="mt-6" role="status" aria-live="polite">{{ result_count }}</p><section class="mt-6" aria-labelledby="results-heading"><h2 id="results-heading" class="text-2xl font-bold">Results</h2><ol class="mt-4 divide-y divide-slate-200">{{ results }}</ol></section></main>'''+tw_foot),
      ("Tailwind accessible article","article","Readable article, metadata, related-content landmark and constrained measure.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[minmax(0,2fr)_minmax(16rem,1fr)] lg:px-8"><article class="prose prose-slate max-w-none"><header><h1>{{ heading }}</h1><p class="text-slate-600">{{ metadata }}</p></header>{{ content }}</article><aside aria-labelledby="related-heading"><h2 id="related-heading" class="text-xl font-bold">Related content</h2><div class="mt-4">{{ related }}</div></aside></main>'''+tw_foot),
      ("Tailwind accessible product","product","Product media, variants, price and purchase status with accessible controls.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2 lg:px-8"><section aria-label="Product media">{{ product_media }}</section><section><h1 class="text-3xl font-bold">{{ product_name }}</h1><p class="mt-4 text-3xl" aria-label="Price">{{ price }}</p><div class="mt-5 text-slate-700">{{ description }}</div><form class="mt-8 space-y-6">{{ variants }}<button class="rounded bg-blue-700 px-6 py-3 font-semibold text-white focus:outline-none focus:ring-4 focus:ring-blue-300" type="submit">Add to cart</button></form><div class="mt-4" aria-live="polite">{{ cart_status }}</div></section></main>'''+tw_foot),
      ("Tailwind accessible authentication","authentication","Sign-in layout with autocomplete, recovery, explicit fields and errors.",tw_head+'''<main id="main" class="mx-auto flex min-h-screen max-w-lg items-center px-4 py-12"><section class="w-full rounded-xl border border-slate-200 bg-white p-8 shadow-sm" aria-labelledby="signin-heading"><h1 id="signin-heading" class="text-3xl font-bold">{{ heading }}</h1><p id="signin-help" class="mt-3 text-slate-700">{{ instructions }}</p><form class="mt-8 space-y-5" aria-describedby="signin-help" novalidate><div><label class="font-semibold" for="username">Email or username</label><input class="mt-2 w-full rounded border border-slate-400 px-4 py-3 focus:outline-none focus:ring-4 focus:ring-blue-300" id="username" name="username" autocomplete="username" required></div><div><label class="font-semibold" for="password">Password</label><input class="mt-2 w-full rounded border border-slate-400 px-4 py-3 focus:outline-none focus:ring-4 focus:ring-blue-300" id="password" name="password" type="password" autocomplete="current-password" required></div><button class="w-full rounded bg-blue-700 px-5 py-3 font-semibold text-white focus:outline-none focus:ring-4 focus:ring-blue-300" type="submit">Sign in</button></form><div class="mt-5">{{ recovery_links }}</div></section></main>'''+tw_foot),
      ("Tailwind accessible listing","listing","Filterable directory with a live count, responsive grid and pagination.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8"><h1 class="text-3xl font-bold">{{ heading }}</h1><div class="mt-8 grid gap-10 lg:grid-cols-[16rem_minmax(0,1fr)]"><aside aria-labelledby="filters-heading"><h2 id="filters-heading" class="text-xl font-bold">Filters</h2><div class="mt-4">{{ filters }}</div></aside><section aria-labelledby="items-heading"><h2 id="items-heading" class="text-xl font-bold" aria-live="polite">{{ result_count }}</h2><div class="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{{ items }}</div><nav class="mt-8" aria-label="Pagination">{{ pagination }}</nav></section></div></main>'''+tw_foot),
      ("Tailwind accessible media","media","Audio or video page with description, transcript and related-media regions.",tw_head+'''<header class="border-b border-slate-200">{{ navigation }}</header><main id="main" class="mx-auto max-w-5xl px-4 py-12 sm:px-6"><h1 class="text-3xl font-bold">{{ heading }}</h1><figure class="mt-8">{{ media_player }}<figcaption class="mt-3 text-slate-700">{{ media_description }}</figcaption></figure><section class="mt-10" aria-labelledby="transcript-heading"><h2 id="transcript-heading" class="text-2xl font-bold">Transcript</h2><div class="mt-4">{{ transcript }}</div></section><section class="mt-10" aria-labelledby="related-heading"><h2 id="related-heading" class="text-2xl font-bold">Related media</h2><div class="mt-4">{{ related }}</div></section></main>'''+tw_foot)
    ])
    return templates


def ensure_column(cursor, table_name, column_name, definition):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )

    if cursor.fetchone()[0] == 0:
        cursor.execute(
            f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}"
        )


def ensure_experiment_url_capacity(cursor):
    """Widen legacy URL lists without deleting or rewriting observations."""
    cursor.execute("SHOW COLUMNS FROM experiments LIKE 'urls'")
    column = cursor.fetchone()
    if column and column[1].lower() != "longtext":
        cursor.execute("ALTER TABLE experiments MODIFY COLUMN urls LONGTEXT NOT NULL")


def get_connection():
    # return mysql.connector.connect(
    #     host=os.getenv("DB_HOST", "db"),
    #     port=int(os.getenv("DB_PORT", "3306")),
    #     database=os.getenv("DB_NAME", "accessibility_experiments"),
    #     user=os.getenv("DB_USER", "access_user"),
    #     password=os.getenv("DB_PASSWORD", "access_pass"),
    # )

    return mysql.connector.connect(
        host=current_app.config["DB_HOST"],
        port=int(current_app.config["DB_PORT"]),
        database=current_app.config["DB_NAME"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
    )


def init_db():
    max_attempts = 100

    for attempt in range(max_attempts):
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS url_category_jobs (
                    id TINYINT PRIMARY KEY DEFAULT 1,
                    status VARCHAR(20) NOT NULL DEFAULT 'idle',
                    total_urls INT NOT NULL DEFAULT 0,
                    completed_urls INT NOT NULL DEFAULT 0,
                    model VARCHAR(255),
                    input_tokens INT NOT NULL DEFAULT 0,
                    output_tokens INT NOT NULL DEFAULT 0,
                    cost_usd DECIMAL(14,8) NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at DATETIME,
                    updated_at DATETIME NOT NULL
                )
            """)
            ensure_column(cursor, "url_category_jobs", "input_tokens", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "url_category_jobs", "experiment_id", "INT NULL")
            ensure_column(cursor, "url_category_jobs", "output_tokens", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "url_category_jobs", "cost_usd", "DECIMAL(14,8) NOT NULL DEFAULT 0")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    storage_key CHAR(32) NOT NULL UNIQUE,
                    content_sha256 CHAR(64) NOT NULL,
                    resource_policy VARCHAR(20) NOT NULL DEFAULT 'isolated',
                    observation_count INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dataset_observations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    dataset_id INT NOT NULL,
                    relative_path TEXT NOT NULL,
                    observation_key VARCHAR(255) NOT NULL,
                    pair_key VARCHAR(255) NULL,
                    condition_label VARCHAR(100) NULL,
                    stratum VARCHAR(100) NULL,
                    expected_label TINYINT NULL,
                    content_sha256 CHAR(64) NOT NULL,
                    served_url TEXT NOT NULL,
                    display_name VARCHAR(255) NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
                )
            """)
            ensure_column(cursor, "dataset_observations", "display_name", "VARCHAR(255) NULL")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    urls LONGTEXT NOT NULL,
                    include_semantic BOOLEAN NOT NULL DEFAULT FALSE,
                    include_wave BOOLEAN NOT NULL DEFAULT FALSE,
                    semantic_provider VARCHAR(50) NULL,
                    semantic_model VARCHAR(255) NULL,
                    axe_standard VARCHAR(20) NOT NULL DEFAULT 'wcag22aa',
                    axe_include_best_practices BOOLEAN NOT NULL DEFAULT FALSE,
                    reuse_cached_results BOOLEAN NOT NULL DEFAULT FALSE,
                    evaluation_signature CHAR(64) NULL,
                    experiment_origin VARCHAR(30) NOT NULL DEFAULT 'evaluation',
                    language VARCHAR(10) NOT NULL DEFAULT 'en',
                    status VARCHAR(50) NOT NULL DEFAULT 'registered',
                    created_at DATETIME NOT NULL,
                    completed_at DATETIME NULL,
                    resume_count INT NOT NULL DEFAULT 0,
                    last_resumed_at DATETIME NULL
                )
            """)

            ensure_experiment_url_capacity(cursor)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiment_environment (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    experiment_id INT NOT NULL,
                    docker_web_image VARCHAR(255) NULL,
                    docker_evaluator_image VARCHAR(255) NULL,
                    python_version VARCHAR(100) NULL,
                    node_version VARCHAR(100) NULL,
                    chromium_version VARCHAR(255) NULL,
                    axe_version VARCHAR(100) NULL,
                    axe_standard VARCHAR(20) NULL,
                    axe_include_best_practices BOOLEAN NULL,
                    axe_counting_mode VARCHAR(50) NULL,
                    app_timezone VARCHAR(100) NULL,
                    lighthouse_version VARCHAR(100) NULL,
                    openai_model VARCHAR(100) NULL,
                    llm_provider VARCHAR(50) NULL,
                    llm_model VARCHAR(255) NULL,
                    wave_api_version VARCHAR(50) NULL,
                    wave_report_type INT NULL,
                    wave_eval_delay_ms INT NULL,
                    page_load_timeout_ms INT NULL,
                    network_idle_timeout_ms INT NULL,
                    page_settle_delay_ms INT NULL,
                    dom_stability_window_ms INT NULL,
                    dom_stability_timeout_ms INT NULL,
                    lazy_load_scroll BOOLEAN NULL,
                    scroll_step_px INT NULL,
                    scroll_delay_ms INT NULL,
                    max_scroll_steps INT NULL,
                    evaluator_concurrency VARCHAR(255) NULL,
                    execution_seconds FLOAT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)

            ensure_column(
                cursor, "experiments", "semantic_provider", "VARCHAR(50) NULL"
            )
            ensure_column(
                cursor, "experiments", "include_wave", "BOOLEAN NOT NULL DEFAULT FALSE"
            )
            ensure_column(
                cursor, "experiments", "semantic_model", "VARCHAR(255) NULL"
            )
            ensure_column(
                cursor, "experiments", "language", "VARCHAR(10) NOT NULL DEFAULT 'en'"
            )
            ensure_column(cursor, "experiments", "axe_standard", "VARCHAR(20) NOT NULL DEFAULT 'wcag22aa'")
            ensure_column(cursor, "experiments", "axe_include_best_practices", "BOOLEAN NOT NULL DEFAULT FALSE")
            ensure_column(cursor, "experiments", "reuse_cached_results", "BOOLEAN NOT NULL DEFAULT FALSE")
            ensure_column(cursor, "experiments", "evaluation_signature", "CHAR(64) NULL")
            ensure_column(cursor, "experiments", "experiment_origin", "VARCHAR(30) NOT NULL DEFAULT 'evaluation'")
            ensure_column(cursor, "experiments", "source_type", "VARCHAR(20) NOT NULL DEFAULT 'url'")
            ensure_column(cursor, "experiments", "dataset_id", "INT NULL")
            ensure_column(cursor, "experiments", "resource_policy", "VARCHAR(20) NOT NULL DEFAULT 'external'")
            ensure_column(cursor, "experiments", "resume_count", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "experiments", "last_resumed_at", "DATETIME NULL")
            ensure_column(cursor, "experiments", "acquisition_quality_policy", "JSON NULL")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tranco_samples (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    experiment_id INT NOT NULL UNIQUE,
                    list_id VARCHAR(100) NOT NULL,
                    list_sha256 CHAR(64) NOT NULL,
                    source_filename VARCHAR(255) NOT NULL,
                    frame_size INT NOT NULL,
                    sampling_seed VARCHAR(100) NOT NULL,
                    sample_per_stratum INT NOT NULL,
                    reserve_per_stratum INT NOT NULL,
                    strata JSON NOT NULL,
                    candidates JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tranco_attempts (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    experiment_id INT NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    attempt_number INT NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME NULL,
                    wall_seconds DOUBLE NULL,
                    evaluator_seconds DOUBLE NULL,
                    error_category VARCHAR(80) NULL,
                    error_message TEXT NULL,
                    INDEX idx_tranco_attempts_experiment (experiment_id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
                )
            """)
            ensure_column(
                cursor, "experiment_environment", "llm_provider", "VARCHAR(50) NULL"
            )
            ensure_column(
                cursor, "experiment_environment", "llm_model", "VARCHAR(255) NULL"
            )
            ensure_column(
                cursor, "experiment_environment", "wave_api_version", "VARCHAR(50) NULL"
            )
            ensure_column(
                cursor, "experiment_environment", "wave_report_type", "INT NULL"
            )
            environment_columns = {
                "wave_eval_delay_ms": "INT NULL",
                "page_load_timeout_ms": "INT NULL",
                "network_idle_timeout_ms": "INT NULL",
                "page_settle_delay_ms": "INT NULL",
                "dom_stability_window_ms": "INT NULL",
                "dom_stability_timeout_ms": "INT NULL",
                "lazy_load_scroll": "BOOLEAN NULL",
                "scroll_step_px": "INT NULL",
                "scroll_delay_ms": "INT NULL",
                "max_scroll_steps": "INT NULL",
                "evaluator_concurrency": "VARCHAR(255) NULL",
                "axe_standard": "VARCHAR(20) NULL",
                "axe_include_best_practices": "BOOLEAN NULL",
                "axe_counting_mode": "VARCHAR(50) NULL",
                "app_timezone": "VARCHAR(100) NULL",
            }
            for column_name, definition in environment_columns.items():
                ensure_column(cursor, "experiment_environment", column_name, definition)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiment_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    experiment_id INT NOT NULL,
                    url TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    axe_violations INT DEFAULT 0,
                    axe_critical INT DEFAULT 0,
                    axe_serious INT DEFAULT 0,
                    axe_moderate INT DEFAULT 0,
                    axe_minor INT DEFAULT 0,
                    axe_failed_rules INT DEFAULT 0,
                    axe_critical_rules INT DEFAULT 0,
                    axe_serious_rules INT DEFAULT 0,
                    axe_moderate_rules INT DEFAULT 0,
                    axe_minor_rules INT DEFAULT 0,
                    axe_needs_review INT DEFAULT 0,
                    axe_needs_review_rules INT DEFAULT 0,
                    axe_best_practice_issues INT NULL,
                    axe_best_practice_rules INT NULL,
                    axe_wcag_violations INT NULL,
                    axe_wcag_critical INT NULL,
                    axe_wcag_serious INT NULL,
                    axe_wcag_moderate INT NULL,
                    axe_wcag_minor INT NULL,
                    axe_wcag_failed_rules INT NULL,
                    axe_wcag_needs_review INT NULL,
                    lighthouse_score INT NULL,
                    wave_status VARCHAR(50) NULL,
                    wave_errors INT DEFAULT 0,
                    wave_contrast_errors INT DEFAULT 0,
                    wave_alerts INT DEFAULT 0,
                    wave_features INT DEFAULT 0,
                    wave_structure INT DEFAULT 0,
                    wave_aria INT DEFAULT 0,
                    wave_aim_score FLOAT NULL,
                    wave_total_elements INT DEFAULT 0,
                    wave_credits_used INT NULL,
                    wave_cost_usd DECIMAL(14,8) NULL,
                    wave_raw_path TEXT NULL,
                    wave_error_message TEXT NULL,
                    semantic_status VARCHAR(50) NULL,
                    semantic_risk_level VARCHAR(50) NULL,
                    semantic_summary TEXT NULL,
                    semantic_findings JSON NULL,
                    semantic_input_tokens INT NULL,
                    semantic_output_tokens INT NULL,
                    semantic_total_tokens INT NULL,
                    semantic_cost_usd DECIMAL(14,8) NULL,
                    cost_incurred_usd DECIMAL(14,8) NOT NULL DEFAULT 0,
                    html_size INT DEFAULT 0,
                    dom_nodes INT DEFAULT 0,
                    images INT DEFAULT 0,
                    images_without_alt INT DEFAULT 0,
                    links INT DEFAULT 0,
                    buttons INT DEFAULT 0,
                    forms INT DEFAULT 0,
                    inputs INT DEFAULT 0,
                    headings INT DEFAULT 0,
                    h1_count INT DEFAULT 0,
                    language_declared VARCHAR(50) NULL,
                    has_main_landmark BOOLEAN DEFAULT FALSE,
                    has_nav_landmark BOOLEAN DEFAULT FALSE,
                    has_header_landmark BOOLEAN DEFAULT FALSE,
                    has_footer_landmark BOOLEAN DEFAULT FALSE,
                    execution_seconds FLOAT NULL,
                    network_idle_reached BOOLEAN NULL,
                    lazy_scroll_steps INT NULL,
                    dom_stable BOOLEAN NULL,
                    dom_stability_wait_ms INT NULL,
                    screenshot_path TEXT NULL,
                    screenshot_mode VARCHAR(50) NULL,
                    captured_url TEXT NULL,
                    page_title TEXT NULL,
                    acquisition_signals JSON NULL,
                    axe_raw_path TEXT NULL,
                    lighthouse_raw_path TEXT NULL,
                    semantic_raw_path TEXT NULL,
                    source_result_id INT NULL,
                    source_experiment_id INT NULL,
                    provenance VARCHAR(30) NOT NULL DEFAULT 'fresh',
                    normalized_url TEXT NULL,
                    evaluated_at DATETIME NULL,
                    error_message TEXT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)

            wave_result_columns = {
                "wave_status": "VARCHAR(50) NULL",
                "wave_errors": "INT DEFAULT 0",
                "wave_contrast_errors": "INT DEFAULT 0",
                "wave_alerts": "INT DEFAULT 0",
                "wave_features": "INT DEFAULT 0",
                "wave_structure": "INT DEFAULT 0",
                "wave_aria": "INT DEFAULT 0",
                "wave_aim_score": "FLOAT NULL",
                "wave_total_elements": "INT DEFAULT 0",
                "wave_raw_path": "TEXT NULL",
                "wave_error_message": "TEXT NULL",
                "wave_credits_used": "INT NULL",
                "wave_cost_usd": "DECIMAL(14,8) NULL",
            }
            for column_name, definition in wave_result_columns.items():
                ensure_column(
                    cursor, "experiment_results", column_name, definition
                )

            load_result_columns = {
                "network_idle_reached": "BOOLEAN NULL",
                "lazy_scroll_steps": "INT NULL",
                "dom_stable": "BOOLEAN NULL",
                "dom_stability_wait_ms": "INT NULL",
                "screenshot_path": "TEXT NULL",
                "screenshot_mode": "VARCHAR(50) NULL",
                "captured_url": "TEXT NULL",
                "page_title": "TEXT NULL",
                "acquisition_signals": "JSON NULL",
            }
            for column_name, definition in load_result_columns.items():
                ensure_column(cursor, "experiment_results", column_name, definition)

            semantic_usage_columns = {
                "semantic_input_tokens": "INT NULL",
                "semantic_output_tokens": "INT NULL",
                "semantic_total_tokens": "INT NULL",
                "semantic_cost_usd": "DECIMAL(14,8) NULL",
                "cost_incurred_usd": "DECIMAL(14,8) NOT NULL DEFAULT 0",
            }
            for column_name, definition in semantic_usage_columns.items():
                ensure_column(cursor, "experiment_results", column_name, definition)

            axe_result_columns = {
                "axe_failed_rules": "INT DEFAULT 0",
                "axe_critical_rules": "INT DEFAULT 0",
                "axe_serious_rules": "INT DEFAULT 0",
                "axe_moderate_rules": "INT DEFAULT 0",
                "axe_minor_rules": "INT DEFAULT 0",
                "axe_needs_review": "INT DEFAULT 0",
                "axe_needs_review_rules": "INT DEFAULT 0",
                "axe_best_practice_issues": "INT NULL",
                "axe_best_practice_rules": "INT NULL",
                "axe_wcag_violations": "INT NULL",
                "axe_wcag_critical": "INT NULL",
                "axe_wcag_serious": "INT NULL",
                "axe_wcag_moderate": "INT NULL",
                "axe_wcag_minor": "INT NULL",
                "axe_wcag_failed_rules": "INT NULL",
                "axe_wcag_needs_review": "INT NULL",
            }
            for column_name, definition in axe_result_columns.items():
                ensure_column(cursor, "experiment_results", column_name, definition)

            page_feature_columns = {
                "same_domain_links": "INT NULL",
                "visible_text_length": "INT NULL",
                "aria_attributes": "INT NULL",
                "uses_aria": "BOOLEAN NULL",
                "skip_links": "INT NULL",
                "broken_skip_links": "INT NULL",
                "ambiguous_links": "INT NULL",
                "doctype": "VARCHAR(255) NULL",
                "valid_html5_doctype": "BOOLEAN NULL",
                "site_category": "VARCHAR(100) NULL",
                "site_category_source": "VARCHAR(255) NULL",
            }
            for column_name, definition in page_feature_columns.items():
                ensure_column(cursor, "experiment_results", column_name, definition)

            provenance_columns = {
                "source_result_id": "INT NULL",
                "source_experiment_id": "INT NULL",
                "provenance": "VARCHAR(30) NOT NULL DEFAULT 'fresh'",
                "normalized_url": "TEXT NULL",
                "evaluated_at": "DATETIME NULL",
                "dataset_observation_id": "INT NULL",
                "content_sha256": "CHAR(64) NULL",
                "display_name": "VARCHAR(255) NULL",
            }
            for column_name, definition in provenance_columns.items():
                ensure_column(cursor, "experiment_results", column_name, definition)
            ensure_column(cursor, "experiment_results", "source_snapshot_path", "TEXT NULL")
            ensure_column(cursor, "experiment_results", "response_source_path", "TEXT NULL")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS remediation_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(160) NOT NULL,
                    page_type VARCHAR(60) NOT NULL,
                    description TEXT NULL,
                    html_template LONGTEXT NOT NULL,
                    is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS remediation_runs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_result_id INT NOT NULL,
                    template_id INT NULL,
                    title VARCHAR(180) NOT NULL,
                    transformation_format VARCHAR(20) NOT NULL DEFAULT 'html',
                    generator_provider VARCHAR(50) NOT NULL,
                    generator_model VARCHAR(255) NOT NULL,
                    reviewer_provider VARCHAR(50) NOT NULL,
                    reviewer_model VARCHAR(255) NOT NULL,
                    max_iterations INT NOT NULL DEFAULT 3,
                    min_lighthouse INT NOT NULL DEFAULT 96,
                    max_axe INT NOT NULL DEFAULT 3,
                    min_aim DECIMAL(4,1) NULL DEFAULT 9.0,
                    status VARCHAR(30) NOT NULL DEFAULT 'queued',
                    accepted_iteration_id INT NULL,
                    total_input_tokens INT NOT NULL DEFAULT 0,
                    total_output_tokens INT NOT NULL DEFAULT 0,
                    total_cost_usd DECIMAL(14,8) NOT NULL DEFAULT 0,
                    execution_seconds FLOAT NOT NULL DEFAULT 0,
                    error_message TEXT NULL,
                    created_at DATETIME NOT NULL,
                    completed_at DATETIME NULL,
                    FOREIGN KEY (source_result_id) REFERENCES experiment_results(id),
                    FOREIGN KEY (template_id) REFERENCES remediation_templates(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS remediation_iterations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    run_id INT NOT NULL,
                    iteration_number INT NOT NULL,
                    prompt_text LONGTEXT NOT NULL,
                    feedback_text TEXT NULL,
                    output_path TEXT NULL,
                    output_url TEXT NULL,
                    decision VARCHAR(20) NOT NULL,
                    decision_reason TEXT NULL,
                    generator_provider VARCHAR(50) NOT NULL,
                    generator_model VARCHAR(255) NOT NULL,
                    reviewer_provider VARCHAR(50) NOT NULL,
                    reviewer_model VARCHAR(255) NOT NULL,
                    input_tokens INT NOT NULL DEFAULT 0,
                    output_tokens INT NOT NULL DEFAULT 0,
                    cost_usd DECIMAL(14,8) NOT NULL DEFAULT 0,
                    execution_seconds FLOAT NOT NULL DEFAULT 0,
                    axe_violations INT NULL,
                    lighthouse_score INT NULL,
                    wave_aim_score DECIMAL(4,1) NULL,
                    created_at DATETIME NOT NULL,
                    UNIQUE KEY unique_run_iteration (run_id, iteration_number),
                    FOREIGN KEY (run_id) REFERENCES remediation_runs(id) ON DELETE CASCADE
                )
            """)
            ensure_column(cursor, "remediation_runs", "accessibility_priority", "INT NOT NULL DEFAULT 70")
            ensure_column(cursor, "remediation_runs", "temperature", "DECIMAL(3,2) NOT NULL DEFAULT 0.15")
            ensure_column(cursor, "remediation_runs", "template_selection", "VARCHAR(20) NOT NULL DEFAULT 'automatic'")
            ensure_column(cursor, "remediation_runs", "template_rationale", "TEXT NULL")
            ensure_column(cursor, "remediation_runs", "use_wave", "BOOLEAN NOT NULL DEFAULT FALSE")
            ensure_column(cursor, "remediation_runs", "model_selection_mode", "VARCHAR(20) NOT NULL DEFAULT 'manual'")
            ensure_column(cursor, "remediation_runs", "use_expert_settings", "BOOLEAN NULL DEFAULT NULL")
            ensure_column(cursor, "remediation_runs", "model_cost_tier", "VARCHAR(20) NOT NULL DEFAULT 'low'")
            ensure_column(cursor, "remediation_runs", "allowed_models_json", "TEXT NULL")
            ensure_column(cursor, "remediation_runs", "current_phase", "VARCHAR(30) NOT NULL DEFAULT 'queued'")
            ensure_column(cursor, "remediation_runs", "current_iteration", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "remediation_runs", "progress_percent", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "remediation_runs", "progress_message", "VARCHAR(500) NULL")
            ensure_column(cursor, "remediation_runs", "progress_updated_at", "DATETIME NULL")
            ensure_column(cursor, "remediation_runs", "published_experiment_id", "INT NULL")
            ensure_column(cursor, "remediation_runs", "max_dom_distance", "DECIMAL(5,2) NOT NULL DEFAULT 70")
            ensure_column(cursor, "remediation_runs", "enforce_dom_distance", "BOOLEAN NOT NULL DEFAULT FALSE")
            ensure_column(cursor, "remediation_runs", "review_policy", "VARCHAR(30) NOT NULL DEFAULT 'automated'")
            ensure_column(cursor, "remediation_runs", "max_cost_usd", "DECIMAL(10,4) NOT NULL DEFAULT 0.25")
            ensure_column(cursor, "remediation_runs", "max_execution_seconds", "INT NOT NULL DEFAULT 300")
            ensure_column(cursor, "remediation_runs", "use_rag", "BOOLEAN NOT NULL DEFAULT FALSE")
            ensure_column(cursor, "remediation_runs", "generator_evidence_mode", "VARCHAR(24) NOT NULL DEFAULT 'guided'")
            ensure_column(cursor, "remediation_runs", "reconstruction_mode", "VARCHAR(24) NOT NULL DEFAULT 'whole_page'")
            ensure_column(cursor, "remediation_runs", "planner_model", "VARCHAR(150) NOT NULL DEFAULT 'openai/gpt-6-luna'")
            cursor.execute("ALTER TABLE remediation_runs ALTER COLUMN planner_model SET DEFAULT 'openai/gpt-6-luna'")
            ensure_column(cursor, "remediation_runs", "markdown_provider", "VARCHAR(24) NOT NULL DEFAULT 'local'")
            ensure_column(cursor, "remediation_runs", "execution_mode", "VARCHAR(24) NOT NULL DEFAULT 'iterative'")
            ensure_column(cursor, "remediation_runs", "local_llm_config_json", "TEXT NULL")
            ensure_column(cursor, "remediation_runs", "model_config_json", "TEXT NULL")
            ensure_column(cursor, "remediation_runs", "rag_top_k", "INT NOT NULL DEFAULT 4")
            ensure_column(cursor, "remediation_runs", "diagnosis_policy", "VARCHAR(16) NOT NULL DEFAULT 'disabled'")
            cursor.execute("ALTER TABLE remediation_runs ALTER COLUMN diagnosis_policy SET DEFAULT 'disabled'")
            ensure_column(cursor, "remediation_iterations", "wave_credits_used", "INT NOT NULL DEFAULT 0")
            ensure_column(cursor, "remediation_iterations", "wave_cost_usd", "DECIMAL(14,8) NOT NULL DEFAULT 0")
            ensure_column(cursor, "remediation_iterations", "candidate_key", "CHAR(36) NULL")
            ensure_column(cursor, "remediation_iterations", "screenshot_path", "TEXT NULL")
            ensure_column(cursor, "remediation_iterations", "dom_distance", "DECIMAL(5,2) NULL")
            ensure_column(cursor, "remediation_iterations", "original_dom_nodes", "INT NULL")
            ensure_column(cursor, "remediation_iterations", "candidate_dom_nodes", "INT NULL")
            ensure_column(cursor, "remediation_iterations", "dom_changes_json", "JSON NULL")
            ensure_column(cursor, "remediation_iterations", "specialist_reviews_json", "JSON NULL")
            ensure_column(cursor, "remediation_iterations", "agent_usage_json", "JSON NULL")
            ensure_column(cursor, "remediation_iterations", "strategy_json", "JSON NULL")
            ensure_column(cursor, "remediation_iterations", "axe_wcag_violations", "INT NULL")
            ensure_column(cursor, "remediation_iterations", "axe_best_practice_issues", "INT NULL")
            ensure_column(cursor, "remediation_iterations", "axe_metrics_json", "JSON NULL")
            ensure_column(cursor, "remediation_iterations", "axe_raw_path", "TEXT NULL")
            ensure_column(cursor, "remediation_runs", "axe_counting_policy", "VARCHAR(50) NULL")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS remediation_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    run_id INT NOT NULL,
                    actor VARCHAR(80) NOT NULL,
                    event_type VARCHAR(40) NOT NULL,
                    message VARCHAR(1000) NOT NULL,
                    details_json JSON NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES remediation_runs(id) ON DELETE CASCADE,
                    INDEX idx_remediation_event_run (run_id,id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS browser_remediation_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    url TEXT NOT NULL,
                    normalized_url VARCHAR(2048) NOT NULL,
                    acquisition_experiment_id INT NULL,
                    remediation_run_id INT NULL,
                    model_cost_tier VARCHAR(20) NOT NULL DEFAULT 'low',
                    preservation_level INT NOT NULL DEFAULT 2,
                    use_rag BOOLEAN NOT NULL DEFAULT FALSE,
                    use_wave BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR(30) NOT NULL DEFAULT 'queued',
                    error_message TEXT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_browser_request_normalized (normalized_url(191)),
                    FOREIGN KEY (acquisition_experiment_id) REFERENCES experiments(id) ON DELETE SET NULL,
                    FOREIGN KEY (remediation_run_id) REFERENCES remediation_runs(id) ON DELETE SET NULL
                )
            """)
            ensure_column(cursor, "browser_remediation_requests", "configuration_json", "TEXT NULL")
            builtins=remediation_builtin_templates()
            builtin_names=[]
            for name,page_type,description,markup in builtins:
                builtin_names.append(name)
                cursor.execute("SELECT id FROM remediation_templates WHERE name=%s AND is_builtin=TRUE LIMIT 1",(name,))
                existing=cursor.fetchone()
                if existing:
                    cursor.execute("UPDATE remediation_templates SET page_type=%s,description=%s,html_template=%s,updated_at=NOW() WHERE id=%s",(page_type,description,markup,existing[0]))
                else:
                    cursor.execute("INSERT INTO remediation_templates (name,page_type,description,html_template,is_builtin,created_at,updated_at) VALUES (%s,%s,%s,%s,TRUE,NOW(),NOW())",(name,page_type,description,markup))
            cursor.execute("DELETE FROM remediation_templates WHERE is_builtin=TRUE AND name NOT IN ("+",".join(["%s"]*len(builtin_names))+")",builtin_names)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comparison_studies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    dimension_label VARCHAR(100) NOT NULL DEFAULT 'Group',
                    notes TEXT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comparison_members (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    comparison_id INT NOT NULL,
                    source_result_id INT NULL,
                    source_experiment_id INT NULL,
                    source_experiment_title VARCHAR(255) NULL,
                    locator TEXT NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    group_label VARCHAR(100) NOT NULL DEFAULT 'Unassigned',
                    group_label_2 VARCHAR(100) NULL,
                    pair_key VARCHAR(255) NULL,
                    is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
                    sort_order INT NOT NULL DEFAULT 0,
                    evaluated_at DATETIME NULL,
                    axe_violations INT NULL,
                    axe_critical INT NULL,
                    axe_serious INT NULL,
                    axe_moderate INT NULL,
                    axe_minor INT NULL,
                    lighthouse_score INT NULL,
                    wave_errors INT NULL,
                    wave_contrast_errors INT NULL,
                    wave_alerts INT NULL,
                    wave_features INT NULL,
                    wave_aim_score FLOAT NULL,
                    semantic_findings_count INT NULL,
                    semantic_risk_level VARCHAR(50) NULL,
                    semantic_provider VARCHAR(50) NULL,
                    semantic_model VARCHAR(255) NULL,
                    semantic_total_tokens INT NULL,
                    created_at DATETIME NOT NULL,
                    UNIQUE KEY unique_comparison_source (comparison_id, source_result_id),
                    FOREIGN KEY (comparison_id) REFERENCES comparison_studies(id) ON DELETE CASCADE
                )
            """)
            comparison_columns = {
                "wave_alerts": "INT NULL",
                "wave_features": "INT NULL",
                "semantic_total_tokens": "INT NULL",
                "group_label_2": "VARCHAR(100) NULL",
                "sort_order": "INT NOT NULL DEFAULT 0",
                "source_remediation_run_id": "INT NULL",
                "source_remediation_iteration_id": "INT NULL",
                "axe_wcag_violations": "INT NULL",
                "axe_best_practice_issues": "INT NULL",
                "axe_metrics_json": "JSON NULL",
            }
            for column_name, definition in comparison_columns.items():
                ensure_column(cursor, "comparison_members", column_name, definition)
            cursor.execute("""
                UPDATE comparison_members m
                JOIN experiments e ON e.id = m.source_experiment_id
                SET m.semantic_findings_count = NULL,
                    m.semantic_risk_level = NULL,
                    m.semantic_total_tokens = NULL
                WHERE e.include_semantic = FALSE
            """)

            cursor.execute("""
                UPDATE dataset_observations
                SET display_name = LEFT(observation_key, 255)
                WHERE display_name IS NULL OR display_name = ''
            """)
            cursor.execute("""
                UPDATE experiment_results r
                LEFT JOIN dataset_observations o ON o.id = r.dataset_observation_id
                SET r.display_name = LEFT(COALESCE(o.display_name, o.observation_key, r.url), 255)
                WHERE r.display_name IS NULL OR r.display_name = ''
            """)

            conn.commit()
            cursor.close()
            conn.close()
            return

        except Error:
            time.sleep(2)

    raise RuntimeError("No fue posible conectar con MySQL después de varios intentos.")
