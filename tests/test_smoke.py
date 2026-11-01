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


def test_code_context_runner_and_sources_exist():
    assert (ROOT / "scripts" / "run_gt_experiment.py").is_file()
    source_dir = ROOT / "data" / "code_snippets"
    assert source_dir.is_dir()
    for filename in ("UserRepository.java", "CommentController.java", "DatabaseConfig.java"):
        assert (source_dir / filename).is_file(), f"Missing code snippet: {filename}"
