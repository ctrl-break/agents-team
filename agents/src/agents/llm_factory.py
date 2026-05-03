"""Centralised LLM factory — reads config or env, returns a configured LLM."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from crewai import LLM

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "pipeline.yaml"


def _load_pipeline_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def build_llm(
    model: Optional[str] = None,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> LLM:
    """
    Build a CrewAI LLM instance.

    Resolution order:
    1. Explicit arguments
    2. OPENAI_MODEL_NAME / MODEL env vars
    3. pipeline.yaml → llm section
    4. Fallback: openai/gpt-4o
    """
    cfg = _load_pipeline_config().get("llm", {})

    model_name = (
        model
        or os.getenv("OPENAI_MODEL_NAME")
        or os.getenv("MODEL")
        or cfg.get("model", "openai/gpt-4o")
    )

    # Normalise — ensure provider prefix
    if "/" not in model_name:
        provider = os.getenv("LLM_PROVIDER", "openai")
        model_name = f"{provider}/{model_name}"

    tokens = (
        max_completion_tokens
        if max_completion_tokens is not None
        else cfg.get("max_completion_tokens", 4000)
    )
    temp = (
        temperature
        if temperature is not None
        else cfg.get("temperature", 0.3)
    )

    return LLM(model=model_name, max_completion_tokens=tokens, temperature=temp)