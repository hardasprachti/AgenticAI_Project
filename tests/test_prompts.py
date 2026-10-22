from pathlib import Path

import pytest

from pulse.prompts import PromptError, load_prompt

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path, body):
    (tmp_path / "p.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_loads_version_and_sections(tmp_path):
    d = _write(tmp_path, "<!-- version: 3 -->\n[[system]]\nBe brief.\n\n[[user]]\nHello {{who}}.\n")
    prompt = load_prompt("p", d)
    assert prompt.version == "p@3"
    assert prompt.system == "Be brief."
    assert prompt.render(who="there") == ("Be brief.", "Hello there.")


def test_json_braces_in_prompt_are_left_alone(tmp_path):
    d = _write(tmp_path, '<!-- version: 1 -->\n[[system]]\nReply {"a": 1}\n[[user]]\n{{x}}\n')
    system, user = load_prompt("p", d).render(x="y")
    assert system == 'Reply {"a": 1}' and user == "y"


def test_substituted_text_is_not_reinterpreted(tmp_path):
    d = _write(tmp_path, "<!-- version: 1 -->\n[[system]]\ns\n[[user]]\n{{a}} {{b}}\n")
    _, user = load_prompt("p", d).render(a="{{b}}", b="done")
    assert user == "{{b}} done"


def test_placeholder_mismatch_rejected(tmp_path):
    d = _write(tmp_path, "<!-- version: 1 -->\n[[system]]\ns\n[[user]]\n{{a}}\n")
    with pytest.raises(PromptError, match="placeholders"):
        load_prompt("p", d).render(a="1", extra="2")


def test_missing_version_or_section_rejected(tmp_path):
    with pytest.raises(PromptError, match="version"):
        load_prompt("p", _write(tmp_path, "[[system]]\ns\n[[user]]\nu\n"))
    with pytest.raises(PromptError, match="sections"):
        load_prompt("p", _write(tmp_path, "<!-- version: 1 -->\n[[system]]\ns\n"))


@pytest.mark.parametrize("name", ["theme_assign", "compose"])
def test_shipped_prompts_load_and_say_review_text_is_data(name):
    prompt = load_prompt(name, REPO_ROOT / "prompts")
    assert prompt.version.startswith(f"{name}@")
    assert "untrusted" in prompt.system
