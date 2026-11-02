"""Branch 3 runner: RAG + source-code context.

Input reports:
    data/sast_reports/GT*.json

Optional snippets:
    data/code_snippets/GT01.json

Outputs:
    results/GPT5.5/GT01_LLM.json
    results/Gemini/GT01_LLM.json
    results/Kimi/GT01_LLM.json
    results/Claude/GT01_LLM.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.config import settings
from backend.schemas import SecurityTestReport, SonarReport
from backend.chroma_service import query_knowledge
from backend.openai_service import _SYSTEM_PROMPT, _build_finding_block


# Each provider has its own output folder.
PROVIDERS = {
    "GPT": {
        "api_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_CHAT_MODEL",
        "model": "gpt-6.1-sol",
        "folder": "GPT5.5",
    },
    "Gemini": {
        "api_env": "GOOGLE_API_KEY",
        "model_env": "GEMINI_MODEL",
        "model": "gemini-3.8-flash",
        "folder": "Gemini",
    },
    "Kimi": {
        "api_env": "KIMI_API_KEY",
        "model_env": "KIMI_MODEL",
        "model": "kimi-k3.1-pro",
        "folder": "Kimi",
    },
    "Claude": {
        "api_env": "ANTHROPIC_API_KEY",
        "model_env": "CLAUDE_MODEL",
        "model": "claude-sonnet-5",
        "folder": "Claude",
    },
}


def model_for(name: str) -> str:
    cfg = PROVIDERS[name]
    return (os.getenv(cfg["model_env"]) or cfg["model"]).strip()


def output_folder_for(name: str) -> str:
    """Return the stable output folder assigned to a provider."""
    return PROVIDERS[name]["folder"]


def api_key_for(name: str) -> str:
    if name == "GPT":
        return os.getenv("OPENAI_API_KEY", "").strip()

    return os.getenv(PROVIDERS[name]["api_env"], "").strip()


def _source_excerpt(path: Path, line_number: int | None, radius: int = 15) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    if not lines:
        return None

    if line_number is not None and 1 <= line_number <= len(lines):
        start = max(1, line_number - radius)
        end = min(len(lines), line_number + radius)
    else:
        # Some sample reports use line numbers from a larger fixture; retain
        # the matching file as context rather than silently dropping it.
        start = 1
        end = min(len(lines), 120)

    excerpt = "\n".join(f"{n:>5}: {lines[n - 1]}" for n in range(start, end + 1))
    return f"Source: {path.name} (lines {start}-{end})\n{excerpt}"


def load_snippets(
    report_path: Path,
    raw: dict[str, Any],
    report: SonarReport,
    snippets_dir: Path,
) -> list[str | None]:
    """Load explicit snippets, or match sample source files by component basename."""
    value: Any = raw.get("code_snippets")
    snippet_path = snippets_dir / f"{report_path.stem}.json"

    if value is None and snippet_path.is_file():
        try:
            value = json.loads(snippet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read {snippet_path}: {exc}") from exc

    if isinstance(value, dict) and "code_snippets" in value:
        value = value["code_snippets"]

    if isinstance(value, list):
        values = [v if isinstance(v, str) and v.strip() else None for v in value]
        return (values + [None] * len(report.issues))[:len(report.issues)]

    if isinstance(value, dict):
        snippets = []
        for index, issue in enumerate(report.issues, start=1):
            keys = [str(index), issue.key or "", issue.component or "", issue.rule]
            item = next((value[k] for k in keys if k and k in value), None)
            snippets.append(item if isinstance(item, str) and item.strip() else None)
        return snippets

    if value is not None:
        raise ValueError(
            f"Unsupported snippet format in {snippet_path}; use a list or object."
        )

    files_by_name: dict[str, Path] = {}
    if snippets_dir.is_dir():
        for candidate in sorted(snippets_dir.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in {
                ".java", ".js", ".ts", ".py", ".php", ".cs", ".go"
            }:
                files_by_name.setdefault(candidate.name.casefold(), candidate)

    snippets: list[str | None] = []
    for issue in report.issues:
        component = (issue.component or "").split(":", 1)[-1].replace("\\", "/")
        source_path = files_by_name.get(Path(component).name.casefold())
        line_number = issue.line or (
            issue.textRange.startLine if issue.textRange else None
        )
        snippets.append(
            _source_excerpt(source_path, line_number) if source_path else None
        )

    return snippets


def extract_source_snippets(
    report: SonarReport,
    source_root: Path,
    radius: int = 15,
) -> list[str | None]:
    """Extract source context using component paths, with a safe basename fallback."""
    snippets: list[str | None] = []
    root = source_root.resolve()

    # Index source files once. Sonar component paths often include a project prefix
    # (for example, "juice-shop:routes/file.ts") that is not a directory under root.
    source_files = [
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {
            ".java", ".js", ".jsx", ".ts", ".tsx", ".py", ".php",
            ".cs", ".go", ".rb", ".html", ".xml", ".sql",
        }
    ] if root.is_dir() else []

    by_relative_path = {
        path.relative_to(root).as_posix().casefold(): path
        for path in source_files
    }
    by_basename: dict[str, list[Path]] = {}
    for path in source_files:
        by_basename.setdefault(path.name.casefold(), []).append(path)

    for issue in report.issues:
        component = issue.component or ""
        relative = component.split(":", 1)[1] if ":" in component else component
        relative = relative.replace("\\", "/").lstrip("/")
        relative = relative.removeprefix("./")
        candidate = (root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            snippets.append(None)
            continue

        if not candidate.is_file():
            candidate = by_relative_path.get(relative.casefold())
        if not candidate:
            matches = by_basename.get(Path(relative).name.casefold(), [])
            # Prefer a path ending in the full component-relative path; otherwise
            # use a deterministic first match when only a basename is available.
            matching_suffix = [
                path for path in matches
                if path.as_posix().casefold().endswith(relative.casefold())
            ]
            candidate = sorted(matching_suffix or matches, key=lambda p: p.as_posix())[0] if matches else None

        if not candidate:
            snippets.append(None)
            continue

        try:
            lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            snippets.append(None)
            continue

        if not lines:
            snippets.append(None)
            continue

        line_number = issue.line or (
            issue.textRange.startLine if issue.textRange else None
        )
        if line_number and 1 <= line_number <= len(lines):
            start_line = max(1, line_number - radius)
            end_line = min(len(lines), line_number + radius)
        else:
            # Keep the file as context even when the scanner line does not map
            # to this checkout (for example, line numbers from another revision).
            start_line = 1
            end_line = min(len(lines), 120)

        excerpt = "\n".join(
            f"{n:>5}: {lines[n - 1]}"
            for n in range(start_line, end_line + 1)
        )
        snippets.append(
            f"Source: {candidate.relative_to(root).as_posix()} "
            f"(lines {start_line}-{end_line})\n{excerpt}"
        )

    return snippets

def prompt_for_snippets(report_path: Path, report: SonarReport) -> list[str | None]:
    """Prompt for a code snippet for each finding; finish each snippet with a line containing ###."""
    snippets: list[str | None] = []
    print(f"\n[SNIPPETS] {report_path.name}: informe o código para cada finding.")
    print("Cole o conteúdo do arquivo e finalize com ### em uma linha isolada.")
    print("Para pular um finding, pressione Enter e depois digite ###.\n")

    for index, issue in enumerate(report.issues, start=1):
        print("-" * 70)
        print(f"Finding {index}/{len(report.issues)}")
        print(f"Rule: {issue.rule}")
        print(f"Message: {issue.message}")
        print(f"Component: {issue.component or 'N/A'}")
        line_number = issue.line or (
            issue.textRange.startLine if issue.textRange else None
        )
        print(f"Line: {line_number or 'N/A'}")
        print("Cole o snippet abaixo (terminador ###):")

        lines: list[str] = []
        while True:
            try:
                line = sys.stdin.readline()
            except KeyboardInterrupt:
                print("\n[WARN] Entrada interativa interrompida.")
                return snippets + [None] * (len(report.issues) - len(snippets))

            if line == "":
                # EOF: preserve snippets already entered and skip remaining findings.
                print("\n[WARN] Entrada encerrada; findings restantes serão ignorados.")
                return snippets + [None] * (len(report.issues) - len(snippets))

            line = line.rstrip("\r\n")
            if line.strip() == "###":
                break
            lines.append(line)

        snippet = "\n".join(lines).strip()
        snippets.append(snippet if snippet else None)
        print("[OK] Snippet recebido." if snippet else "[SKIP] Finding sem snippet.")

    return snippets


