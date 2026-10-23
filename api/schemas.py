"""Response models. Each is an explicit allow-list: nothing is added by dumping a source object."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class AppView(BaseModel):
    play_package: str
    play_lang: str
    play_country: str


class WeightsView(BaseModel):
    volume: float
    recency: float
    severity: float


class RankingView(BaseModel):
    weights: WeightsView
    recency_window_weeks: int


class PulseLimitsView(BaseModel):
    max_words: int
    min_reviews: int
    min_words: int
    max_analysed: int


class ModelsView(BaseModel):
    theme_assign: str | None
    compose: str | None
    judge: str | None


class ConfigView(BaseModel):
    app: AppView
    window_weeks: int
    max_themes: int
    taxonomy: list[str]
    ranking: RankingView
    pulse: PulseLimitsView
    models: ModelsView
    batch_size: int
    draft_to: str | None
    doc_url: str | None


class RunSummary(BaseModel):
    run_id: str
    week_label: str | None
    status: str
    started_at: str | None
    duration_s: float | None
    fetched: int | None
    clean: int | None
    analysed: int | None
    word_count: int | None
    has_pulse: bool
    doc_url: str | None
    draft_id: str | None
    is_dry_run: bool


class RunDetail(BaseModel):
    run: dict[str, Any] | None
    status: str
    pulse: Any | None
    note: str | None
    ranking: Any | None
    themes: Any | None
    file_errors: dict[str, str]


class ReviewRow(BaseModel):
    review_id: str
    rating: int | None
    title: str
    text: str
    date: str | None
    app_version: str | None
    theme_id: str | None


class ReviewPage(BaseModel):
    items: list[ReviewRow]
    total: int
    page: int
    page_size: int


class WeekBucket(BaseModel):
    week_start: str
    count: int
    avg_rating: float | None


class ThemeBucket(BaseModel):
    theme_id: str | None
    count: int
    avg_rating: float | None


class ReviewSummary(BaseModel):
    total: int
    rating: dict[str, int]
    weekly: list[WeekBucket]
    by_theme: list[ThemeBucket]


class StepView(BaseModel):
    """One ledger step. Only these keys are served; anything else in the file is dropped."""

    state: Literal["appended", "created", "pending"]
    run_id: str | None = None
    document_id: str | None = None
    revision_id: str | None = None
    characters_appended: int | None = None
    draft_id: str | None = None
    thread_id: str | None = None
    subject: str | None = None
    confirmed_by_hand: bool | None = None


class WeekView(BaseModel):
    doc: StepView | None
    draft: StepView | None


class LedgerView(BaseModel):
    weeks: dict[str, WeekView]
    error: Literal["ledger_unreadable"] | None


class StartRequest(BaseModel):
    """Body of POST /api/runs. Unknown fields (a CSV path, say) are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["play", "csv"]
    dry_run: bool = True
    as_of: date | None = None
    confirm: str | None = None

    @field_validator("as_of")
    @classmethod
    def _not_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("as_of cannot be in the future")
        return value

    @model_validator(mode="after")
    def _publishing_needs_confirmation(self) -> StartRequest:
        if not self.dry_run and self.confirm != "publish":
            raise ValueError('a real run needs confirm: "publish"')
        return self


class StartResponse(BaseModel):
    pid: int
    started_at: str


class ActiveRun(BaseModel):
    active: bool
    elapsed_s: float | None
    last_line: str | None
    started_by_api: bool
    exit_code: int | None
    exit_message: str | None
    new_run_id: str | None
    stderr_tail: list[str]
