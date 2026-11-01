"""Direct-LLM experiment runner.

Loads every JSON report from data/sast_reports (including sample.json), sends
findings directly to the selected provider without RAG, and writes stable
results under results/<provider-folder>/<report>_LLM.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases

REPORTS_DIR = ROOT / "data" / "sast_reports"
RESULTS_DIR = ROOT / "results"

PROVIDER_FOLDERS = {
    "openai": "GPT5.5",  # Historical folder name retained for compatibility.
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


def discover_reports(only: str | None = None) -> list[Path]:
    """Return JSON reports in a stable order, optionally selecting one by stem."""
    if not REPORTS_DIR.is_dir():
        raise SystemExit(f"Reports directory not found: {REPORTS_DIR}")

    reports = list(REPORTS_DIR.glob("*.json"))

    def sort_key(path: Path):
        match = re.fullmatch(r"GT(\d+)", path.stem, re.IGNORECASE)
        if match:
            return (0, int(match.group(1)), path.name.casefold())
        return (1, 0, path.name.casefold())

    reports.sort(key=sort_key)

    if only:
        requested = Path(only.strip()).stem.casefold()
        reports = [path for path in reports if path.stem.casefold() == requested]
        if not reports:
            available = ", ".join(path.stem for path in discover_reports())
            raise SystemExit(
                f"Report '{only}' not found in {REPORTS_DIR}. "
                f"Available reports: {available}"
            )

    if not reports:
        raise SystemExit(f"No JSON reports found in: {REPORTS_DIR}")
    return reports


def choose_providers(
    requested_provider: str | None = None,
    all_providers: bool = False,
) -> list[str]:
    providers = list(PROVIDER_FOLDERS)

    if requested_provider:
        return [requested_provider.strip().lower()]
    if all_providers:
        return providers

    default_provider = settings.llm_provider.strip().lower()
    if default_provider not in PROVIDER_FOLDERS:
        raise SystemExit(
            f"Unsupported LLM_PROVIDER '{default_provider}'. "
            f"Choose one of: {', '.join(providers)}."
        )

    print("\nSelect LLM provider:")
    for index, provider in enumerate(providers, start=1):
        suffix = " (configured default)" if provider == default_provider else ""
        print(
            f"  {index}. {PROVIDER_LABELS[provider]} "
            f"({model_for(provider)}){suffix}"
        )
    print("  5. All providers")

    while True:
        choice = input(
            f"Option [Enter = {default_provider}, 5 = all]: "
        ).strip()
        if not choice:
            return [default_provider]
        if choice == "5" or choice.casefold() == "all":
            return providers
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            return [providers[int(choice) - 1]]
        provider_match = next(
            (provider for provider in providers if provider.casefold() == choice.casefold()),
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
    """Write atomically to the stable report filename, replacing prior output."""
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


def validate_report(report_path: Path) -> SonarReport:
    return SonarReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )


def process_report(report_path: Path, provider: str) -> bool:
    output_path = output_path_for(report_path, provider)
    error_path = output_path.with_name(f"{report_path.stem}_ERROR.txt")

    print(f"\nReport: {report_path.name}")
    print(f"Provider/model: {provider} / {model_for(provider)}")

    try:
        report = validate_report(report_path)
        print(f"Findings loaded: {len(report.issues)}")

        # Branch 1 is direct LLM: no RAG, retrieved documents, or code context.
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


def run_simulation(reports: list[Path]) -> int:
    """Validate report structure without calling any LLM or writing result files."""
    valid = 0
    invalid = 0
    print("\nSIMULATION MODE: no provider APIs will be called.")
    for report_path in reports:
        try:
            report = validate_report(report_path)
            print(f"[VALIDATED] {report_path.name}: {len(report.issues)} findings")
            valid += 1
        except Exception as exc:
            print(f"[INVALID] {report_path.name}: {type(exc).__name__}: {exc}")
            invalid += 1

    print("\nSIMULATION SUMMARY")
    print(f"Reports checked: {len(reports)}")
    print(f"Valid: {valid}")
    print(f"Invalid: {invalid}")
    return 1 if invalid else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the direct-LLM SAST experiment."
    )
    parser.add_argument(
        "--provider",
        choices=tuple(PROVIDER_FOLDERS),
        help="Run one provider without prompting.",
    )
    parser.add_argument(
        "--all-providers",
        action="store_true",
        help="Run all configured providers. This may incur API costs.",
    )
    parser.add_argument(
        "--only",
        metavar="REPORT",
        help="Run one report by filename or stem, e.g. GT01 or sample.json.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Validate report JSON without making API calls or writing results.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.provider and args.all_providers:
        parser.error("--provider and --all-providers cannot be used together.")

    reports = discover_reports(args.only)
    print(f"Reports found: {len(reports)}")
    print("Inputs: " + ", ".join(path.name for path in reports))

    if args.simulate:
        return run_simulation(reports)

    providers = choose_providers(args.provider, args.all_providers)
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
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
