"""CLI: load a SonarQube JSON report, generate test cases, and save them under results."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases

_REPORT_PATH = ROOT / "data" / "sast_reports" / "sample.json"

_PROVIDER_FOLDERS = {
    "openai": "GPT5.5",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}


def _save_result(report_path: Path, result) -> Path:
    """Save generated test cases without overwriting previous results."""
    provider = settings.llm_provider.strip().lower()
    folder = _PROVIDER_FOLDERS.get(provider, provider)

    output_dir = ROOT / "results" / folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{report_path.stem}_LLM.json"

    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = (
            output_dir /
            f"{report_path.stem}_LLM_{timestamp}.json"
        )

    payload = json.dumps(
        result.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )
    temporary_path.write_text(payload, encoding="utf-8")
    temporary_path.replace(output_path)

    return output_path


def main() -> None:
    report_path = Path(
        input(f"SonarQube report path [{_REPORT_PATH}]: ").strip()
        or str(_REPORT_PATH)
    )

    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path).resolve()

    if not report_path.is_file():
        print(f"File not found: {report_path}")
        sys.exit(1)

    report = SonarReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    print(f"Loaded {len(report.issues)} finding(s) from {report_path}.")

    user_context = input(
        "Optional focus/context (Enter to skip): "
    ).strip()

    print("\nGenerating test cases...\n")
    result = generate_test_cases(report.issues, user_context)

    print(json.dumps(
        result.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    ))

    saved_path = _save_result(report_path, result)
    print(f"\n[SAVED] Result written to: {saved_path.resolve()}")


if __name__ == "__main__":
    main()
