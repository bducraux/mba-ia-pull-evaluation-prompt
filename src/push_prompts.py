"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

DICAS DE IMPLEMENTAÇÃO:

- O push é feito pelo cliente do LangSmith:

      from langsmith import Client
      from langchain_core.prompts import ChatPromptTemplate

      client = Client()
      prompt = ChatPromptTemplate.from_messages([
          ("system", system_prompt),
          ("user", user_prompt),
      ])
      url = client.push_prompt(
          f"{username}/bug_to_user_story_v2",
          object=prompt,
          is_public=True,
          description="...",
          tags=[...],
      )

- `username` vem de USERNAME_LANGSMITH_HUB no .env e precisa ser o seu handle
  do Hub. Se você ainda não tem um handle, veja as instruções no .env.example.

- A variável do template precisa ser {bug_report}, que é a chave de entrada
  usada no dataset de avaliação.

- Use `load_yaml` de utils.py para ler o arquivo .yml.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header

load_dotenv()

PROMPT_KEY = "bug_to_user_story_v2"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_KEY}.yml"
REQUIRED_VARIABLE = "bug_report"


def build_readme(prompt_data: dict) -> str:
    """Monta o README exibido no Hub com as técnicas aplicadas."""
    techniques = "\n".join(f"- {t}" for t in prompt_data.get("techniques_applied", []))
    return (
        f"# {PROMPT_KEY}\n\n"
        f"{prompt_data.get('description', '')}\n\n"
        f"## Técnicas aplicadas\n\n{techniques}\n\n"
        f"Versão: {prompt_data.get('version', '')}\n"
    )


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_data["system_prompt"]),
        ("user", prompt_data["user_prompt"]),
    ])

    techniques = prompt_data.get("techniques_applied", [])
    tags = list(dict.fromkeys(prompt_data.get("tags", []) + techniques))

    client = Client()
    print(f"   Fazendo push de {prompt_name} (público)...")

    try:
        url = client.push_prompt(
            prompt_name,
            object=prompt,
            is_public=True,
            description=prompt_data.get("description", ""),
            readme=build_readme(prompt_data),
            tags=tags,
            commit_description=prompt_data.get("changelog") or None,
        )
    except Exception as e:
        error_msg = str(e).lower()
        # O Hub recusa commit idêntico ao último; metadados já foram atualizados.
        if "nothing to commit" in error_msg or "409" in error_msg:
            print("   ⚠️  Conteúdo idêntico ao último commit; nada novo para enviar.")
            print(f"   ✓ https://smith.langchain.com/hub/{prompt_name}")
            return True
        print(f"❌ Falha no push de '{prompt_name}': {e}")
        if "handle" in error_msg or "403" in error_msg or "404" in error_msg:
            print("   Confira se USERNAME_LANGSMITH_HUB é o seu handle público do Hub.")
        return False

    print(f"   ✓ Push concluído: {url}")
    print(f"   ✓ Tags: {', '.join(tags)}")
    return True


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []

    for field in ("description", "system_prompt", "user_prompt", "version"):
        if not str(prompt_data.get(field, "")).strip():
            errors.append(f"Campo obrigatório vazio ou ausente: {field}")

    full_text = f"{prompt_data.get('system_prompt', '')}\n{prompt_data.get('user_prompt', '')}"
    if "[TODO]" in full_text or "TODO" in prompt_data.get("system_prompt", ""):
        errors.append("O prompt ainda contém TODOs")

    if f"{{{REQUIRED_VARIABLE}}}" not in prompt_data.get("user_prompt", ""):
        errors.append(f"user_prompt precisa conter a variável {{{REQUIRED_VARIABLE}}}")

    techniques = prompt_data.get("techniques_applied", [])
    if len(techniques) < 2:
        errors.append(f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}")

    if not errors:
        try:
            template = ChatPromptTemplate.from_messages([
                ("system", prompt_data["system_prompt"]),
                ("user", prompt_data["user_prompt"]),
            ])
            if set(template.input_variables) != {REQUIRED_VARIABLE}:
                errors.append(
                    f"Variáveis inesperadas no template: {sorted(template.input_variables)} "
                    f"(use {{{{ }}}} para chaves literais)"
                )
        except Exception as e:
            errors.append(f"Template inválido: {e}")

    return (len(errors) == 0, errors)


def main():
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS")

    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return 1

    data = load_yaml(str(PROMPT_PATH))
    if not data or PROMPT_KEY not in data:
        print(f"❌ Chave '{PROMPT_KEY}' não encontrada em {PROMPT_PATH}")
        return 1

    prompt_data = data[PROMPT_KEY]

    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt inválido:")
        for error in errors:
            print(f"   - {error}")
        return 1
    print("   ✓ Prompt validado")

    username = os.getenv("USERNAME_LANGSMITH_HUB")
    prompt_name = f"{username}/{PROMPT_KEY}"

    return 0 if push_prompt_to_langsmith(prompt_name, prompt_data) else 1


if __name__ == "__main__":
    sys.exit(main())
