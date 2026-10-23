"""Guard the complete production package tree, including future packages."""
from pathlib import Path
import re
import pytest
from tools.redact import FLAG_NAMES


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"(?<!\w)(?:8013|8016)(?!\w)|ofrep|demo\.flagd\.json|defaultVariant|flagd|:4000\b|feature[_.\s-]*flag|"
                       + "|".join(re.escape(name) for name in FLAG_NAMES), re.I)
SKIP = {".git", ".venv", ".build", ".specs", ".pytest_cache", "__pycache__", "tests", "runs"}
EXEMPT_FILES = {"action_api/flags.py", "tools/redact.py"}


def test_port_scan_does_not_match_digits_inside_recorded_timestamps():
    assert not FORBIDDEN.search('2026-10-23T11:06:45.858013+00:00')
    assert not FORBIDDEN.search('sha256: a8395f3e94c565a0b7f02bd3eea8ad61dba41d8cb11d66e0c8016a32930490e1')
    assert not FORBIDDEN.search('evidence/abc8013def.json')
    assert FORBIDDEN.search('http://localhost:8013/evaluate')
    assert FORBIDDEN.search('port = 8016')


def production_files():
    # A package may be a namespace package; include code directories even before
    # their __init__ is added. Documentation-only directories aren't packages.
    for extension in ("*.py", "*.js", "*.ts", "*.ps1", "*.sh"):
        yield from ROOT.glob(extension)
    for directory in ROOT.iterdir():
        if not directory.is_dir() or directory.name in SKIP or directory.name == "faultctl":
            continue
        if not any(path.suffix in {".py", ".js", ".ts", ".ps1", ".sh"} for path in directory.rglob("*")):
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not any(part in SKIP for part in path.relative_to(ROOT).parts):
                if path.relative_to(ROOT).as_posix() in EXEMPT_FILES:
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
    with pytest.raises(AssertionError, match="Forbidden"):
        test_no_flag_reads()


@pytest.mark.parametrize("relative", ["tools/reader.py", "tools/nested/redact.py",
    "action_api/helper.py", "agent/reader.py", "detect/reader.py", "new_module.py",
    "reader.js", "reader.ts", "reader.ps1", "reader.sh", "web/reader.ts"])
@pytest.mark.parametrize("marker", ["flagd", "feature_flag.key", "paymentFailure"])
def test_no_other_module_is_exempt(tmp_path, monkeypatch, relative, marker):
    import sys
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("endpoint = " + repr(marker), encoding="utf-8")
    with pytest.raises(AssertionError, match="Forbidden"):
        test_no_flag_reads()


def test_only_authorized_filter_and_operator_files_are_exempt(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    for relative in ("faultctl/cli.py", "tools/redact.py", "action_api/flags.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("marker = 'flagd'", encoding="utf-8")
    test_no_flag_reads()
