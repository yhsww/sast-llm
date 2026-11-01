"""CLI: load a SonarQube JSON report, run RAG + LLM, and print structured test cases."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

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

_REPORT_PATH = Path("data/sast_reports/sample.json")


def _collect_code_snippets(issues) -> list[str | None]:
    snippets: list[str | None] = []
    print("\nYou can paste the vulnerable code snippet for each finding.")
    print("Finish each snippet with a line containing only '###'. Press Enter then '###' to skip.\n")

    for index, issue in enumerate(issues, start=1):
        print(f"Finding {index}: [{issue.rule}] {issue.message}")
        print(f"Component: {issue.component or 'N/A'} (line {issue.line or '?'})")
        print("Code snippet (end with '###' on its own line):")

        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                line = "###"
            if line.strip() == "###":
                break
            lines.append(line)

        snippet = "\n".join(lines).strip() or None
        snippets.append(snippet)
        print()

    return snippets


def main() -> None:
    report_path = Path(
        input(f"SonarQube report path [{_REPORT_PATH}]: ").strip() or str(_REPORT_PATH)
    )
    if not report_path.exists():
        print(f"File not found: {report_path}")
        sys.exit(1)

    report = SonarReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(report.issues)} finding(s) from {report_path}.")

    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path).resolve()

    code_snippets = _collect_code_snippets(report.issues)

    print("\nQuerying knowledge base (CWE + WSTG)...")
    retrieved_per_finding = [
        query_knowledge(f"{issue.rule} {issue.message} {' '.join(issue.tags)}")
        for issue in report.issues
    ]

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

    print("\nGenerating test cases...\n")
    llm_report = generate_test_cases(
        report.issues,
        user_context,
        retrieved_per_finding,
        code_snippets,
    )
    print(json.dumps(llm_report.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()