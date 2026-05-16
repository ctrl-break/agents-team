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
    CODING = "coding"
    CODING_BACKEND = "coding_backend"
    CODING_FRONTEND = "coding_frontend"
    CODING_TESTS = "coding_tests"
    CODING_DEVOPS = "coding_devops"


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


# ── Модели технологического стека и структуры проекта ────────────────────────


class TechStack(BaseModel):
    """Технологический стек, определяемый агентом на фазе планирования.

    Все поля — строки с разумными значениями по умолчанию.
    Агент спецификации обязан переопределить их на основе запроса пользователя.
    Если проект не требует какой-либо части (например, нет фронтенда),
    соответствующее поле остаётся пустой строкой.
    """

    # Backend
    backend_language: str = Field(
        default="python",
        description="Язык бэкенда (python, go, rust, typescript, java, ...)",
    )
    backend_framework: str = Field(
        default="fastapi",
        description="Фреймворк бэкенда (fastapi, django, gin, actix, express, ...)",
    )
    backend_package_manager: str = Field(
        default="pip",
        description="Менеджер пакетов бэкенда (pip, poetry, go modules, cargo, npm, ...)",
    )
    backend_build_tool: str = Field(
        default="",
        description="Инструмент сборки бэкенда, если применим (poetry, setuptools, ...)",
    )
    backend_test_framework: str = Field(
        default="pytest",
        description="Фреймворк тестирования бэкенда (pytest, unittest, go test, ...)",
    )

    # Frontend
    frontend_language: str = Field(
        default="typescript",
        description="Язык фронтенда (typescript, javascript, ...)",
    )
    frontend_framework: str = Field(
        default="react",
        description="Фреймворк/библиотека фронтенда (react, vue, svelte, angular, next, ...)",
    )
    frontend_build_tool: str = Field(
        default="vite",
        description="Инструмент сборки фронтенда (vite, webpack, turbopack, ...)",
    )
    frontend_css: str = Field(
        default="tailwind",
        description="CSS-подход (tailwind, css-modules, styled-components, vanilla, ...)",
    )
    frontend_router: str = Field(
        default="react-router",
        description="Роутер фронтенда, если SPA (react-router, vue-router, svelte-kit, ...)",
    )
    frontend_test_framework: str = Field(
        default="vitest",
        description="Фреймворк тестирования фронтенда (vitest, jest, playwright, cypress, ...)",
    )
    frontend_component_test_lib: str = Field(
        default="react-testing-library",
        description="Библиотека тестирования компонентов (react-testing-library, vue-test-utils, ...)",
    )

    # Database
    database: str = Field(
        default="postgresql",
        description="Основная база данных (postgresql, sqlite, mysql, mongodb, ...)",
    )
    orm: str = Field(
        default="sqlalchemy",
        description="ORM / data-access библиотека (sqlalchemy, prisma, typeorm, gorm, ...)",
    )
    migration_tool: str = Field(
        default="alembic",
        description="Инструмент миграций (alembic, prisma migrate, golang-migrate, ...)",
    )

    # DevOps
    container_runtime: str = Field(
        default="docker",
        description="Среда контейнеризации (docker, podman, ...)",
    )
    backend_server: str = Field(
        default="uvicorn",
        description="Сервер для бэкенда (uvicorn, gunicorn, node, ...)",
    )
    frontend_server: str = Field(
        default="nginx",
        description="Сервер для раздачи фронтенда (nginx, caddy, ...)",
    )
    ci_cd: str = Field(
        default="github-actions",
        description="CI/CD платформа (github-actions, gitlab-ci, ...)",
    )

    # E2E / integration
    e2e_framework: str = Field(
        default="playwright",
        description="E2E фреймворк (playwright, cypress, selenium, ...)",
    )

    @property
    def has_frontend(self) -> bool:
        """Требуется ли фронтенд."""
        return bool(self.frontend_framework.strip())

    @property
    def has_backend(self) -> bool:
        """Требуется ли бэкенд."""
        return bool(self.backend_language.strip())

    def to_context_string(self) -> str:
        """Форматирует стек в строку для подстановки в промпт агента."""
        lines = ["## Technology Stack (from approved specification)"]
        lines.append(f"- Backend: {self.backend_language} / {self.backend_framework}")
        if self.database:
            lines.append(f"- Database: {self.database} + {self.orm} ({self.migration_tool})")
        lines.append(f"- Backend tests: {self.backend_test_framework}")
        if self.has_frontend:
            lines.append(f"- Frontend: {self.frontend_language} / {self.frontend_framework}")
            lines.append(f"- Build tool: {self.frontend_build_tool}")
            lines.append(f"- CSS: {self.frontend_css}")
            if self.frontend_router:
                lines.append(f"- Router: {self.frontend_router}")
            lines.append(f"- Frontend tests: {self.frontend_test_framework} + {self.frontend_component_test_lib}")
        else:
            lines.append("- Frontend: NOT REQUIRED (no UI)")
        lines.append(f"- Containerization: {self.container_runtime}")
        lines.append(f"- Backend server: {self.backend_server}")
        if self.has_frontend:
            lines.append(f"- Frontend server: {self.frontend_server}")
        if self.e2e_framework:
            lines.append(f"- E2E: {self.e2e_framework}")
        return "\n".join(lines)


