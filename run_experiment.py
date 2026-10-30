
import json
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from backend.config import settings
from backend.schemas import SonarReport
from backend.openai_service import generate_test_cases


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "data" / "sast_reports"
RESULTS_DIR = BASE_DIR / "results"

VALID_PROVIDERS = {"gemini", "kimi", "claude"}


def main():
    provider = settings.llm_provider.strip().lower()

    if provider not in VALID_PROVIDERS:
        print("LLM_PROVIDER deve ser gemini, kimi ou claude.")
        sys.exit(1)

    if provider == "gemini":
        if not settings.google_api_key or not settings.gemini_model:
            print("Configure GOOGLE_API_KEY e GEMINI_MODEL no .env.")
            sys.exit(1)
    elif provider == "kimi":
        if not settings.kimi_api_key or not settings.kimi_model:
            print("Configure KIMI_API_KEY e KIMI_MODEL no .env.")
            sys.exit(1)
    elif provider == "claude":
        if not settings.anthropic_api_key or not settings.claude_model:
            print("Configure ANTHROPIC_API_KEY e CLAUDE_MODEL no .env.")
            sys.exit(1)

    output_dir = RESULTS_DIR / provider.capitalize()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(INPUT_DIR.glob("GT*.json"))

    if not input_files:
        print(f"Nenhum relatório encontrado em: {INPUT_DIR}")
        sys.exit(1)

    print(f"Provedor: {provider}")
    print(f"Destino: {output_dir}")
    print(f"Relatórios: {len(input_files)}")
    print("Arquivos existentes não serão sobrescritos.")

    sucessos = 0
    erros = 0
    pulados = 0

    for input_file in input_files:
        output_file = output_dir / f"{input_file.stem}_LLM.json"

        if output_file.exists():
            print(f"[PULADO] {input_file.name}: resultado já existe.")
            pulados += 1
            continue

        print(f"\nProcessando {input_file.name}...")

        try:
            raw_data = json.loads(
                input_file.read_text(encoding="utf-8")
            )
            report = SonarReport.model_validate(raw_data)

            if not report.issues:
                print(f"[ERRO] {input_file.name}: sem ocorrências.")
                erros += 1
                continue

            result = generate_test_cases(report.issues)

            if len(result.test_cases) != len(report.issues):
                print(
                    f"[ERRO] {input_file.name}: esperados "
                    f"{len(report.issues)} casos, recebidos "
                    f"{len(result.test_cases)}."
                )
                erros += 1
                continue

            content = json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ) + "\n"

            # Modo exclusivo: falha se o arquivo já existir.
            with output_file.open("x", encoding="utf-8") as file:
                file.write(content)

            print(f"[OK] Resultado salvo: {output_file.name}")
            sucessos += 1

        except FileExistsError:
            print(f"[PULADO] {output_file.name} já existe.")
            pulados += 1
        except (json.JSONDecodeError, ValidationError) as exc:
            print(f"[ERRO DE DADOS] {input_file.name}: {exc}")
            erros += 1
        except Exception as exc:
            print(f"[ERRO] {input_file.name}: {type(exc).__name__}: {exc}")
            erros += 1

        time.sleep(1)

    print("\n===== RESUMO =====")
    print(f"Sucessos: {sucessos}")
    print(f"Erros: {erros}")
    print(f"Pulados: {pulados}")
    print(f"Resultados em: {output_dir}")


if __name__ == "__main__":
    main()
