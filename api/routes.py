"""HTTP routes. Everything here is read-only except the run control added in a later task."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field

from api.controller import RunConflict, RunStartError
from api.ledger_view import read_ledger
from api.reviews import ReviewFilters, get_reviews, get_summary
from api.runs import get_run, list_runs
from api.safe_paths import RunNotFound
from api.schemas import (
    ActiveRun,
    AppView,
    ConfigView,
    LedgerView,
    ModelsView,
    PulseLimitsView,
    RankingView,
    ReviewPage,
    ReviewSummary,
    RunDetail,
    RunSummary,
    StartRequest,
    StartResponse,
    WeightsView,
)
from api.settings import Settings

router = APIRouter(prefix="/api")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def active_run_id(request: Request) -> str | None:
    """The run the API itself started, if any (set once the run controller exists)."""
    controller = getattr(request.app.state, "controller", None)
    return getattr(controller, "active_run_id", None)


def build_config_view(settings: Settings) -> ConfigView:
    """Built field by field: Config (server_dir, `raw`) is never dumped."""
    cfg = settings.config
    document_id = cfg.mcp.document_id
    return ConfigView(
        app=AppView(
            play_package=cfg.app.play_package,
            play_lang=cfg.app.play_lang,
            play_country=cfg.app.play_country,
        ),
        window_weeks=cfg.window_weeks,
        max_themes=cfg.max_themes,
        taxonomy=list(cfg.taxonomy),
        ranking=RankingView(
            weights=WeightsView(
                volume=cfg.ranking.volume,
                recency=cfg.ranking.recency,
                severity=cfg.ranking.severity,
            ),
            recency_window_weeks=cfg.ranking.recency_window_weeks,
        ),
        pulse=PulseLimitsView(
            max_words=cfg.max_words,
            min_reviews=cfg.min_reviews,
            min_words=cfg.min_words,
            max_analysed=cfg.max_analysed,
        ),
        models=ModelsView(
            theme_assign=cfg.models.get("theme_assign"),
            compose=cfg.models.get("compose"),
            judge=cfg.models.get("judge"),
        ),
        batch_size=cfg.llm.batch_size,
        draft_to=cfg.draft_to,
        doc_url=f"https://docs.google.com/document/d/{document_id}/edit" if document_id else None,
    )


@router.get("/config", response_model=ConfigView)
def get_config(request: Request) -> ConfigView:
    return build_config_view(get_settings(request))


@router.get("/runs", response_model=list[RunSummary])
def get_runs(request: Request) -> list[RunSummary]:
    return list_runs(get_settings(request), active_run_id(request), time.time())


@router.post("/runs", response_model=StartResponse)
def start_run(body: StartRequest, request: Request) -> StartResponse:
    try:
        return request.app.state.controller.start(body)
    except RunConflict:
        raise HTTPException(status_code=409, detail="A run is already in progress") from None
    except RunStartError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None


# Declared before /runs/{run_id}, which would otherwise take "active" as a run id.
@router.get("/runs/active", response_model=ActiveRun)
def get_active_run(request: Request) -> ActiveRun:
    return request.app.state.controller.active()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run_detail(run_id: str, request: Request) -> RunDetail:
    try:
        return get_run(get_settings(request), run_id, active_run_id(request), time.time())
    except RunNotFound:
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.get("/runs/{run_id}/reviews", response_model=ReviewPage)
def get_run_reviews(
    run_id: str,
    request: Request,
    theme: Annotated[list[str] | None, Query()] = None,
    rating: Annotated[list[Annotated[int, Field(ge=1, le=5)]] | None, Query()] = None,
    review_id: Annotated[list[str] | None, Query()] = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ReviewPage:
    filters = ReviewFilters(
        themes=theme or [], ratings=rating or [], review_ids=review_id or [], q=q
    )
    try:
        return get_reviews(get_settings(request), run_id, filters, page, page_size)
    except RunNotFound:
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.get("/runs/{run_id}/reviews/summary", response_model=ReviewSummary)
def get_run_reviews_summary(run_id: str, request: Request) -> ReviewSummary:
    try:
        return get_summary(get_settings(request), run_id)
    except RunNotFound:
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.get("/ledger", response_model=LedgerView)
def get_ledger(request: Request) -> LedgerView:
    return read_ledger(get_settings(request))
