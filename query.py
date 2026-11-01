"""CLI: run the direct SAST-to-LLM experiment for one or all providers."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases

DEFAULT_REPORT = ROOT / "data" / "sast_reports" / "sample.json"
PROVIDER_FOLDERS = {
    "openai": "GPT5.5",
    "gemini": "Gemini",
    "kimi": "Kimi",
    "claude": "Claude",
}


def choose_providers() -> list[str]:
    print("\nSelecione a LLM:")
    print("  1. OpenAI / GPT")
    print("  2. Google Gemini")
    print("  3. Kimi")
    print("  4. Anthropic Claude")
    print("  5. Todas")
    options = {"1": "openai", "2": "gemini", "3": "kimi", "4": "claude"}
    while True:
        choice = input("Opção [5]: ").strip() or "5"
        if choice == "5":
            return list(PROVIDER_FOLDERS)
        if choice in options:
            return [options[choice]]
        print("Opção inválida. Digite de 1 a 5.")


def model_for(provider: str) -> str:
    return {
        "openai": settings.openai_chat_model,
        "gemini": settings.gemini_model,
        "kimi": settings.kimi_model,
        "claude": settings.claude_model,
    }[provider]


def save_result(report_path: Path, provider: str, result) -> Path:
    output_dir = ROOT / "results" / PROVIDER_FOLDERS[provider]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report_path.stem}_LLM.json"
    if output_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = output_dir / f"{report_path.stem}_LLM_{stamp}.json"
    payload = result.model_dump(mode="json")
    if isinstance(payload, dict):
        payload["_metadata"] = {
            "provider": provider,
            "model": model_for(provider),
            "source_report": report_path.name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(output_path)
    return output_path


def main() -> None:
    raw_path = input(f"Caminho do relatório SAST [{DEFAULT_REPORT}]: ").strip()
    report_path = Path(raw_path) if raw_path else DEFAULT_REPORT
    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path).resolve()
    if not report_path.is_file():
        raise SystemExit(f"Arquivo não encontrado: {report_path}")

    report = SonarReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    print(f"Carregados {len(report.issues)} achado(s) de {report_path}.")
    context = input("Contexto/foco adicional (Enter para ignorar): ").strip()
    providers = choose_providers()

    for provider in providers:
        print(f"\nExecutando {provider} ({model_for(provider)})...")
        try:
            result = generate_test_cases(report.issues, context, provider=provider)
            print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
            print(f"[SAVED] {save_result(report_path, provider, result).resolve()}")
        except Exception as exc:
            print(f"[ERROR] {provider}: {type(exc).__name__}: {exc}")
            if len(providers) == 1:
                raise


if __name__ == "__main__":
    main()
