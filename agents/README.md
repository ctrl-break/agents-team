# Agents

CLI-orchestrated CrewAI project for turning a user request into approved
specification artifacts and delivery documents.

## What It Does

The pipeline runs in two phases:

1. Planning
   Generates a draft specification and saves it to `docs/specs/pending-plan.md`.
2. Delivery
   After approval, promotes the plan to `docs/specs/latest-plan.md` and produces:
   - `docs/implementation/backend-plan.md`
   - `docs/implementation/frontend-plan.md`
   - `docs/qa/qa-report.md`
   - `docs/architecture/architecture-review.md`

Artifacts are saved automatically by the task pipeline into `docs/`.

## Installation

Use Python `>=3.10,<3.14`.

```bash
uv sync
```

Set the required environment variables before running:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL_NAME=openai/gpt-5.4-mini
```

If you prefer a different provider, you can also set:

```bash
LLM_PROVIDER=openai
MODEL=gpt-5.4-mini
```

## Running

From the `agents/` directory:

```bash
uv run agent-team "Build a support ticket triage system"
```

Interactive approval is enabled by default. For automated runs:

```bash
uv run agent-team --auto-approve "Build a support ticket triage system"
```

If you already have an approved plan and want to run only delivery:

```bash
uv run agent-team --delivery-only
```

By default this reads `docs/specs/latest-plan.md`. To use a different file:

```bash
uv run agent-team --delivery-only --plan-file docs/specs/my-approved-plan.md
```

You can still pass the original request text if you want to give delivery extra context, but it is optional in this mode.

If no request is passed as an argument, the CLI will prompt for multiline input.

## Notes

- Planning and delivery artifacts are saved automatically to `docs/`.
- The approved specification is treated as the source of truth for downstream tasks.
