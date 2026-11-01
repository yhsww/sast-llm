
"""Run SAST test-case experiments using the LLM configured in .env.

Examples:
    py run_experiment.py
    py run_experiment.py --report GT03
    py run_experiment.py --report GT03 --overwrite
    py run_experiment.py --provider claude
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "sast_reports"
DEFAULT_RESULTS_DIR = BASE_DIR / "results"
ENV_FILE = BASE_DIR / ".env"

PROVIDERS = ("openai", "gemini", "kimi", "claude")

PROVIDER_FOLDERS = {
    "openai": "GPT4.1",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}


def read_env_value(name: str) -> str | None:
    """Read a variable from the process environment or the project's .env."""
    value = os.environ.get(name)

    if value and value.strip():
        return value.strip().strip("\"'")

    if not ENV_FILE.is_file():
        return None

    try:
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, raw_value = line.split("=", 1)

            if key.strip() == name:
                value = raw_value.strip().strip("\"'")

                # Remove an inline comment when it is separated by whitespace.
                if " #" in value:
                    value = value.split(" #", 1)[0].strip()

                return value or None

    except OSError as exc:
        print(f"[WARNING] Could not read .env: {exc}")

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate security test cases using the LLM configured in .env."
        )
    )

    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="Optional provider override. If omitted, uses LLM_PROVIDER from .env.",
    )

    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Optional report name, e.g. GT03 or GT03.json.",
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing GT*.json SAST reports.",
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory where provider-specific results are saved.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing result files.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between API calls.",
    )

    return parser.parse_args()


def missing_configuration(provider: str) -> list[str]:
    """Return required configuration variables missing for a provider."""
    required = {
        "openai": [
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("OPENAI_CHAT_MODEL", settings.openai_chat_model),
        ],
        "gemini": [
            ("GOOGLE_API_KEY", settings.google_api_key),
            ("GEMINI_MODEL", settings.gemini_model),
        ],
        "kimi": [
            ("KIMI_API_KEY", settings.kimi_api_key),
            ("KIMI_MODEL", settings.kimi_model),
        ],
        "claude": [
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
            ("CLAUDE_MODEL", settings.claude_model),
        ],
    }

    return [
        name
        for name, value in required[provider]
        if not value or not str(value).strip()
    ]


def save_error(
    error_file: Path,
    provider: str,
    input_file: Path,
    exc: Exception,
) -> None:
    """Save an error in the selected provider's results folder."""
    message = (
        f"Provider: {provider}\n"
        f"Report: {input_file.name}\n"
        f"Error type: {type(exc).__name__}\n"
        f"Error: {exc}\n"
    )

    try:
        error_file.write_text(message, encoding="utf-8")
        print(f"[ERROR SAVED] {error_file.resolve()}")
    except OSError as write_exc:
        print(f"[ERROR] Could not save error file: {write_exc}")


