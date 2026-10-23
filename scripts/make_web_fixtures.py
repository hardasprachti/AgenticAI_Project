"""Build web/fixtures/ from real run folders under data/runs/.

    python scripts/make_web_fixtures.py [--out web/fixtures]

Copies only the files the dashboard API serves (never the downloaded-review cache), trims the
analysed sample to 150 reviews, drops the one note that names a filesystem path, and swaps the
two personal values in the config view (recipient address, Google Doc id) for placeholders.
Everything is read and written as UTF-8: the reviews hold rupee signs, Hinglish and emoji.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

SUCCESS_RUN = "20261022-121514"
FAILED_RUN = "20261022-151338"
SAMPLE_SIZE = 150

# Same patterns the fixture test uses: a review that matches either is never sampled.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")

PLACEHOLDER_DRAFT_TO = "product-leads@example.com"
PLACEHOLDER_DOC_URL = "https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit"

# Synthetic, in the real ledger format (Ledger.entry / architecture 4.7). One week is complete and
# one has its draft left `pending`, so the "check the Drafts folder" banner shows in mock mode.
SYNTHETIC_LEDGER = {
    "2026-W38": {
        "doc": {
            "state": "appended",
            "run_id": "20260917-090012",
            "document_id": "EXAMPLE_DOCUMENT_ID",
            "revision_id": "rev_sample_38",
            "characters_appended": 1180,
        },
        "draft": {
            "state": "created",
            "run_id": "20260917-090012",
            "draft_id": "draft_sample_38",
            "thread_id": "thread_sample_38",
            "subject": "Groww Weekly Review Pulse - 2026-W38",
        },
    },
    "2026-W39": {
        "doc": {
            "state": "appended",
            "run_id": "20260924-090009",
            "document_id": "EXAMPLE_DOCUMENT_ID",
            "revision_id": "rev_sample_39",
            "characters_appended": 1254,
        },
        "draft": {"state": "pending", "run_id": "20260924-090009"},
    },
}

README = """# Web fixtures

Real files from two runs under `data/runs/`, used by mock mode (`npm run dev:mock`) and the web
tests. Regenerate with `python scripts/make_web_fixtures.py`.

| Path | Source |
| --- | --- |
| `runs/20261022-121514/` | A completed dry run: `run.json`, `pulse.json`, `note.txt`, `ranking.json`, `themes.json`, `sanitized.json` |
| `runs/20261022-151338/` | A failed run (Groq daily token limit): `run.json`, `sanitized.json` |
| `config.json` | The `GET /api/config` view of `config.yaml` |
| `ledger.json` | **Synthetic.** Not from a real ledger; the real `data/ledger.json` does not exist yet. It uses the real format and has one `pending` draft (2026-W39) so the banner is visible in mock mode. |

What was changed from the real files:

- `sanitized.json` is trimmed to 150 reviews: the three quoted reviews plus an even spread of the
  rest. `themes.json` assignments are filtered to the same ids. **Mock explorer totals (150)
  therefore differ from the run's `analysed` count (500).** Reviews that look like they contain an
  email address or a 10-digit number are never sampled.
- The ingest stage's cache-location note is removed (it is a filesystem path).
- `config.json` has a placeholder recipient (`product-leads@example.com`) and Doc id
  (`EXAMPLE_DOCUMENT_ID`) in place of the real ones.
- Nothing is copied from the downloaded-review cache; no reviewer names, emails or device data are present.
"""  # noqa: E501


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _is_clean(review: dict) -> bool:
    text = f"{review.get('title', '')} {review.get('text', '')}"
    return not (EMAIL_RE.search(text) or PHONE_RE.search(text))


def trim_sample(reviews: list[dict], keep_ids: set[str], size: int = SAMPLE_SIZE) -> list[dict]:
    """The `keep_ids` reviews plus every Nth of the rest, in the original order."""
    kept = [r for r in reviews if r["review_id"] in keep_ids]
    if len(kept) != len(keep_ids):
        raise SystemExit(
            f"quoted reviews missing from the sample: {keep_ids - {r['review_id'] for r in kept}}"
        )
    others = [r for r in reviews if r["review_id"] not in keep_ids and _is_clean(r)]
    wanted = size - len(kept)
    step = len(others) / wanted
    picked = {others[int(i * step)]["review_id"] for i in range(wanted)}
    chosen = keep_ids | picked
    return [r for r in reviews if r["review_id"] in chosen]


def scrub_run(run: dict) -> dict:
    for stage in run.get("stages", []):
        stage["notes"] = [n for n in stage.get("notes", []) if not n.startswith("raw cache:")]
    return run


def build(runs_dir: Path, out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)

    # The completed run
    src, dst = runs_dir / SUCCESS_RUN, out / "runs" / SUCCESS_RUN
    pulse = read_json(src / "pulse.json")
    quote_ids = {q["review_id"] for q in pulse["quotes"]}
    sample = trim_sample(read_json(src / "sanitized.json"), quote_ids)
    ids = {r["review_id"] for r in sample}
    for quote in pulse["quotes"]:
        review = next(r for r in sample if r["review_id"] == quote["review_id"])
        if _normalize(quote["text"]) not in _normalize(review["text"]):
            raise SystemExit(f"quote {quote['review_id']} is not in its review text")
    themes = read_json(src / "themes.json")
    themes["assignments"] = [a for a in themes["assignments"] if a["review_id"] in ids]
    write_json(dst / "run.json", scrub_run(read_json(src / "run.json")))
    write_json(dst / "pulse.json", pulse)
    write_json(dst / "ranking.json", read_json(src / "ranking.json"))
    write_json(dst / "themes.json", themes)
    write_json(dst / "sanitized.json", sample)
    (dst / "note.txt").write_text((src / "note.txt").read_text(encoding="utf-8"), encoding="utf-8")

    # The failed run
    src, dst = runs_dir / FAILED_RUN, out / "runs" / FAILED_RUN
    write_json(dst / "run.json", scrub_run(read_json(src / "run.json")))
    write_json(dst / "sanitized.json", trim_sample(read_json(src / "sanitized.json"), set()))

    # Config view, ledger, README
    from api.routes import build_config_view
    from api.settings import Settings

    from pulse.config import DEFAULT_CONFIG_PATH

    view = build_config_view(Settings.load(REPO_ROOT / DEFAULT_CONFIG_PATH)).model_dump()
    view["draft_to"] = PLACEHOLDER_DRAFT_TO
    view["doc_url"] = PLACEHOLDER_DOC_URL
    write_json(out / "config.json", view)
    write_json(out / "ledger.json", SYNTHETIC_LEDGER)
    (out / "README.md").write_text(README, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "web" / "fixtures")
    parser.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "data" / "runs")
    args = parser.parse_args()
    build(args.runs_dir, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