def parse_response(text: str) -> SecurityTestReport:
    """Parse a provider response as a SecurityTestReport."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")

        if start >= 0 and end > start:
            text = text[start:end + 1]

    return SecurityTestReport.model_validate(json.loads(text))


def build_user_content(issues, retrieved, snippets: list[str | None]) -> str:
    """Monta o prompt com os achados, o código vulnerável e o contexto RAG."""
    snippets = list(snippets) + [None] * max(0, len(issues) - len(snippets))
    blocks = []

    for index, (issue, docs) in enumerate(
        zip(issues, retrieved), start=1
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
        if snippet and snippet.strip():
            lines.extend([
                "",
                "[Vulnerable Source Code]",
                "```",
                snippet.strip(),
                "```",
            ])

        for doc in docs:
            lines.extend([
                "",
                f"[{getattr(doc, 'source', 'Reference')} "
                f"Reference: {getattr(doc, 'id', 'N/A')}]",
                getattr(doc, 'title', '') or '',
                (getattr(doc, 'content', '') or '')[:1500],
            ])

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def generate(provider: str, user_content: str) -> SecurityTestReport:
    """Call the selected provider and parse its generated test cases."""
    key = api_key_for(provider)
    model = model_for(provider)

    if not key:
        raise RuntimeError(
            f"Missing {PROVIDERS[provider]['api_env']} for {provider} in .env."
        )

    if provider in ("GPT", "Kimi"):
        from openai import OpenAI

        kwargs = {"api_key": key}

        if provider == "Kimi":
            kwargs["base_url"] = os.getenv(
                "KIMI_BASE_URL",
                "https://api.moonshot.ai/v1"
            )

        client = OpenAI(**kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content

        if not text:
            raise ValueError(f"{provider} returned an empty response.")

        result = parse_response(text)

    elif provider == "Gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=SecurityTestReport,
            ),
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        result = parse_response(response.text)

    else:
        from anthropic import Anthropic

        client = Anthropic(api_key=key)

        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        chunks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]

        if not chunks:
            raise ValueError("Claude returned no text content.")

        result = parse_response("\n".join(chunks))

    return result


def discover_reports(
    input_dir: Path,
    requested: str | None,
) -> list[Path]:
    """Find the requested report or all GT*.json reports."""
    if requested:
        requested_path = Path(requested)
        if requested_path.suffix.lower() != ".json":
            requested_path = requested_path.with_suffix(".json")
        path = requested_path if requested_path.is_absolute() else input_dir / requested_path

        if not path.is_file():
            raise SystemExit(f"[ERROR] Report not found: {path.resolve()}")

        return [path.resolve()]

    reports = list(input_dir.glob("GT*.json"))

    reports.sort(
        key=lambda p: (
            int(re.search(r"GT(\d+)", p.stem).group(1))
            if re.search(r"GT(\d+)", p.stem)
            else 10**9
        )
    )

    if not reports:
        raise SystemExit(f"[ERROR] No GT*.json files found in {input_dir}")

    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Branch 3 experiment: RAG + code context"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call the selected LLM APIs to generate results.",
    )
    def normalize_provider(value: str) -> str:
        if value.casefold() == "all":
            return "all"
        for name in PROVIDERS:
            if name.casefold() == value.casefold():
                return name
        return value

    parser.add_argument(
        "--provider",
        type=normalize_provider,
        choices=[*PROVIDERS, "all"],
        default="all",
        help="Select GPT, Gemini, Kimi, Claude, or all (default: all).",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--allreports", "--all-reports",
        action="store_true",
        help="Process every *.json report in --reports-dir.",
    )
    selection.add_argument(
        "--only",
        metavar="ARQUIVO.json",
        help="Process only one report, e.g. --only GT01.json.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Run one SonarQube JSON report directly, e.g. sample.json.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=ROOT / "data" / "sast_reports",
    )
    parser.add_argument(
        "--snippets-dir",
        type=Path,
        default=ROOT / "data" / "code_snippets",
    )
    parser.add_argument(
        "--auto-snippets",
        action="store_true",
        help="Disable interactive prompts and load snippets from JSON/files or --source-root.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Optional source-code root to extract code around Sonar issues.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing result JSON files. By default, existing results are preserved.",
    )

    args = parser.parse_args(argv)

    if args.input_file:
        input_path = args.input_file
        if not input_path.is_absolute():
            input_path = (Path.cwd() / input_path).resolve()
        if not input_path.is_file():
            raise SystemExit(f"[ERROR] Input report not found: {input_path}")
        if args.allreports or args.only:
            parser.error("--input-file cannot be combined with --allreports or --only.")
        reports = [input_path]
    elif args.allreports:
        reports = sorted(
            (p for p in args.reports_dir.glob("*.json") if p.is_file()),
            key=lambda p: p.name.casefold(),
        )
        if not reports:
            raise SystemExit(f"[ERROR] No JSON reports found in {args.reports_dir}")
    else:
        # Preserve the original no-argument behavior: process GT*.json.
        reports = discover_reports(args.reports_dir, args.only)
    provider_names = (
        list(PROVIDERS)
        if args.provider == "all"
        else [args.provider]
    )

    print("Branch 3 — RAG + Code Context")
    print(f"Reports: {len(reports)} | Providers: {', '.join(provider_names)}")
    print(
        f"Mode: {'LIVE GENERATION' if args.execute else 'DRY RUN (no generation calls)'}"
    )

    totals = {"ok": 0, "error": 0, "skip": 0}
    prepared = []

    # Retrieve RAG context once per report and reuse it across providers.
    for path in reports:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            report = SonarReport.model_validate(raw)

            if args.auto_snippets:
                snippets = load_snippets(
                    path,
                    raw,
                    report,
                    args.snippets_dir,
                )

                if args.source_root:
                    extracted = extract_source_snippets(
                        report,
                        args.source_root,
                    )
                    snippets = [
                        existing or extracted[i]
                        for i, existing in enumerate(snippets)
                    ]
            else:
                snippets = prompt_for_snippets(path, report)

            retrieved = [
                query_knowledge(
                    f"{issue.rule} {issue.message} {' '.join(issue.tags)}"
                )
                for issue in report.issues
            ]

            count = sum(bool(s and s.strip()) for s in snippets)
            docs_count = sum(len(docs) for docs in retrieved)

            print(
                f"[RAG] {path.name}: findings={len(report.issues)}, "
                f"snippets={count}/{len(report.issues)}, docs={docs_count}"
            )

            if not count:
                print(
                    f"[WARN] {path.name}: no source snippets loaded; "
                    "code-context portion will be empty."
                )

            prepared.append((path, report, retrieved, snippets))

        except Exception as exc:
            print(
                f"[ERROR] Preparing {path.name}: "
                f"{type(exc).__name__}: {exc}"
            )
            totals["error"] += 1

    # Execute each provider independently and save into its own folder.
    for provider in provider_names:
        summary = {"ok": 0, "error": 0, "skip": 0}
        provider_folder = output_folder_for(provider)
        out_dir = ROOT / "results" / provider_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"\n{'=' * 54}\n{provider} | model={model_for(provider)} "
            f"| output=results/{provider_folder}"
        )

        for item_index, (path, report, retrieved, snippets) in enumerate(prepared):
            out = out_dir / f"{path.stem}_LLM.json"
            err = out_dir / f"{path.stem}_ERROR.txt"

            if args.execute and out.is_file() and not args.force:
                print(
                    f"[SKIP] Preserving existing result {out.relative_to(ROOT)} "
                    "(use --force to overwrite)."
                )
                summary["skip"] += 1
                continue

            if args.execute and not api_key_for(provider):
                print(
                    f"[SKIP] {provider}: {PROVIDERS[provider]['api_env']} is not configured; "
                    "no API call or error file created."
                )
                summary["skip"] += 1
                continue

            try:
                user_content = build_user_content(
                    report.issues,
                    retrieved,
                    snippets,
                )

                if not args.execute:
                    print(
                        f"[DRY RUN] results/{provider_folder}/"
                        f"{path.stem}_LLM.json: "
                        f"{len(report.issues)} finding(s) prepared"
                    )
                    summary["ok"] += 1
                    continue

                generated = generate(provider, user_content)

                if len(generated.test_cases) != len(report.issues):
                    raise ValueError(
                        f"Expected {len(report.issues)} test cases, "
                        f"got {len(generated.test_cases)}"
                    )

                payload = json.dumps(
                    generated.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                ) + "\n"

                temporary_path = out.with_suffix(out.suffix + ".tmp")
                try:
                    temporary_path.write_text(payload, encoding="utf-8")
                    temporary_path.replace(out)
                finally:
                    if temporary_path.exists():
                        temporary_path.unlink()

                if err.exists():
                    err.unlink()

                print(f"[OK] Saved {out.relative_to(ROOT)}")
                summary["ok"] += 1

            except Exception as exc:
                message = str(exc)
                print(
                    f"[ERROR] {provider}/{path.name}: "
                    f"{type(exc).__name__}: {message}"
                )
                summary["error"] += 1

                if args.execute:
                    err.write_text(
                        f"Error type: {type(exc).__name__}\n"
                        f"Error message: {message}\n",
                        encoding="utf-8",
                    )

                # Do not make the same doomed request for every report when
                # the provider reports exhausted credits/quota or a suspended
                # account. Record the first failure and skip the remaining cases.
                lowered = message.casefold()
                quota_failure = any(token in lowered for token in (
                    "insufficient balance",
                    "credit balance is too low",
                    "insufficient_quota",
                    "exceeded_current_quota",
                    "account is suspended",
                    "billing hard limit",
                    "quota exceeded",
                ))
                if args.execute and quota_failure:
                    remaining = len(prepared) - item_index - 1
                    if remaining:
                        print(
                            f"[WARN] {provider}: quota/billing failure detected; "
                            f"skipping {remaining} remaining report(s) for this provider."
                        )
                        summary["skip"] += remaining
                    break

        for key in totals:
            totals[key] += summary[key]

        print(
            f"[SUMMARY] {provider}: OK={summary['ok']}, "
            f"ERROR={summary['error']}, SKIPPED={summary['skip']}"
        )

    print(
        f"\nFINAL SUMMARY: OK={totals['ok']}, "
        f"ERROR={totals['error']}, SKIPPED={totals['skip']}"
    )

    if not args.execute:
        print(
            "Dry run only. Add --execute to generate results. "
            "ChromaDB uses local embeddings; the first run may initialize the local model."
        )

    return 1 if totals["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
