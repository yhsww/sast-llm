import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.schemas import SonarReport


def test_sample_report_parses():
    path = ROOT / "data" / "sast_reports" / "sample.json"
    assert path.is_file(), f"Missing sample report: {path}"
    report = SonarReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.issues


def test_all_gt_reports_parse():
    reports_dir = ROOT / "data" / "sast_reports"
    for number in range(1, 9):
        path = reports_dir / f"GT{number:02d}.json"
        assert path.is_file(), f"Missing report: {path}"
        report = SonarReport.model_validate_json(path.read_text(encoding="utf-8"))
        assert report.issues, f"No findings in {path.name}"


def test_rag_runner_and_ingestion_scripts_exist():
    assert (ROOT / "scripts" / "run_gt_experiment.py").is_file()
    assert (ROOT / "scripts" / "build_cwe_kb.py").is_file()
    assert (ROOT / "scripts" / "build_wstg_kb.py").is_file()
    assert (ROOT / "scripts" / "ingest.py").is_file()
