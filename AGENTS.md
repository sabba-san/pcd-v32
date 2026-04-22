# AGENTS.md

## Purpose

This repository is a Flask + PostgreSQL application for Malaysian property defect workflows. It combines:

- user authentication and role-based dashboards
- defect/project management backed by SQLAlchemy
- report-generation flows in `app/module3`
- an AI-assisted legal/chatbot component in `app/chatbot_component`

Agents working in this repo should optimize for preserving current behavior, especially in `module3`, where business logic, seeded accounts, PDF/report generation, and role workflows are tightly coupled.

## High-Level Architecture

- `app/__init__.py`
  Creates the Flask app, loads `.env`, configures SQLAlchemy and Flask-Login, registers blueprints, creates tables, and applies a few idempotent `ALTER TABLE` migrations on startup.
- `app/models.py`
  Main SQLAlchemy schema. Central entities are `User`, `Scan`, `Defect`, and supporting report/audit/evidence models.
- `app/auth/routes.py`
  Main login, logout, registration, and dashboard routing.
- `app/module1/routes.py`
  JSON API for the chatbot and document/image analysis endpoints under `/api`.
- `app/module2/routes.py`
  Project/scan upload and visualization workflows for defects and 3D scan assets.
- `app/module3/routes.py`
  Largest business module. Handles defect dashboards, seeded demo accounts, report generation, evidence resolution, audit logging, and compliance/reporting flows.
- `app/module4/routes.py`
  Feedback endpoint.
- `app/chatbot_component/*`
  AI chatbot, legal knowledge loading, feedback handling, and conversation logging.

## Important Runtime Facts

- Database: PostgreSQL, configured through `DATABASE_URL`.
- Auth: Flask-Login using `User` records from `app/models.py`.
- App entrypoint: `app:app`.
- Docker app port: container `5000`, host `5100` from `docker-compose.yml`.
- Environment variables are loaded from `.env` before app setup.
- Groq-backed AI features require `GROQ_API_KEY`.

## Common Commands

- Install dependencies locally:
  `pip install -r requirements.txt`
- Run the app locally:
  `python -c "from app import create_app; app = create_app(); app.run(debug=True, host='0.0.0.0', port=5000)"`
- Run with Docker:
  `docker-compose up --build`
- Initialize database and seed supplemental tables/accounts:
  `flask init-db`
- Seed sample Module 3 data manually:
  `python scripts/db/seed_module3.py`

## Data Model Notes

- `User.user_type` is the primary role field used by the active auth system.
- `User.role` still exists for compatibility with older Module 3 seed/migration logic.
- `Defect` is the main workflow record and is shared across homeowner, developer, and legal flows.
- `app/__init__.py` performs startup-safe schema adjustments for some `defects` columns.
- `app/module3/routes.py` contains additional compatibility helpers such as `_ensure_module3_tables()` and `_ensure_login_accounts_seeded()`.

## Editing Guidance

- Prefer minimal, targeted changes. This codebase contains legacy compatibility paths and partial migrations.
- Treat `app/module3/routes.py` as sensitive. Read surrounding helpers before changing any route or auth-related logic there.
- Keep `user_type` and `role` compatibility in mind when touching authentication or role checks.
- Do not remove fallback import blocks unless the replacement is verified across the repo.
- Preserve existing seeded/demo flows unless the task explicitly asks to remove them.
- Avoid changing generated caches, uploaded assets, or audit JSON files unless the task is specifically about fixtures or data repair.

## Files Agents Should Read First

- `app/__init__.py`
- `app/models.py`
- `app/auth/routes.py`
- `app/module3/routes.py`
- `docker-compose.yml`
- `.env.example`

## Known Caveats

- `readme/README.md` is partially outdated relative to the live app structure.
- There are legacy patch/helper scripts under `scripts/patches/` such as `patch_module3.py`; they are useful as migration history but should not be assumed to reflect the current runtime state.
- Some files with `:Zone.Identifier` suffix are Windows metadata artifacts and should usually be ignored.

## When Adding Features

- For auth/dashboard features: update `app/auth/routes.py`, relevant templates, and check role redirects.
- For schema changes: prefer SQLAlchemy model changes plus safe/idempotent migration handling consistent with current patterns.
- For Module 3 report changes: inspect `app/module3/report_data.py`, `report_generator.py`, and `prompts.py` together.
- For chatbot changes: inspect `app/module1/routes.py` and `app/chatbot_component/chatbot_core.py` together.

## Expected Agent Behavior

- Verify architecture from code, not from the README alone.
- Explain assumptions when touching role behavior or DB schema.
- Prefer `rg` for search and inspect related templates/static assets before changing route behavior.
- If a change touches seeded users, login flow, or defect statuses, note likely regression risk and validate carefully.
