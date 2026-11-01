"""Run the main-branch direct-LLM experiment using sample.json by default."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases

REPORT_PATH = ROOT / "data" / "sast_reports" / "sample.json"
RESULTS_DIR = ROOT / "results"

PROVIDER_FOLDERS = {
    "openai": "GPT4.1",
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


def choose_provider() -> str:
    """Ask which configured LLM provider should generate the report."""
    providers = list(PROVIDER_FOLDERS)
    print("\nSelecione a LLM:")
    for index, provider in enumerate(providers, start=1):
        print(f"  {index}. {PROVIDER_LABELS[provider]} ({model_for(provider)})")

    while True:
        choice = input("Opção [1-4]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            return providers[int(choice) - 1]
        provider_match = next(
            (provider for provider in providers if provider.casefold() == choice.casefold()),
            None,
        )
        if provider_match:
            return provider_match
        print("Opção inválida. Escolha 1-4 ou informe o nome do provedor.")


def save_result(report_path: Path, provider: str, result) -> Path:
    """Save the result under a stable filename, replacing a previous run."""
    output_dir = RESULTS_DIR / PROVIDER_FOLDERS[provider]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_path.stem}_LLM.json"

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


def main() -> int:
    provider = choose_provider()

    if not REPORT_PATH.is_file():
        print(f"[ERROR] Relatório não encontrado: {REPORT_PATH}", file=sys.stderr)
        return 1

    try:
        report = SonarReport.model_validate_json(
            REPORT_PATH.read_text(encoding="utf-8")
        )
        if not report.issues:
            print(f"[ERROR] O relatório não contém achados: {REPORT_PATH}", file=sys.stderr)
            return 1

        print(f"Relatório de entrada: {REPORT_PATH.name}")
        print(f"Achados carregados: {len(report.issues)}")
        print(f"LLM selecionada: {PROVIDER_LABELS[provider]} ({model_for(provider)})")
        print("Modo: Direct LLM, sem RAG e sem contexto adicional.")
        print("\nGerando casos de teste...")

        result = generate_test_cases(report.issues, provider=provider)
        if len(result.test_cases) != len(report.issues):
            raise ValueError(
                f"Esperados {len(report.issues)} casos de teste, "
                f"mas a LLM retornou {len(result.test_cases)}."
            )

        output_path = save_result(REPORT_PATH, provider, result)
        print(f"[SAVED] {output_path.relative_to(ROOT)}")
        return 0

    except Exception as exc:
        error_dir = RESULTS_DIR / PROVIDER_FOLDERS[provider]
        error_dir.mkdir(parents=True, exist_ok=True)
        error_path = error_dir / f"{REPORT_PATH.stem}_ERROR.txt"
        error_path.write_text(
            f"Report: {REPORT_PATH.name}\n"
            f"Provider: {provider}\n"
            f"Model: {model_for(provider)}\n"
            f"Error: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"[ERROR FILE] {error_path.relative_to(ROOT)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
