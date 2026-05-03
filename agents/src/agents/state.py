"""
PipelineState — Pydantic-модель состояния всего пайплайна.

Отражает прогресс по фазам, результаты итераций, метрики качества.
Используется как параметризованный тип для CrewAI Flow[PipelineState].
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class Phase(str, Enum):
    """Фазы пайплайна."""

    ANALYSIS = "analysis"
    PLANNING = "planning"
    HUMAN_APPROVAL = "human_approval"
    IMPLEMENTATION = "implementation"
    QA_ARCHITECTURE = "qa_architecture"
    VALIDATION = "validation"
    DELIVERY = "delivery"


class ReviewDecision(str, Enum):
    """Решение по результатам ревью."""

    APPROVED = "approved"
    REVISIONS_NEEDED = "revisions_needed"
    REJECTED = "rejected"


# ── Вспомогательные модели ───────────────────────────────────────────────────


class IterationResult(BaseModel):
    """Результат одной итерации + ревью."""

    iteration: int = Field(..., ge=1, description="Номер итерации (с 1)")
    output: str = Field(..., description="Сгенерированный текст артефакта")
    score: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Оценка ревью (0-10)"
    )
    criteria_scores: dict[str, float] = Field(
        default_factory=dict, description="Оценки по отдельным критериям"
    )
    issues: list[str] = Field(
        default_factory=list, description="Найденные проблемы"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Предложения по улучшению"
    )
    decision: ReviewDecision = Field(
        default=ReviewDecision.REVISIONS_NEEDED,
        description="Решение по данной итерации",
    )


class CrossReviewResult(BaseModel):
    """Результат перекрёстного ревью Backend ↔ Frontend."""

    backend_review_of_frontend: str = Field(
        default="", description="Замечания Backend Engineer к Frontend-плану"
    )
    frontend_review_of_backend: str = Field(
        default="", description="Замечания Frontend Engineer к Backend-плану"
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Обнаруженные расхождения в API-контрактах",
    )
    resolved: bool = Field(
        default=False, description="Все конфликты разрешены"
    )


class ValidationCheck(BaseModel):
    """Результат одной автоматической проверки."""

    name: str = Field(..., description="Название проверки")
    passed: bool = Field(default=False, description="Пройдена?")
    details: str = Field(default="", description="Детали / причина провала")


class ValidationReport(BaseModel):
    """Сводка автоматической валидации."""

    checks: list[ValidationCheck] = Field(default_factory=list)
    total: int = Field(default=0)
    passed: int = Field(default=0)
    failed: int = Field(default=0)
    score_pct: float = Field(default=0.0)

    @classmethod
    def from_checks(cls, checks: list[ValidationCheck]) -> "ValidationReport":
        """Create a ValidationReport from a list of checks, computing aggregate stats."""
        total = len(checks)
        passed_count = sum(1 for c in checks if c.passed)
        failed_count = total - passed_count
        score = 100.0 if total == 0 else round((passed_count / total) * 100.0, 1)
        return cls(
            checks=checks,
            total=total,
            passed=passed_count,
            failed=failed_count,
            score_pct=score,
        )

    @property
    def is_clean(self) -> bool:
        return self.failed == 0

    @property
    def all_passed(self) -> bool:
        """True if there are no failed checks."""
        return self.failed == 0

    @property
    def passed_pct(self) -> float:
        """Percentage of checks that passed."""
        return self.score_pct

    def failing_names(self) -> list[str]:
        """Return names of all failing checks."""
        return [c.name for c in self.checks if not c.passed]


class QualitySummary(BaseModel):
    """Финальная сводка качества."""

    plan_iterations: int = Field(
        default=0, description="Потребовалось итераций планирования"
    )
    final_review_score: float = Field(default=0.0, ge=0.0, le=10.0)
    cross_review_issues: int = Field(default=0)
    qa_coverage_pct: float = Field(default=0.0)
    broken_links: int = Field(default=0)
    sections_complete: int = Field(default=0)
    sections_expected: int = Field(default=0)
    overall_score_pct: float = Field(default=0.0)
    passed: bool = Field(default=False)


# ── Основное состояние пайплайна ─────────────────────────────────────────────


class PipelineState(BaseModel):
    """
    Состояние пайплайна SpecPipeline.

    Накапливает все промежуточные результаты по мере прохождения фаз.
    Может быть сериализовано/десериализовано (persist).
    """

    # ── Входные данные ──
    request: str = Field(default="", description="Исходный запрос пользователя")
    auto_approve: bool = Field(
        default=False, description="Автоодобрение всех гейтов"
    )

    # ── Текущая фаза ──
    current_phase: Phase = Field(
        default=Phase.ANALYSIS, description="Текущая активная фаза"
    )

    # ── Phase 0: Analysis ──
    analysis_brief: str = Field(default="")
    clarifications: list[str] = Field(default_factory=list)

    # ── Phase 1: Planning ──
    plan_iterations: list[IterationResult] = Field(default_factory=list)
    approved_spec: str = Field(default="")

    # ── Phase 2: Human Approval ──
    human_feedback: str = Field(
        default="", description="Комментарий человека при отклонении"
    )
    approval_rounds: int = Field(
        default=0, description="Сколько раз человек отправлял на доработку"
    )

    # ── Phase 3: Implementation ──
    backend_plan: str = Field(default="")
    frontend_plan: str = Field(default="")
    backend_iterations: list[IterationResult] = Field(default_factory=list)
    frontend_iterations: list[IterationResult] = Field(default_factory=list)
    cross_review: CrossReviewResult = Field(default_factory=CrossReviewResult)

    # ── Phase 4: QA & Architecture ──
    qa_report: str = Field(default="")
    architecture_review: str = Field(default="")

    # ── Phase 5: Validation ──
    validation: ValidationReport = Field(default_factory=ValidationReport)

    # ── Phase 6: Delivery ──
    quality: QualitySummary = Field(default_factory=QualitySummary)
    delivery_summary: str = Field(default="")

    # ── Мета ──
    errors: list[str] = Field(
        default_factory=list, description="Накопленные ошибки"
    )
    started_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)

    # ── Удобные свойства ──

    @property
    def latest_plan_score(self) -> float:
        """Оценка последней итерации планирования (или 0)."""
        if self.plan_iterations:
            return self.plan_iterations[-1].score
        return 0.0

    @property
    def latest_plan_issues(self) -> list[str]:
        """Проблемы последней итерации планирования."""
        if self.plan_iterations:
            return self.plan_iterations[-1].issues
        return []

    @property
    def is_plan_approved(self) -> bool:
        """Утверждён ли план."""
        return bool(self.approved_spec.strip())

    @property
    def has_errors(self) -> bool:
        """Были ли ошибки."""
        return len(self.errors) > 0