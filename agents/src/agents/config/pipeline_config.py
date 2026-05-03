"""Load pipeline configuration from pipeline.yaml and produce PipelineThresholds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agents.quality import PipelineThresholds

_DEFAULT_PATH = Path(__file__).resolve().parent / "pipeline.yaml"


def _load_raw(path: Path | None = None) -> dict[str, Any]:
    """Load raw YAML config."""
    path = path or _DEFAULT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_pipeline_config(path: Path | None = None) -> PipelineThresholds:
    """
    Load pipeline configuration from YAML and return PipelineThresholds.

    Args:
        path: Optional path to pipeline.yaml. Uses default if not provided.

    Returns:
        PipelineThresholds instance populated from the YAML config.
    """
    raw = _load_raw(path)

    planning = raw.get("phases", {}).get("planning", {})
    human = raw.get("phases", {}).get("human_approval", {})
    implementation = raw.get("phases", {}).get("implementation", {})
    cross_review = raw.get("phases", {}).get("cross_review", {})
    validation = raw.get("phases", {}).get("validation", {})
    errors = raw.get("errors", {})

    return PipelineThresholds(
        plan_max_iterations=planning.get("iterations", 3),
        plan_review_score_threshold=planning.get("review_score_threshold", 7.0),
        max_approval_rounds=human.get("max_rounds", 3),
        impl_max_iterations=max(
            implementation.get("backend_iterations", 2),
            implementation.get("frontend_iterations", 2),
        ),
        impl_review_score_threshold=implementation.get("review_score_threshold", 7.0),
        cross_review_max_iterations=cross_review.get("max_iterations", 2),
        final_quality_threshold_pct=validation.get("quality_threshold_pct", 85.0),
        qa_min_coverage_pct=validation.get("qa_min_coverage_pct", 80.0),
        max_errors_before_abort=errors.get("max_before_abort", 5),
    )


def load_llm_config(path: Path | None = None) -> dict[str, Any]:
    """Extract LLM configuration from pipeline.yaml.

    Returns dict with keys: model, max_completion_tokens, temperature, verbose.
    """
    raw = _load_raw(path)
    llm_block = raw.get("llm", {})
    return {
        "model": llm_block.get("model", "gpt-4o"),
        "max_completion_tokens": llm_block.get("max_completion_tokens", 4000),
        "temperature": llm_block.get("temperature", 0.3),
        "verbose": llm_block.get("verbose", False),
    }


def load_scoring_config(path: Path | None = None) -> dict[str, Any]:
    """Extract scoring criteria from pipeline.yaml.

    Returns dict with keys: plan_review, implementation_review.
    Each contains a list of criterion dicts with key, label, description, weight.
    """
    raw = _load_raw(path)
    return raw.get("scoring", {})


def is_phase_enabled(phase_name: str, path: Path | None = None) -> bool:
    """Check if a specific phase is enabled in the pipeline config.

    Args:
        phase_name: e.g. 'analysis', 'planning', 'human_approval', etc.
        path: Optional path to pipeline.yaml.

    Returns:
        True if the phase is enabled, False otherwise.
    """
    raw = _load_raw(path)
    return raw.get("phases", {}).get(phase_name, {}).get("enabled", True)