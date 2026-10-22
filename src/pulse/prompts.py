"""Versioned prompt files (architecture section 6).

A prompt file starts with `<!-- version: N -->` and has a `[[system]]` and a `[[user]]` section.
Placeholders look like `{{name}}` and are filled by plain substitution, so JSON braces in the
prompt text are never misread as format fields. The version is recorded in each run record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_VERSION_RE = re.compile(r"^<!--\s*version:\s*(\d+)\s*-->\s*$", re.MULTILINE)
_SECTION_RE = re.compile(r"^\[\[(system|user)\]\]\s*$", re.MULTILINE)
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class PromptError(ValueError):
    """A prompt file is missing, malformed, or rendered with the wrong placeholders."""


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str  # e.g. "theme_assign@1"
    system: str
    user: str

    def render(self, **values: str) -> tuple[str, str]:
        """Return (system, user) with `{{name}}` placeholders in the user section filled."""
        wanted = set(_PLACEHOLDER_RE.findall(self.user))
        if wanted != set(values):
            raise PromptError(
                f"{self.name}: placeholders {sorted(wanted)} do not match values {sorted(values)}"
            )
        user = _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], self.user)
        return self.system, user


def load_prompt(name: str, prompts_dir: str | Path = "prompts") -> Prompt:
    path = Path(prompts_dir) / f"{name}.md"
    if not path.is_file():
        raise PromptError(f"Prompt file not found: {path}")
    text = path.read_text(encoding="utf-8")

    version = _VERSION_RE.search(text)
    if version is None:
        raise PromptError(f"{path.name} has no '<!-- version: N -->' header")

    parts = _SECTION_RE.split(text)  # [preamble, 'system', body, 'user', body]
    sections = dict(zip(parts[1::2], parts[2::2], strict=False))
    if set(sections) != {"system", "user"}:
        raise PromptError(f"{path.name} needs both [[system]] and [[user]] sections")
    return Prompt(
        name=name,
        version=f"{name}@{version.group(1)}",
        system=sections["system"].strip(),
        user=sections["user"].strip(),
    )
