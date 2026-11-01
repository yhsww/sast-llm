"""Direct-LLM experiment runner.

Loads each JSON report from data/sast_reports, sends findings directly to
the selected provider (without RAG or pasted source-code context), and writes
one result per report/provider under results/<provider-folder>/.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases

REPORTS_DIR = ROOT / "data" / "sast_reports"
RESULTS_DIR = ROOT / "results"

PROVIDER_FOLDERS = {
    "openai": "GPT5.5",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "kimi": "Kimi (Moonshot)",
    "claude": "Anthropic Claude",
}


def model_for(provider: str) -> str:
    models = {
        "openai": settings.openai_chat_model,
        "gemini": settings.gemini_model,
        "kimi": settings.kimi_model,
        "claude": settings.claude_model,
    }
    return str(models[provider])


def discover_reports() -> list[Path]:
    """Return report JSON files in a stable order."""
    if not REPORTS_DIR.is_dir():
        raise SystemExit(f"Reports directory not found: {REPORTS_DIR}")

    reports = list(REPORTS_DIR.glob("*.json"))

    def sort_key(path: Path):
        match = re.fullmatch(r"GT(\d+)", path.stem, re.IGNORECASE)
        if match:
            return (0, int(match.group(1)), path.name.casefold())
        return (1, 0, path.name.casefold())

    reports.sort(key=sort_key)
    if not reports:
        raise SystemExit(f"No JSON reports found in: {REPORTS_DIR}")
    return reports


def choose_providers() -> list[str]:
    providers = list(PROVIDER_FOLDERS)
    print("\nSelect LLM provider:")
    for index, provider in enumerate(providers, start=1):
        print(
            f"  {index}. {PROVIDER_LABELS[provider]} "
            f"({model_for(provider)})"
        )
    print("  5. All providers")

    while True:
        choice = input("Option [5 = all]: ").strip() or "5"
        if choice == "5" or choice.casefold() == "all":
            return providers
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            return [providers[int(choice) - 1]]
        provider_match = next(
            (provider for provider in providers
             if provider.casefold() == choice.casefold()),
            None,
        )
        if provider_match:
            return [provider_match]
        print("Invalid option. Choose 1-5 or enter a provider name.")


def output_path_for(report_path: Path, provider: str) -> Path:
    output_dir = RESULTS_DIR / PROVIDER_FOLDERS[provider]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{report_path.stem}_LLM.json"


def save_result(result, output_path: Path) -> Path:
    """Write atomically and never overwrite a previous result."""
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = output_path.with_name(
            f"{output_path.stem}_{timestamp}{output_path.suffix}"
        )

    payload = json.dumps(
        result.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary_path.write_text(payload, encoding="utf-8")
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return output_path


def process_report(report_path: Path, provider: str) -> bool:
    output_path = output_path_for(report_path, provider)
    error_path = output_path.with_name(f"{report_path.stem}_ERROR.txt")

    print(f"\nReport: {report_path.name}")
    print(f"Provider/model: {provider} / {model_for(provider)}")

    try:
        report = SonarReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        print(f"Findings loaded: {len(report.issues)}")

        # Branch 1 is direct LLM: no RAG, extra context, or code snippet prompt.
        result = generate_test_cases(report.issues, provider=provider)
        saved_path = save_result(result, output_path)

        if error_path.exists():
            error_path.unlink()
        print(f"[SAVED] {saved_path.relative_to(ROOT)}")
        return True
    except Exception as exc:
        error_path.write_text(
            f"Report: {report_path.name}\n"
            f"Provider: {provider}\n"
            f"Model: {model_for(provider)}\n"
            f"Error: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        print(f"[ERROR FILE] {error_path.relative_to(ROOT)}")
        return False


def main() -> None:
    reports = discover_reports()
    providers = choose_providers()

    print(f"\nReports found: {len(reports)}")
    print(f"Selected providers: {', '.join(providers)}")
    print("Mode: direct LLM (no RAG and no additional context prompt)")

    succeeded = 0
    failed = 0
    for provider in providers:
        print(f"\n{'=' * 64}\n{PROVIDER_LABELS[provider]}: {model_for(provider)}")
        print("=" * 64)
        for report_path in reports:
            if process_report(report_path, provider):
                succeeded += 1
            else:
                failed += 1

    print(f"\n{'=' * 64}")
    print("EXECUTION SUMMARY")
    print(f"Reports: {len(reports)}")
    print(f"Providers: {len(providers)}")
    print(f"Successful: {succeeded}")
    print(f"Failed: {failed}")
    print(f"Results directory: {RESULTS_DIR}")
    print("=" * 64)


if __name__ == "__main__":
    main()
