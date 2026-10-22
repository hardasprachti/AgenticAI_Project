"""Privacy audit (implementation plan, Phase 7 task 2).

Takes the identities present in the raw reviews (reviewer names, store ids, and the emails, phone
numbers, URLs and long digit strings written in review text) and searches everything a run wrote or
would send for them: every file in the run directory, the ledger, the logs, the theme cache, and the
two texts that leave the machine, the Doc section (`note.txt`) and the draft body.

Google cannot be read back through the MCP server, so what was sent is audited instead: those two
texts are what the append and the draft call carry. The raw cache is where identities legitimately
live (sanitizing needs the name), so it is the audit's input, never something it audits.

A finding reports where and what kind, never the value, so the audit output is itself safe to share.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pulse.models import Pulse
from pulse.pii import find_pii
from pulse.render import render_email_body
from pulse.sources.csv_source import CsvSource

MIN_NAME_PART = 3  # shorter name fragments ("Jo", "Li") would match ordinary words
MIN_ID_LEN = 6  # shorter ids ("r12") would match inside unrelated tokens

NAME = "reviewer name"
STORE_ID = "store review id"
RAW_PII = "personal data from the raw reviews"


@dataclass
class Identities:
    names: set[str]
    store_ids: set[str]
    pii_strings: set[str]  # emails, phones, URLs, long digit strings found in the raw text


@dataclass(frozen=True)
class Finding:
    artifact: str
    kind: str
    count: int


@dataclass
class AuditReport:
    artifacts: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    def render(self) -> str:
        lines = [f"Audited {len(self.artifacts)} artifacts:"]
        lines += [f"  {name}" for name in self.artifacts]
        if self.clean:
            lines.append("Clean: no reviewer identity or personal data found.")
        else:
            lines.append(f"{len(self.findings)} finding(s):")
            lines += [f"  {f.artifact}: {f.kind} (x{f.count})" for f in self.findings]
        return "\n".join(lines)


def _identities(rows: list[tuple[str | None, str | None, str | None, str]]) -> Identities:
    """From (author_name, author_id, store_review_id, text) rows."""
    ids = Identities(names=set(), store_ids=set(), pii_strings=set())
    for author_name, author_id, store_id, text in rows:
        if author_name and author_name.strip():
            ids.names.add(author_name.strip())
        for value in (author_id, store_id):
            if value and len(value.strip()) >= MIN_ID_LEN:
                ids.store_ids.add(value.strip())
        ids.pii_strings.update(match.text for match in find_pii(text or ""))
    return ids


def identities_from_csv(path: Path | str) -> Identities:
    raw = CsvSource(path).fetch(date(1900, 1, 1), date(2999, 12, 31))
    return _identities([(r.author_name, r.author_id, r.store_review_id, r.text) for r in raw])


def identities_from_raw_cache(path: Path | str) -> Identities:
    """The `data/raw/<run_id>/reviews.json` a live run writes."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return _identities(
        [
            (r.get("author_name"), r.get("author_id"), r.get("store_review_id"), r["text"])
            for r in rows
        ]
    )


def _name_pattern(names: set[str]) -> re.Pattern[str] | None:
    """Full names, and each part of at least MIN_NAME_PART letters, case-sensitive on word edges."""
    words = set(names)
    for name in names:
        words.update(part for part in re.split(r"\W+", name) if len(part) >= MIN_NAME_PART)
    if not words:
        return None
    alternation = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)")


def _scan(name: str, text: str, ids: Identities, pattern: re.Pattern[str] | None) -> list[Finding]:
    found: list[Finding] = []
    if pattern and (n := len(pattern.findall(text))):
        found.append(Finding(name, NAME, n))
    if n := sum(text.count(i) for i in ids.store_ids):
        found.append(Finding(name, STORE_ID, n))
    if n := sum(text.count(s) for s in ids.pii_strings):
        found.append(Finding(name, RAW_PII, n))
    return found


def audit_run(run_dir: Path, identities: Identities, *, data_dir: Path) -> AuditReport:
    report = AuditReport()
    pattern = _name_pattern(identities.names)

    candidates: list[tuple[str, Path]] = [(p.name, p) for p in sorted(run_dir.iterdir())]
    for extra in (data_dir / "ledger.json", data_dir / "cache" / "theme_assignments.json"):
        candidates.append(
            (f"{extra.parent.name}/{extra.name}" if extra.parent != data_dir else extra.name, extra)
        )
    candidates += [(f"logs/{p.name}", p) for p in sorted((data_dir / "logs").glob("*"))]

    texts: dict[str, str] = {}
    for name, path in candidates:
        if path.is_file():
            texts[name] = path.read_text(encoding="utf-8", errors="replace")

    # What leaves the machine: the Doc section and the draft body.
    doc_url: str | None = None
    pulse_file = run_dir / "pulse.json"
    if pulse_file.is_file():
        pulse = Pulse.from_json(json.loads(pulse_file.read_text(encoding="utf-8")))
        try:  # a damaged run.json is still scanned as a file below; it just gives no doc link
            doc_url = json.loads((run_dir / "run.json").read_text(encoding="utf-8")).get("doc_url")
        except (OSError, ValueError):
            doc_url = None
        texts["draft body"] = render_email_body(pulse, doc_url)

    for name, text in texts.items():
        report.artifacts.append(name)
        report.findings += _scan(name, text, identities, pattern)
        if name in ("note.txt", "draft body"):
            kinds: dict[str, int] = {}
            # The draft carries our own Doc link on purpose; it is not reviewer data.
            for match in find_pii(text.replace(doc_url, "") if doc_url else text):
                kinds[match.kind] = kinds.get(match.kind, 0) + 1
            report.findings += [Finding(name, kind, n) for kind, n in kinds.items()]
    return report
