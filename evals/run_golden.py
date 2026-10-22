"""Run the golden-set evals end to end against the live model (architecture section 8.2).

    python evals/run_golden.py                       # full run, with the advisory judge
    python evals/run_golden.py --no-judge            # deterministic checks only
    python evals/run_golden.py --use-cache           # reuse cached theme assignments (fast, but
                                                     # does not exercise the theme prompt)
    python evals/run_golden.py --degrade theme_assign   # swap in a deliberately bad prompt; the
                                                     # run must FAIL, proving the evals can
    python evals/run_golden.py --save-baseline       # record this run as evals/baseline.json

Runs the same pipeline as `python -m pulse run --dry-run` on the fixture reviews in a fresh data
directory, then applies the deterministic checks to the files it wrote. The exit code is 1 if any
deterministic check fails. The judge is advisory and never changes the exit code. Results are saved
under evals/results/, named by prompt version.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sys
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `evals` imports from anywhere

from evals.checks import Artifacts, CheckResult, Thresholds, run_checks  # noqa: E402
from evals.golden import FIXTURES, GoldenSet  # noqa: E402
from evals.judge import JudgeResult, judge_pulse  # noqa: E402
from pulse.config import DEFAULT_CONFIG_PATH, ConfigError, load_config  # noqa: E402
from pulse.llm import LLMError  # noqa: E402
from pulse.pipeline import build_llm, run_pipeline  # noqa: E402
from pulse.prompts import PromptError, load_prompt  # noqa: E402
from pulse.sources.csv_source import CsvSource  # noqa: E402

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"
BASELINE_PATH = EVALS_DIR / "baseline.json"
THRESHOLDS_PATH = EVALS_DIR / "thresholds.yaml"
DEGRADED_DIR = EVALS_DIR / "degraded"
DEFAULT_AS_OF = "2026-10-19"  # the fixture's window ends here


def load_thresholds(config_max_words: int, config_max_themes: int) -> Thresholds:
    raw = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")) or {}
    return Thresholds(
        theme_agreement_min=float(raw["theme_agreement_min"]),
        max_words=config_max_words,
        max_themes=config_max_themes,
    )


def build_prompts_dir(target: Path, repo_prompts: Path, degrade: list[str]) -> None:
    """The prompts the run will use: the real ones, with any `--degrade` names swapped out."""
    for path in repo_prompts.glob("*.md"):
        shutil.copy(path, target / path.name)
    for name in degrade:
        source = DEGRADED_DIR / f"{name}.md"
        if not source.is_file():
            raise PromptError(f"No degraded prompt for '{name}' (looked for {source})")
        shutil.copy(source, target / source.name)


def format_table(results: list[CheckResult]) -> str:
    rows = [("", "check", "measured", "target")]
    rows += [("PASS" if r.passed else "FAIL", r.name, r.value, r.target) for r in results]
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def baseline_note(judge: JudgeResult | None) -> str:
    if judge is None or not BASELINE_PATH.is_file():
        return ""
    base = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("judge")
    if not base:
        return ""
    parts = [f"{c} {s} ({s - base['scores'][c]:+d})" for c, s in judge.scores.items()]
    return "vs baseline: " + ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    degradable = sorted(p.stem for p in DEGRADED_DIR.glob("*.md"))
    parser.add_argument("--degrade", action="append", default=[], choices=degradable)
    parser.add_argument("--save-baseline", action="store_true")
    args = parser.parse_args(argv)

    if args.save_baseline and args.degrade:
        print("Refusing to save a degraded run as the baseline.", file=sys.stderr)
        return 2

    load_dotenv()
    started = time.perf_counter()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        config = load_config(args.config)
        thresholds = load_thresholds(config.max_words, config.max_themes)
        llm = build_llm(config)
        golden = GoldenSet.load()
    except (ConfigError, LLMError, OSError, KeyError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 2

    data_dir = Path(config.data_dir) / "evals" / stamp
    if args.use_cache:
        cache = Path(config.data_dir) / "cache" / "theme_assignments.json"
        if cache.is_file():
            (data_dir / "cache").mkdir(parents=True, exist_ok=True)
            shutil.copy(cache, data_dir / "cache" / cache.name)

    with tempfile.TemporaryDirectory() as tmp:
        prompts_dir = Path(tmp)
        try:
            build_prompts_dir(prompts_dir, config.prompts_dir, args.degrade)
            eval_config = dataclasses.replace(config, data_dir=data_dir, prompts_dir=prompts_dir)
            result = run_pipeline(
                source=CsvSource(FIXTURES / "reviews.csv"),
                config=eval_config,
                llm=llm,
                as_of=date.fromisoformat(args.as_of),
            )
            judge_prompt = load_prompt("judge", prompts_dir)
        except (LLMError, PromptError, OSError, ValueError) as exc:
            print(f"Pipeline could not run: {exc}", file=sys.stderr)
            return 2

        artifacts = Artifacts.load(result.run_dir)
        checks = run_checks(artifacts, golden, thresholds)

        judge: JudgeResult | None = None
        if not args.no_judge:
            try:
                judge = judge_pulse(llm, judge_prompt, artifacts)
            except LLMError as exc:  # advisory: report it, never fail the run for it
                print(f"(judge unavailable: {exc})", file=sys.stderr)

    versions = "+".join(sorted(artifacts.run.get("prompt_versions", {}).values()))
    if judge:
        versions += f"+{judge.prompt_version}"
    failed = [c for c in checks if not c.passed]
    elapsed = round(time.perf_counter() - started, 1)

    print(f"Golden-set evals  |  prompts: {versions}  |  run {artifacts.run.get('run_id')}")
    if args.degrade:
        print(f"DEGRADED on purpose: {', '.join(args.degrade)} (this run is expected to fail)")
    print()
    print(format_table(checks))
    for c in checks:
        if c.detail and not c.passed:
            print(f"  - {c.name}: {c.detail}")
    if judge:
        scores = ", ".join(f"{k} {v}/5" for k, v in judge.scores.items())
        print(f"\nJudge (advisory): {scores}")
        note = baseline_note(judge)
        if note:
            print(f"                  {note}")
    retries = artifacts.run.get("retries", 0)
    if retries:
        print(f"Compose needed {retries} retr{'y' if retries == 1 else 'ies'} (advisory)")
    usage = {k: dict(v) for k, v in llm.usage.items()}
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed in {elapsed}s")

    report = {
        "timestamp": stamp,
        "prompt_versions": artifacts.run.get("prompt_versions", {}),
        "judge_prompt": judge.prompt_version if judge else None,
        "models": config.models,
        "degraded": args.degrade,
        "as_of": args.as_of,
        "run_id": artifacts.run.get("run_id"),
        "passed": not failed,
        "checks": [dataclasses.asdict(c) for c in checks],
        "judge": dataclasses.asdict(judge) if judge else None,
        "thresholds": dataclasses.asdict(thresholds),
        "compose_retries": retries,
        "llm_usage": usage,
        "elapsed_s": elapsed,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    tag = "DEGRADED_" if args.degrade else ""
    out = RESULTS_DIR / f"{tag}{versions.replace('+', '_').replace('@', '')}__{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {out.relative_to(EVALS_DIR.parent)}")
    if args.save_baseline:
        if failed:
            print("Not saving a baseline from a failing run.", file=sys.stderr)
        else:
            BASELINE_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Baseline saved to {BASELINE_PATH.relative_to(EVALS_DIR.parent)}")

    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
