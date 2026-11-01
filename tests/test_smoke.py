import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import query
from backend.schemas import SonarReport


def test_sample_report_parses():
    path = ROOT / "data" / "sast_reports" / "sample.json"
    assert path.is_file(), f"Missing sample report: {path}"
    report = SonarReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.issues


def test_default_report_is_sample():
    reports = query.discover_reports()
    assert len(reports) == 1
    assert reports[0].name == "sample.json"


def test_simulation_validates_sample_without_api(capsys):
    reports = query.discover_reports()
    assert query.run_simulation(reports) == 0
    output = capsys.readouterr().out
    assert "SIMULATION MODE" in output
    assert "[VALIDATED] sample.json" in output


def test_all_reports_mode_includes_sample():
    reports = query.discover_reports(all_reports=True)
    assert any(path.name == "sample.json" for path in reports)
