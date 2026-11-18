"""``.github/dependabot.yml`` must cover every dependency manifest the repo has.

The repo had no Dependabot config at all, and its four ``requirements*.txt``
files use ``>=`` with no pins, so a breaking release reached the next install
with nothing surfacing it. Parsed as text to avoid a PyYAML test dependency.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CONFIG = REPO_ROOT / ".github" / "dependabot.yml"


def _entries() -> list[tuple[str, str]]:
    """(ecosystem, directory) for each ``updates`` entry, in file order."""
    text = CONFIG.read_text()
    ecosystems = re.findall(r"package-ecosystem:\s*[\"']?([\w-]+)", text)
    directories = re.findall(r"^\s+directory:\s*[\"']?([^\"'\n]+)", text, flags=re.MULTILINE)
    assert len(ecosystems) == len(directories), "each update entry needs a directory"
    return list(zip(ecosystems, directories, strict=True))


def test_dependabot_config_exists_and_is_v2():
    assert CONFIG.is_file()
    assert re.search(r"^version:\s*2\s*$", CONFIG.read_text(), flags=re.MULTILINE)


def test_every_requirements_file_is_covered_by_pip_updates():
    pip_dirs = {d.strip().strip("/") for eco, d in _entries() if eco == "pip"}
    req_files = [
        p for p in REPO_ROOT.rglob("requirements*.txt")
        if ".git" not in p.parts and "venv" not in p.parts and ".venv" not in p.parts
    ]
    assert req_files, "expected at least one requirements file"
    for req in req_files:
        rel_dir = req.parent.relative_to(REPO_ROOT).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        assert rel_dir in pip_dirs, f"{req.relative_to(REPO_ROOT)} has no pip update entry"


def test_github_actions_are_covered():
    assert ("github-actions", "/") in [(e, d.strip()) for e, d in _entries()]
