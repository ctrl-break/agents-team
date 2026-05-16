# SpecPipeline — AI-Driven Specification & Implementation Generator

**SpecPipeline** is a multi-agent AI pipeline built on [CrewAI](https://crewai.com) that turns a natural-language project request into a full set of specification and delivery artifacts: plans, architecture reviews, QA reports, and generated source code across backend, frontend, tests, and DevOps.

It orchestrates multiple specialized AI crews through a structured 10-phase workflow with quality scoring, iterative review, human-in-the-loop approval, and automatic validation.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
  - [Quick CLI (Legacy)](#quick-cli-legacy)
  - [Full Pipeline CLI](#full-pipeline-cli)
  - [Interactive Mode](#interactive-mode)
  - [File-Based Workflow](#file-based-workflow)
  - [Resuming and Fixes](#resuming-and-fixes)
  - [Auto-Approve Mode](#auto-approve-mode)
- [Pipeline Phases](#pipeline-phases)
- [Artifacts Produced](#artifacts-produced)
- [Crews Overview](#crews-overview)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Quality Thresholds](#quality-thresholds)
- [Development](#development)
  - [Makefile Commands](#makefile-commands)
  - [Running Tests](#running-tests)
  - [Linting & Type Checking](#linting--type-checking)
- [Architecture](#architecture)
- [Requirements](#requirements)

---

## What It Does

SpecPipeline takes a high-level project description such as:

> "Build a support ticket triage system with a React frontend and FastAPI backend"

And automatically produces:

| Artifact | Phase | Description |
|---|---|---|
| `docs/specs/pending-plan.md` | Planning | Draft specification (human-reviewed) |
| `docs/specs/latest-plan.md` | Human Approval | Approved source-of-truth specification |
| `docs/implementation/backend-plan.md` | Implementation | Backend architecture & API plan |
| `docs/implementation/frontend-plan.md` | Implementation | Frontend component & route plan |
| `docs/qa/qa-report.md` | QA | Quality assurance review |
| `docs/architecture/architecture-review.md` | QA | Architectural review |
| `docs/reviews/tech-review.md` | Planning | Automated technical review |
| `docs/reviews/cross-review.md` | Implementation | Cross-review backend ↔ frontend |
| `apps/backend/*.py` | Coding | Generated backend source code |
| `apps/frontend/*` | Coding | Generated frontend source code |
| `apps/tests/*` | Coding | Generated test suite |
| `apps/Dockerfile.*`, `docker-compose.yml`, `.env.example` | Coding | DevOps & deployment files |
| `docs/state.json` | All phases | Serializable pipeline state for resumption |

The pipeline includes **iterative refinement**: plans are reviewed and regenerated until they meet quality thresholds. Human approval is required by default (with an optional `--auto-approve` flag for automated CI/CD runs).

---

## Project Structure

```
agents/
├── src/agents/
│   ├── main.py                       # Legacy entry point (simple 2-phase CLI)
│   ├── flow.py                       # Full SpecPipeline entry point
│   ├── state.py                      # Pydantic pipeline state model
│   ├── artifacts.py                  # Artifact path definitions
│   ├── quality.py                    # Scoring, thresholds, quality metrics
│   ├── config/
│   │   └── pipeline_config.py        # Pipeline configuration loader
│   ├── crews/
│   │   ├── planning_crew/            # Spec generation crew
│   │   │   ├── planning_crew.py
│   │   │   └── config/
│   │   │       ├── agents.yaml
│   │   │       └── tasks.yaml
│   │   ├── delivery_crew/            # Implementation + coding crews
│   │   │   ├── delivery_crew.py
│   │   │   └── config/
│   │   │       ├── agents.yaml
│   │   │       ├── tasks.yaml
│   │   │       ├── agents_code.yaml
│   │   │       └── tasks_code.yaml
│   │   ├── review_crew/              # Technical & cross-review crews
│   │   │   ├── review_crew.py
│   │   │   └── config/
│   │   │       ├── agents.yaml
│   │   │       └── tasks.yaml
│   │   ├── validation_crew/          # Automated validation crew
│   │   │   ├── validation_crew.py
│   │   │   └── (programmatic checks)
│   │   └── content_crew/             # Legacy content crew
│   │       ├── content_crew.py
│   │       └── config/
│   ├── tools/                        # Custom tools for agents
│   │   ├── common_tools.py           # YAML/JSON validation, search, counting
│   │   ├── file_tools.py             # File read/write/list/create
│   │   └── path_utils.py             # Sandboxed path resolution
│   └── review_parser.py              # Parse technical/cross-review outputs
├── tests/                            # 130 unit tests
│   ├── test_common_tools.py
│   ├── test_file_tools.py
│   ├── test_path_utils.py
│   ├── test_quality.py
│   ├── test_review_parser.py
│   ├── test_state.py
├── pyproject.toml                    # Project config & dependencies
├── Makefile                          # Dev commands (test, lint, format, etc.)
├── AGENTS.md                         # CrewAI reference for coding assistants
├── .env.example                      # Environment variable template
└── README.md                         # This file
```

---

## Quick Start

```bash
# 1. Install dependencies
cd agents
uv sync

# 2. Set your API key
export OPENAI_API_KEY="sk-..."
# or create a .env file:
echo 'OPENAI_API_KEY=sk-...' > .env

# 3. Run a simple project request
python -m agents.flow "Build a REST API for a blog platform"
```

---

## Installation

### Prerequisites

- **Python** >= 3.10, < 3.14
- **uv** package manager ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **OpenAI API key** (or any LiteLLM-compatible provider)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd orchestrator/agents

# Create virtual environment and install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

Create a `.env` file in `agents/` with:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional — override default model
OPENAI_MODEL_NAME=openai/gpt-5.4-mini

# Optional — use a different LiteLLM-compatible provider
LLM_PROVIDER=openai
MODEL=gpt-5.4-mini
```

Supported providers include OpenAI, Anthropic, Google Gemini, AWS Bedrock, Azure, Ollama, Groq, and 20+ others via LiteLLM routing.

---

## Usage

### Quick CLI (Legacy)

The original two-phase CLI (plan → approve → deliver). Simple, no state persistence.

```bash
# From the agents/ directory:

# Interactive approval (default)
uv run agent-team "Build a support ticket triage system"

# Auto-approve and run to completion
uv run agent-team --auto-approve "Build a support ticket triage system"

# Skip planning, run delivery only with an existing approved plan
uv run agent-team --delivery-only

# Use a custom plan file for delivery-only
uv run agent-team --delivery-only --plan-file docs/specs/my-plan.md
```

### Full Pipeline CLI

The new SpecPipeline (`python -m agents.flow`) provides a richer feature set, including state persistence, file-based workflows, resumption, and the full 10-phase pipeline.

```bash
# Basic usage — full pipeline with human approval
python -m agents.flow "Create a real-time chat application"

# Auto-approve everything (no human interaction)
python -m agents.flow "Create a real-time chat application" --auto-approve

# Read request from a file
python -m agents.flow --from-file requests/chat-app/request.md

# Read from file with auto-approve
python -m agents.flow --from-file requests/chat-app/request.md --auto-approve
```

### Interactive Mode

If no request argument is provided and `--from-file` is not used, the CLI prompts for multi-line input:

```bash
python -m agents.flow
# Enter your project request. Finish with an empty line:
# > Build a dashboard for monitoring server metrics
# > Include real-time WebSocket updates
# > [empty line to finish]
```

### File-Based Workflow

This is the recommended workflow for structured projects. Each project request lives in its own directory under `requests/`.

**Step 1: Create a request file**

```
requests/
└── blog-api/
    └── request.md    # Your project description in markdown
```

Write `requests/blog-api/request.md`:

```markdown
# Blog API

Build a REST API for a blog platform with the following features:
- CRUD operations for posts and comments
- JWT-based authentication
- PostgreSQL database
- OpenAPI documentation
```

**Step 2: Run the pipeline**

```bash
python -m agents.flow --from-file requests/blog-api/request.md
```

**Step 3: Approve the generated plan**

The pipeline will:
1. Analyze the request
2. Generate and review a specification iteratively
3. Present the plan and ask for approval (`[y/n/e]`)

```
Approve this plan? [y/n/e]:
```

- **`y`** — Approve and continue to implementation
- **`n`** — Reject and abort (or provide feedback for regeneration)
- **`e`** — Edit the plan externally. The plan is saved as `plan_vN.md` in the request directory. You edit it in your text editor, save, and press Enter. The edited version becomes the approved plan.

**After approval**, the pipeline proceeds through implementation, QA, validation, and code generation automatically.

### Resuming and Fixes

The pipeline saves its state to `docs/state.json` (or `requests/<project>/state.json`). If the pipeline is interrupted or you want to re-run specific phases:

```bash
# Resume a pipeline from where it left off
python -m agents.flow --continue requests/blog-api/

# Resume and apply fixes/improvements
python -m agents.flow --continue requests/blog-api/ --fixes requests/blog-api/fixes_1.md
```

The `--fixes` flag reads a markdown file with specific improvement instructions and passes them as feedback to the implementation and coding crews. This is useful for iterative refinement.

### Auto-Approve Mode

For CI/CD pipelines or fully automated runs:

```bash
python -m agents.flow "Build a user management service" --auto-approve
python -m agents.flow --from-file requests/my-project/request.md --auto-approve
```

With `--auto-approve`, the human approval phase is skipped, and the pipeline runs end-to-end without interaction.

---

## Pipeline Phases

The SpecPipeline runs through 10 phases in sequence:

| # | Phase | Description |
|---|---|---|
| 0 | **Analysis** | Validates input, no LLM — quick sanity check |
| 1 | **Planning** | Generates specification via Planning Crew, iterates with technical review until quality threshold is met |
| 2 | **Human Approval** | Presents the plan for human review. Supports approve / reject-with-feedback / edit-in-editor |
| 3 | **Implementation** | Generates backend + frontend plans via Delivery Crew, then runs cross-review between them |
| 4 | **QA & Architecture** | Collects QA report and architecture review produced by the delivery phase |
| 5 | **Validation** | Runs automated checks (file existence, required sections, markdown links, etc.) and computes final quality score |
| 6a | **Coding: Backend** | Generates backend source code under `apps/backend/` |
| 6b | **Coding: Frontend** | Generates frontend source code under `apps/frontend/` |
| 6c | **Coding: Tests** | Generates test suite under `apps/tests/` |
| 6d | **Coding: DevOps** | Generates Dockerfiles, docker-compose, .env.example, and README |

### Resumption Behavior

If a pipeline is resumed via `--continue`, it picks up from the last saved phase. This means:

- **Planning is done but not approved** → you'll be asked for approval again
- **Approved but code generation was interrupted** → coding phases will re-run
- **Fully completed** → all phases are skipped (state already complete)

---

## Artifacts Produced

All artifacts are saved under the `docs/` and `apps/` directories at the repository root.

### Documentation (`docs/`)

```
docs/
├── specs/
│   ├── pending-plan.md              # Draft specification (pre-approval)
│   └── latest-plan.md               # Approved specification (source of truth)
├── implementation/
│   ├── backend-plan.md              # Backend architecture & design
│   └── frontend-plan.md             # Frontend architecture & design
├── qa/
│   └── qa-report.md                 # QA review findings
├── architecture/
│   └── architecture-review.md       # Architecture review
├── reviews/
│   ├── tech-review.md               # Technical review of the plan
│   └── cross-review.md              # Cross-review backend ↔ frontend
└── state.json                       # Pipeline state (for resumption)
```

### Generated Code (`apps/`)

```
apps/
├── backend/                         # Generated backend Python code
│   ├── main.py
│   ├── models.py
│   ├── routes.py
│   └── ...
├── frontend/                        # Generated frontend code (React/Vue/etc.)
│   ├── src/
│   │   ├── App.tsx (or .vue, etc.)
│   │   ├── components/
│   │   └── ...
│   ├── package.json
│   └── ...
├── tests/                           # Generated test files
│   ├── test_backend.py
│   ├── test_frontend.py
│   └── ...
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── .env.example
```

---

## Crews Overview

SpecPipeline uses 5 specialized CrewAI crews:

### 1. Planning Crew (`planning_crew`)
- **Purpose**: Generate project specifications from user requests
- **Agents**: Product Manager, Senior Architect, Technical Writer
- **Input**: User request text (+ optional human feedback for regeneration)
- **Output**: Comprehensive specification document

### 2. Delivery Crew (`delivery_crew`)
- **Purpose**: Generate implementation plans and source code
- **Sub-teams**:
  - `build_delivery_crew()` — Backend + Frontend implementation plans
  - `build_coding_backend_crew()` — Backend source code generation
  - `build_coding_frontend_crew()` — Frontend source code generation
  - `build_coding_tests_crew()` — Test suite generation
  - `build_coding_devops_crew()` — Dockerfile, docker-compose, env, README generation
- **Input**: Approved specification, implementation plans
- **Output**: Implementation documents + source code files

### 3. Review Crew (`review_crew`)
- **Purpose**: Review artifacts for quality
- **Sub-teams**:
  - `build_tech_review_crew()` — Scores artifacts against quality criteria
  - `build_cross_review_crew()` — Cross-reviews backend ↔ frontend for API contract alignment
- **Input**: Artifact paths
- **Output**: Scored reviews with issues and suggestions

### 4. Validation Crew (`validation_crew`)
- **Purpose**: Automated programmatic checks
- **Checks**:
  - File existence validation
  - Required sections completeness
  - Markdown link validity
  - YAML/JSON validation
- **Input**: Artifact paths
- **Output**: `ValidationReport` with pass/fail per check

### 5. Content Crew (`content_crew`)
- **Purpose**: Legacy content generation crew (document writing)
- **Note**: Not actively used in the main pipeline; kept for backward compatibility

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Your OpenAI API key |
| `OPENAI_MODEL_NAME` | No | `gpt-4o` | Model name in `provider/model` format |
| `LLM_PROVIDER` | No | `openai` | LLM provider (openai, anthropic, google, etc.) |
| `MODEL` | No | `gpt-4o` | Fallback model name |

### Quality Thresholds

Quality thresholds are configured in `agents/src/agents/config/pipeline_config.py` and can be customized by creating the file `pipeline_thresholds.yaml` in the project root or a request directory.

Default thresholds:

| Parameter | Default | Description |
|---|---|---|
| `plan_review_score_threshold` | 7.0 | Min score (0-10) to approve a plan |
| `plan_max_iterations` | 3 | Max planning-review iterations |
| `overall_quality_threshold` | 60.0 | Min overall quality % to consider pipeline successful |
| `max_approval_rounds` | 3 | Max human rejection/feedback rounds |

---

## Development

### Makefile Commands

```bash
# Install dependencies
make install

# Run all 130 tests
make test

# Lint code
make lint

# Type check
make typecheck

# Lint + type check
make check

# Auto-format code
make format

# Clean build artifacts
make clean
```

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_state.py -v

# With coverage
python -m pytest tests/ -v --cov=src/agents
```

### Linting & Type Checking

```bash
# Ruff (linter + formatter)
python -m ruff check src/ tests/
python -m ruff format src/ tests/

# Mypy (type checking)
python -m mypy src/ --ignore-missing-imports
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        SpecPipeline                              │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌───────────────┐                │
│  │ Planning │──▶│  Human   │──▶│ Implementation │                │
│  │   Crew   │   │ Approval │   │    + Cross     │                │
│  └──────────┘   └──────────┘   │    Review      │                │
│       │                         └───────┬───────┘                │
│       ▼                                 ▼                        │
│  ┌──────────┐                    ┌────────────┐                  │
│  │  Review  │                    │  QA & Arch  │                  │
│  │   Crew   │                    └──────┬─────┘                  │
│  └──────────┘                           ▼                        │
│       │                          ┌────────────┐                  │
│       └──────── Loop ───────────▶│ Validation  │                  │
│       (until score ≥ threshold)  │    Crew     │                  │
│                                  └──────┬─────┘                  │
│                                         ▼                        │
│                                  ┌────────────┐                  │
│                                  │   Coding    │                  │
│                                  │  Backend    │                  │
│                                  │  Frontend   │                  │
│                                  │   Tests     │                  │
│                                  │  DevOps     │                  │
│                                  └────────────┘                  │
│                                                                  │
│  State: PipelineState (Pydantic) — serialized to state.json      │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **YAML-first configuration**: Agent roles, goals, backstories, and task descriptions are defined in YAML files, making them easy to modify without touching Python code.

2. **Isolated coding sub-phases**: Backend, frontend, tests, and DevOps code generation are separated into distinct phases. Each crew sees only the context relevant to its domain, preventing context pollution and enabling targeted fixes.

3. **Pydantic state model**: The entire pipeline state (`PipelineState`) is a Pydantic model that supports JSON serialization/deserialization. This enables:
   - Resuming interrupted runs
   - Inspecting state between phases
   - Applying fixes to specific phases

4. **Iterative review loop**: The planning phase doesn't just generate once — it reviews the output, scores it against criteria, and regenerates if quality falls below the threshold. This produces higher-quality specifications.

5. **Sandboxed file system**: Custom file tools restrict agent file access to `docs/` and `apps/` directories only, with path traversal prevention. Agents cannot read/write files outside these approved locations.

6. **Human-in-the-loop**: The approval phase supports three modes: approve as-is, reject with feedback (triggers regeneration), or edit externally (save to file, edit in your IDE, continue).

7. **Dual entry points**: The legacy `agent-team` CLI remains for backward compatibility, while the new `python -m agents.flow` provides the full pipeline with state persistence and file-based workflows.

---

## Requirements

- **Python**: >= 3.10, < 3.14
- **Package manager**: `uv` (recommended) or `pip`
- **API key**: OpenAI API key (or any LiteLLM-compatible provider)
- **Key dependencies**:
  - `crewai[litellm,tools]==1.14.2`
  - `litellm>=1.83.0`
  - `pydantic` (transitive via crewai)

---

## License

This project is private. Contact the repository owner for licensing details.