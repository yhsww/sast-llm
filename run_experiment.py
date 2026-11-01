import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases


def get_model_name() -> str:
    """Return the model configured for the selected provider."""
    provider = settings.llm_provider.strip().lower()

    model_names = {
        "openai": settings.openai_chat_model,
        "gemini": settings.gemini_model,
        "kimi": settings.kimi_model,
        "claude": settings.claude_model,
    }

    if provider not in model_names:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: {', '.join(model_names.keys())}"
        )

    return model_names[provider]


def get_output_directory_name(model_name: str) -> str:
    """Convert the model name into a filesystem-safe directory name."""
    return re.sub(
        r"[^a-zA-Z0-9._-]+",
        "-",
        model_name,
    ).strip("-")


def load_report(report_path: Path) -> SonarReport:
    """Load and validate a SonarQube report."""
    with report_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return SonarReport.model_validate(data)


def save_result(output_path: Path, result) -> None:
    """Save the generated result without additional experiment metadata."""
    result_data = result.model_dump(mode="json")
    payload = json.dumps(
        result_data,
        ensure_ascii=False,
        indent=2,
    )

    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary_path.write_text(payload + "\n", encoding="utf-8")
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Branch 1 direct LLM experiment."
    )

    parser.add_argument(
        "--only",
        metavar="GT",
        help="Run only one report, for example GT06.",
    )

    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Validate input reports without making API calls.",
    )

    args = parser.parse_args()

    provider = settings.llm_provider.strip().lower()
    model_name = get_model_name()
    output_directory_name = get_output_directory_name(model_name)

    input_dir = ROOT / "data" / "sast_reports"
    output_dir = ROOT / "results" / output_directory_name

    if not input_dir.is_dir():
        raise SystemExit(
            f"Input directory not found: {input_dir}"
        )

    if args.only:
        report_name = args.only.strip().upper()

        if not re.fullmatch(r"GT\d{2}", report_name):
            raise SystemExit(
                "Invalid report name. Use the format GT01, GT02, etc."
            )

        report_files = [input_dir / f"{report_name}.json"]
    else:
        report_files = sorted(
            input_dir.glob("GT*.json"),
            key=lambda path: path.name,
        )

    if not report_files:
        raise SystemExit(
            f"No GT*.json reports found in: {input_dir}"
        )

    missing_files = [
        str(path)
        for path in report_files
        if not path.is_file()
    ]

    if missing_files:
        raise SystemExit(
            "The following input reports were not found:\n"
            + "\n".join(missing_files)
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BRANCH 1 - DIRECT LLM EXPERIMENT")
    print("=" * 60)
    print(f"Provider: {provider}")
    print(f"Model: {model_name}")
    print(f"Output directory: {output_dir}")
    print(
        f"Mode: {'SIMULATION' if args.simulate else 'GENERATION'}"
    )
    print(f"Reports to process: {len(report_files)}")
    print("=" * 60)

    errors_found = False

    for report_path in report_files:
        report_name = report_path.stem

        output_path = output_dir / f"{report_name}_LLM.json"
        error_path = output_dir / f"{report_name}_ERROR.txt"

        if error_path.exists():
            error_path.unlink()

        try:
            report = load_report(report_path)

            print(f"\n[PROCESSING] {report_name}")
            print(f"Findings: {len(report.issues)}")

            if args.simulate:
                print(
                    f"[VALIDATED] {report_name}: "
                    "input report is valid."
                )
                continue

            start_time = time.perf_counter()

            generated = generate_test_cases(
                report.issues,
                "",
            )

            elapsed_time = time.perf_counter() - start_time

            if len(generated.test_cases) != len(report.issues):
                raise ValueError(
                    "The number of generated test cases does not match "
                    "the number of input findings. "
                    f"Findings: {len(report.issues)}; "
                    f"generated test cases: {len(generated.test_cases)}."
                )

            save_result(output_path, generated)

            print(f"[SUCCESS] Result saved: {output_path}")
            print(
                f"Generated test cases: "
                f"{len(generated.test_cases)}"
            )
            print(f"Elapsed time: {elapsed_time:.2f} seconds")

        except Exception as exc:
            errors_found = True

            error_message = (
                f"Report: {report_name}\n"
                f"Provider: {provider}\n"
                f"Model: {model_name}\n"
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {exc}\n"
            )

            error_path.write_text(
                error_message,
                encoding="utf-8",
            )

            print(f"[ERROR] {report_name}: {exc}")
            print(f"Error details saved to: {error_path}")

    print("\n" + "=" * 60)

    if args.simulate:
        print("SIMULATION COMPLETED")
    elif errors_found:
        print("EXPERIMENT COMPLETED WITH ERRORS")
    else:
        print("EXPERIMENT COMPLETED")

    print("=" * 60)

    return 1 if errors_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
