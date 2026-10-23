"""Guard the complete production package tree, including future packages."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"8013|8016|ofrep|demo\.flagd\.json|defaultVariant|flagd|:4000", re.I)
SKIP = {".git", ".venv", ".build", ".specs", ".pytest_cache", "__pycache__", "tests", "runs"}


def production_files():
    # A package may be a namespace package; include code directories even before
    # their __init__ is added. Documentation-only directories aren't packages.
    for directory in ROOT.iterdir():
        if not directory.is_dir() or directory.name in SKIP or directory.name == "faultctl":
            continue
        if not any(directory.rglob("*.py")):
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not any(part in SKIP for part in path.relative_to(ROOT).parts):
                if path.relative_to(ROOT).as_posix() == "action_api/flags.py":
                    continue
                if path.suffix in {".py", ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".ps1", ".sh", ".js", ".ts"}:
                    yield path


def test_no_flag_reads():
    hits = []
    for path in production_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert not hits, "Forbidden feature-setting references: " + ", ".join(hits)


def test_scanner_covers_future_packages(tmp_path, monkeypatch):
    import sys
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "ROOT", tmp_path)
    package = tmp_path / "future_agent"
    package.mkdir()
    (package / "reader.py").write_text("endpoint = ':8013'", encoding="utf-8")
    assert list(production_files()) == [package / "reader.py"]