class DirectoryLayout(BaseModel):
    """Структура директорий, определяемая агентом на основе типа проекта.

    Позволяет поддерживать не только web-приложения,
    но и CLI-утилиты, библиотеки, мобильные приложения и т.д.
    """

    project_type: str = Field(
        default="web",
        description="Тип проекта: web, cli, library, mobile, desktop",
    )
    source_root: str = Field(
        default="apps",
        description="Корневая директория исходного кода",
    )
    backend_dir: str = Field(
        default="apps/backend",
        description="Путь к бэкенд-коду (может быть пустым)",
    )
    frontend_dir: str = Field(
        default="apps/frontend",
        description="Путь к фронтенд-коду (может быть пустым)",
    )
    test_dir: str = Field(
        default="apps/tests",
        description="Путь к тестам",
    )
    dockerfile_backend: str = Field(
        default="apps/Dockerfile.backend",
        description="Путь к Dockerfile бэкенда",
    )
    dockerfile_frontend: str = Field(
        default="apps/Dockerfile.frontend",
        description="Путь к Dockerfile фронтенда",
    )
    docker_compose: str = Field(
        default="apps/docker-compose.yml",
        description="Путь к docker-compose.yml",
    )
    env_example: str = Field(
        default="apps/.env.example",
        description="Путь к .env.example",
    )
    readme: str = Field(
        default="README.md",
        description="Путь к README.md",
    )

    @classmethod
    def for_cli(cls) -> "DirectoryLayout":
        """Предустановка для CLI-проектов."""
        return cls(
            project_type="cli",
            source_root="src",
            backend_dir="src",
            frontend_dir="",
            test_dir="tests",
            dockerfile_backend="Dockerfile",
            dockerfile_frontend="",
            docker_compose="",
            env_example=".env.example",
            readme="README.md",
        )

    @classmethod
    def for_library(cls) -> "DirectoryLayout":
        """Предустановка для библиотек."""
        return cls(
            project_type="library",
            source_root="src",
            backend_dir="src",
            frontend_dir="",
            test_dir="tests",
            dockerfile_backend="",
            dockerfile_frontend="",
            docker_compose="",
            env_example="",
            readme="README.md",
        )

    @property
    def has_frontend(self) -> bool:
        return bool(self.frontend_dir.strip())

    @property
    def has_backend(self) -> bool:
        return bool(self.backend_dir.strip())

    @property
    def has_docker(self) -> bool:
        return bool(self.dockerfile_backend.strip())


# ── Основное состояние пайплайна ─────────────────────────────────────────────


class PipelineState(BaseModel):
    """
    Состояние пайплайна SpecPipeline.

    Накапливает все промежуточные результаты по мере прохождения фаз.
    Может быть сериализовано/десериализовано (persist).
    """

    # ── Входные данные ──
    request: str = Field(default="", description="Исходный запрос пользователя")
    project_name: str = Field(
        default="", description="Человекочитаемое имя проекта (генерируется из запроса)"
    )
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

    # ── Технологический стек и структура (определяются на фазе Planning) ──
    tech_stack: TechStack = Field(default_factory=TechStack)
    directory_layout: DirectoryLayout = Field(default_factory=DirectoryLayout)

    # ── Phase 7: Coding ──
    backend_code_files: list[str] = Field(default_factory=list)
    frontend_code_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    devops_files: list[str] = Field(default_factory=list)
    code_summary: str = Field(default="")

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