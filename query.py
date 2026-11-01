"""Interactive interface for Branch 3 — RAG + source code context."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.schemas import SonarReport
from backend.chroma_service import query_knowledge

from scripts.run_gt_experiment import (
    PROVIDERS,
    generate,
    output_folder_for,
    model_for,
)


DEFAULT_REPORT = ROOT / "data" / "sast_reports" / "sample.json"


def collect_code_snippets(issues) -> list[str | None]:
    """Optionally collect the vulnerable source code for each finding."""

    snippets: list[str | None] = []

    print("\nPaste the vulnerable source code for each finding.")
    print("Finish each snippet with a line containing only ###.")
    print("To skip a finding's source code, type ###.\n")

    for index, issue in enumerate(issues, start=1):
        print(f"Finding {index}: [{issue.rule}] {issue.message}")
        print(
            f"Component: {issue.component or 'N/A'} "
            f"(line {issue.line or '?'})"
        )

        lines: list[str] = []

        while True:
            try:
                line = input()
            except EOFError:
                line = "###"

            if line.strip() == "###":
                break

            lines.append(line)

        snippet = "\n".join(lines).strip()
        snippets.append(snippet or None)
        print()

    return snippets


def build_user_content(
    issues,
    retrieved,
    snippets: list[str | None],
    focus: str = "",
) -> str:
    """Build the prompt with findings, vulnerable code, and RAG documents."""

    snippets = list(snippets)
    snippets.extend([None] * max(0, len(issues) - len(snippets)))

    blocks: list[str] = []

    for index, (issue, docs) in enumerate(
        zip(issues, retrieved),
        start=1,
    ):
        lines = [
            f"--- Finding {index} ---",
            f"Rule: {getattr(issue, 'rule', 'N/A')}",
            f"Severity: {getattr(issue, 'severity', 'N/A')}",
            f"Message: {getattr(issue, 'message', 'N/A')}",
            f"Component: {getattr(issue, 'component', None) or 'N/A'}",
            f"Line: {getattr(issue, 'line', None) or 'N/A'}",
        ]

        snippet = snippets[index - 1]

        if snippet:
            lines.extend(
                [
                    "",
                    "[Vulnerable Source Code]",
                    "```",
                    snippet,
                    "```",
                ]
            )

        for doc in docs:
            lines.extend(
                [
                    "",
                    (
                        f"[{getattr(doc, 'source', 'Reference')} "
                        f"Reference: {getattr(doc, 'id', 'N/A')}]"
                    ),
                    getattr(doc, "title", "") or "",
                    (getattr(doc, "content", "") or "")[:1500],
                ]
            )

        blocks.append("\n".join(lines))

    parts: list[str] = []

    if focus.strip():
        parts.append(
            "[Additional focus/context]\n" + focus.strip()
        )

    parts.extend(blocks)

    return "\n\n".join(parts)


def save_result(
    report_path: Path,
    provider: str,
    model: str,
    result,
) -> Path:
    """Save the result in the provider-specific output directory."""

    provider_folder = output_folder_for(provider)

    output_dir = ROOT / "results" / provider_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{report_path.stem}_LLM.json"

    # Preserve existing reports instead of overwriting them.
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = (
            output_dir
            / f"{report_path.stem}_LLM_{timestamp}.json"
        )

    payload = result.model_dump(mode="json")

    # Add metadata identifying the provider and model.
    if isinstance(payload, dict):
        payload["_metadata"] = {
            "provider": provider,
            "model": model,
            "source_report": report_path.name,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

    content = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    temporary_path.write_text(
        content,
        encoding="utf-8",
    )

    temporary_path.replace(output_path)

    return output_path


def choose_providers() -> list[str]:
    """Allow the user to select one provider or all providers."""

    providers = list(PROVIDERS)

    print("\nSelect a provider to generate reports:\n")

    for index, provider in enumerate(providers, start=1):
        folder = output_folder_for(provider)
        print(
            f"  {index}. {provider} "
            f"(results/{folder}/)"
        )

    print("  5. All providers")

    while True:
        choice = (
            input("\nChoose [1-5] (default: all): ").strip()
            or "5"
        )

        if choice == "5" or choice.casefold() == "all":
            return providers

        if choice.isdigit():
            index = int(choice)

            if 1 <= index <= len(providers):
                return [providers[index - 1]]

        matched = next(
            (
                provider
                for provider in providers
                if provider.casefold() == choice.casefold()
            ),
            None,
        )

        if matched:
            return [matched]

        print("Invalid option. Enter 1, 2, 3, 4, or 5.")


def main() -> None:
    """Run interactive report generation."""

    entered_path = input(
        f"SonarQube report path [{DEFAULT_REPORT}]: "
    ).strip()

    report_path = Path(entered_path or DEFAULT_REPORT)

    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path).resolve()

    if not report_path.is_file():
        print(f"[ERROR] File not found: {report_path}")
        raise SystemExit(1)

    try:
        report = SonarReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        print(
            "[ERROR] Could not read the report: "
            f"{type(exc).__name__}: {exc}"
        )
        raise SystemExit(1)

    issues = report.issues

    if not issues:
        print("[ERROR] The report contains no findings.")
        raise SystemExit(1)

    print(f"\nReport: {report_path}")
    print(f"Findings loaded: {len(issues)}")

    providers = choose_providers()

    focus = input(
        "\nAdditional context/focus (press Enter to skip): "
    ).strip()

    snippets = collect_code_snippets(issues)

    print("\nQuerying the RAG knowledge base (CWE + WSTG)...")

    retrieved = []

    for index, issue in enumerate(issues, start=1):
        tags = getattr(issue, "tags", None) or []

        query = (
            f"{issue.rule} {issue.message} "
            f"{' '.join(tags)}"
        )

        try:
            docs = query_knowledge(query)
            docs = list(docs or [])
        except Exception as exc:
            print(
                f"[ERROR] Finding {index}: RAG query failed: "
                f"{type(exc).__name__}: {exc}"
            )
            docs = []

        retrieved.append(docs)

        print(
            f"  Finding {index}: {len(docs)} document(s) retrieved: "
            f"{[getattr(doc, 'id', 'N/A') for doc in docs]}"
        )

    user_content = build_user_content(
        issues,
        retrieved,
        snippets,
        focus,
    )

    print("\nStarting report generation...\n")

    succeeded = 0
    failed = 0

    for provider in providers:
        model = model_for(provider)
        folder = output_folder_for(provider)

        print(
            f"\n--- Provider: {provider} "
            f"| Model: {model} "
            f"| Folder: results/{folder}/ ---"
        )

        try:
            result = generate(provider, user_content)

            test_cases = getattr(result, "test_cases", None)

            if test_cases is None:
                raise ValueError(
                    "The response does not contain the test_cases field."
                )

            if len(test_cases) != len(issues):
                raise ValueError(
                    f"Expected {len(issues)} test cases, "
                    f"but received {len(test_cases)}."
                )

            output_path = save_result(
                report_path,
                provider,
                model,
                result,
            )

            print(
                f"[OK] Report saved to: {output_path.resolve()}"
            )

            succeeded += 1

        except Exception as exc:
            error_dir = ROOT / "results" / folder
            error_dir.mkdir(parents=True, exist_ok=True)

            error_path = error_dir / (
                f"{report_path.stem}_ERROR.txt"
            )

            error_path.write_text(
                f"Provider: {provider}\n"
                f"Model: {model}\n"
                f"Report: {report_path}\n"
                f"Error: {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )

            print(
                f"[ERROR] {provider}: "
                f"{type(exc).__name__}: {exc}"
            )
            print(f"[SAVED] Error details: {error_path}")

            failed += 1

    print("\n========== SUMMARY ==========")
    print(f"Reports generated: {succeeded}")
    print(f"Failures: {failed}")

    if failed and not succeeded:
        raise SystemExit(2)


if __name__ == "__main__":
    main()