def run_provider(
    provider: str,
    input_files: list[Path],
    results_dir: Path,
    overwrite: bool,
    delay: float,
) -> tuple[int, int, int]:
    """Run only the selected provider against the selected reports."""
    output_dir = results_dir / PROVIDER_FOLDERS[provider]
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSelected LLM: {provider}")
    print(f"Output directory: {output_dir.resolve()}")
    print(f"Reports selected: {len(input_files)}")

    missing = missing_configuration(provider)

    if missing:
        message = (
            f"Provider: {provider}\n"
            f"Missing configuration: {', '.join(missing)}\n"
        )

        config_error_file = output_dir / "CONFIG_ERROR.txt"
        config_error_file.write_text(message, encoding="utf-8")

        print(f"[CONFIG ERROR] Missing: {', '.join(missing)}")
        print(f"[ERROR SAVED] {config_error_file.resolve()}")

        return 0, len(input_files), 0

    succeeded = 0
    failed = 0
    skipped = 0

    for input_file in input_files:
        output_file = output_dir / f"{input_file.stem}_LLM.json"
        error_file = output_dir / f"{input_file.stem}_ERROR.txt"

        if output_file.exists() and not overwrite:
            print(
                f"[SKIPPED] {input_file.name}: result already exists. "
                "Use --overwrite to run it again."
            )
            skipped += 1
            continue

        print(f"\nProcessing {input_file.name} with {provider}...")

        try:
            raw_data = json.loads(
                input_file.read_text(encoding="utf-8")
            )

            report = SonarReport.model_validate(raw_data)

            if not report.issues:
                raise ValueError("Report contains no findings.")

            # Only the selected provider is called.
            result = generate_test_cases(
                report.issues,
                provider=provider,
            )

            expected_count = len(report.issues)
            actual_count = len(result.test_cases)

            if actual_count != expected_count:
                raise ValueError(
                    f"Expected {expected_count} test cases, "
                    f"received {actual_count}."
                )

            content = json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ) + "\n"

            temporary_file = output_file.with_suffix(
                output_file.suffix + ".tmp"
            )

            temporary_file.write_text(content, encoding="utf-8")
            temporary_file.replace(output_file)

            if error_file.exists():
                error_file.unlink()

            print(f"[OK] Saved: {output_file.resolve()}")
            succeeded += 1

        except (json.JSONDecodeError, ValidationError) as exc:
            save_error(error_file, provider, input_file, exc)
            print(f"[DATA ERROR] {input_file.name}: {exc}")
            failed += 1

        except Exception as exc:
            save_error(error_file, provider, input_file, exc)
            print(
                f"[ERROR] {input_file.name}: "
                f"{type(exc).__name__}: {exc}"
            )
            failed += 1

        if delay > 0:
            time.sleep(delay)

    print(
        f"\nSummary for {provider}: "
        f"successes={succeeded}, failures={failed}, skipped={skipped}"
    )

    return succeeded, failed, skipped


def main() -> int:
    args = parse_args()

    # An explicit command-line provider overrides the .env value.
    # Otherwise, use LLM_PROVIDER from .env or the process environment.
    provider = args.provider or read_env_value("LLM_PROVIDER")

    if not provider:
        print(
            "[ERROR] LLM_PROVIDER is missing.\n"
            "Add LLM_PROVIDER=openai, gemini, kimi or claude to your .env.",
            file=sys.stderr,
        )
        return 2

    provider = provider.strip().lower()

    if provider not in PROVIDERS:
        print(
            f"[ERROR] Invalid LLM_PROVIDER value: {provider!r}\n"
            f"Allowed values: {', '.join(PROVIDERS)}",
            file=sys.stderr,
        )
        return 2

    input_dir = args.input_dir.resolve()
    results_dir = args.results_dir.resolve()

    if not input_dir.is_dir():
        print(
            f"[ERROR] Input directory does not exist: {input_dir}",
            file=sys.stderr,
        )
        return 2

    if args.report:
        report_name = args.report.strip()

        if not report_name.lower().endswith(".json"):
            report_name += ".json"

        selected_file = input_dir / report_name

        if not selected_file.is_file():
            print(
                f"[ERROR] Report not found: {selected_file}",
                file=sys.stderr,
            )
            return 2

        input_files = [selected_file]
    else:
        input_files = sorted(input_dir.glob("GT*.json"))

    if not input_files:
        print(
            f"[ERROR] No GT*.json reports found in: {input_dir}",
            file=sys.stderr,
        )
        return 2

    print(f"Input directory: {input_dir}")
    print(f"Selected provider: {provider}")
    print(f"Selected reports: {', '.join(f.name for f in input_files)}")
    print(f"Overwrite existing outputs: {args.overwrite}")

    succeeded, failed, skipped = run_provider(
        provider=provider,
        input_files=input_files,
        results_dir=results_dir,
        overwrite=args.overwrite,
        delay=args.delay,
    )

    print(
        "\n===== EXPERIMENT SUMMARY =====\n"
        f"Provider: {provider}\n"
        f"Successful reports: {succeeded}\n"
        f"Failed reports: {failed}\n"
        f"Skipped reports: {skipped}\n"
        f"Results directory: {results_dir.resolve()}"
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
