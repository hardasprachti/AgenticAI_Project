"""The analysis pipeline: reviews in, validated note out (architecture section 3, stages 1-6).

This is the offline path used by `--dry-run`: it never touches Google. Each stage's output is
written to `data/runs/<run_id>/` so a run can be inspected afterwards. Publishing, the draft, the
ledger and `--resume` arrive with the orchestrator in later phases.

Nothing written here contains reviewer identity: reviews are sanitized before the first file is
written, and the author names seen in the raw data stay in memory only (for the final PII check).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pulse.compose import ComposeFailed, compose_pulse
from pulse.config import Config
from pulse.llm import GroqLLM, LLMClient
from pulse.models import Pulse, Run, RunStatus, StageRecord, to_jsonable
from pulse.prompts import load_prompt
from pulse.ranking import InsufficientThemes, rank_themes, top_themes
from pulse.render import count_words, render_note
from pulse.sanitize import sanitize_reviews
from pulse.sources.base import ReviewSource
from pulse.theming import AssignmentCache, assign_themes, taxonomy_hash


class PipelineError(RuntimeError):
    """The run cannot produce a note (too few reviews, no themes, ...). Nothing was published."""


@dataclass
class PipelineResult:
    run: Run
    run_dir: Path
    pulse: Pulse | None = None
    note: str | None = None


def week_label_for(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )


class _Stages:
    """Times each stage and appends its record to the run."""

    def __init__(self, run: Run) -> None:
        self._run = run
        self._t0: dict[str, float] = {}

    def start(self, name: str) -> StageRecord:
        record = StageRecord(name=name)
        self._t0[name] = time.perf_counter()
        self._run.stages.append(record)
        return record

    def finish(self, record: StageRecord, **counts: int) -> None:
        record.duration_s = round(time.perf_counter() - self._t0[record.name], 3)
        record.counts.update(counts)


def run_pipeline(
    *,
    source: ReviewSource,
    config: Config,
    llm: LLMClient,
    as_of: date,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PipelineResult:
    started = now()
    run_id = f"{as_of:%Y%m%d}-{started:%H%M%S}"
    run_dir = config.data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run = Run(run_id=run_id, week_label=week_label_for(as_of), started_at=started)
    result = PipelineResult(run=run, run_dir=run_dir)
    stages = _Stages(run)

    theme_prompt = load_prompt("theme_assign", config.prompts_dir)
    compose_prompt = load_prompt("compose", config.prompts_dir)
    run.prompt_versions = {"theme_assign": theme_prompt.version, "compose": compose_prompt.version}

    def finish(status: RunStatus) -> PipelineResult:
        run.status = status
        usage = getattr(llm, "usage", None)
        run.llm_usage = {k: dict(v) for k, v in usage.items()} if usage else {}
        _write_json(run_dir / "run.json", run)
        return result

    try:
        # 1. Ingest
        record = stages.start("ingest")
        since = as_of - timedelta(weeks=config.window_weeks)
        raw = source.fetch(since, as_of)
        stages.finish(record, fetched=len(raw))

        # 2. Sanitize: the PII boundary. `raw` is not used after this point.
        record = stages.start("sanitize")
        sanitized = sanitize_reviews(raw)
        del raw
        reviews = sanitized.reviews
        stages.finish(record, **sanitized.stats.as_counts())
        _write_json(run_dir / "sanitized.json", reviews)
        if len(reviews) < config.min_reviews:
            raise PipelineError(
                f"Only {len(reviews)} usable reviews in {since} to {as_of}; "
                f"at least {config.min_reviews} are needed for a meaningful pulse."
            )

        # 3. Theme
        record = stages.start("theme")
        model = config.models.get("theme_assign", "")
        cache = AssignmentCache(
            config.data_dir / "cache" / "theme_assignments.json",
            taxonomy_hash(config.taxonomy, theme_prompt.version, model),
        )
        theming = assign_themes(
            reviews,
            config.taxonomy,
            llm=llm,
            prompt=theme_prompt,
            model=model,
            batch_size=config.llm.batch_size,
            max_themes=config.max_themes,
            cache=cache,
        )
        stages.finish(
            record,
            themes=len(theming.themes),
            llm_calls=theming.stats.llm_calls,
            cache_hits=theming.stats.cache_hits,
            unknown_labels=theming.stats.unknown_labels,
            unlabeled_defaulted=theming.stats.missing_after_retry,
        )
        if theming.stats.merged_into_other:
            record.notes.append(f"merged into Other: {', '.join(theming.stats.merged_into_other)}")
        _write_json(
            run_dir / "themes.json",
            {"themes": theming.themes, "assignments": theming.assignments},
        )

        # 4. Rank
        record = stages.start("rank")
        ranked = rank_themes(reviews, theming.assignments, theming.themes, config.ranking, as_of)
        top = top_themes(ranked)
        stages.finish(record, ranked=len(ranked), selected=len(top))
        run.theme_scores = {
            t.theme_id: {
                **t.components,
                "score": t.score,
                "review_count": t.review_count,
                "avg_rating": t.avg_rating,
            }
            for t in ranked
        }
        _write_json(run_dir / "ranking.json", {"ranked": ranked, "top": [t.theme_id for t in top]})

        # 5. Compose, which includes 6. Validate (retrying with violation feedback)
        record = stages.start("compose")
        try:
            composed = compose_pulse(
                llm=llm,
                prompt=compose_prompt,
                top=top,
                reviews=reviews,
                assignments=theming.assignments,
                week_label=run.week_label,
                window_start=since,
                window_end=as_of,
                candidates_per_theme=config.compose.candidates_per_theme,
                max_retries=config.compose.max_retries,
                max_words=config.max_words,
                known_author_names=sanitized.known_author_names,
            )
        except ComposeFailed as exc:
            stages.finish(record, attempts=exc.attempts)
            run.retries = exc.attempts - 1
            run.violations = [line for attempt in exc.violation_history for line in attempt]
            return finish(RunStatus.FAILED_VALIDATION)
        stages.finish(record, attempts=composed.attempts)
        run.retries = composed.attempts - 1
        run.violations = [line for attempt in composed.violation_history for line in attempt]

        # 7. Render (the text that was validated is the text that gets written)
        record = stages.start("render")
        note = render_note(composed.pulse)
        run.word_count = count_words(note)
        stages.finish(record, words=run.word_count)
        _write_json(run_dir / "pulse.json", composed.pulse)
        (run_dir / "note.txt").write_text(note, encoding="utf-8")

        result.pulse, result.note = composed.pulse, note
        return finish(RunStatus.COMPLETED)

    except (PipelineError, InsufficientThemes) as exc:
        run.violations.append(str(exc))
        return finish(RunStatus.FAILED)
    except Exception as exc:
        # Unexpected failure (LLM down, bad source file): keep the record, then let it surface.
        run.violations.append(f"{type(exc).__name__}: {exc}")
        finish(RunStatus.FAILED)
        raise


def build_llm(config: Config) -> GroqLLM:
    """The real model client, configured from config.yaml and the environment."""
    return GroqLLM(config.models, config.llm)
