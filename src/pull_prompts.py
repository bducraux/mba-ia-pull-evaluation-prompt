"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

DICAS DE IMPLEMENTAÇÃO:

- O pull é feito pelo cliente do LangSmith:

      from langsmith import Client
      client = Client()
      prompt = client.pull_prompt(
          "leonanluppi/bug_to_user_story_v1",
          dangerously_pull_public_prompt=True,
      )

- O parâmetro `dangerously_pull_public_prompt=True` é obrigatório sempre que o
  identificador tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull
  por padrão porque um prompt do Hub é um objeto LangChain serializado, que pode
  vir de terceiros. Aqui o prompt é o do desafio, então o risco é conhecido.

- O retorno é um ChatPromptTemplate. Para extrair o conteúdo das mensagens,
  use a serialização nativa do LangChain (`prompt.messages`, e o atributo
  `.prompt.template` de cada mensagem).

- Use `save_yaml` de utils.py para gravar o resultado no arquivo .yml.
"""

import os
import sys
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"
PROMPT_KEY = "bug_to_user_story_v1"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_KEY}.yml"

# Tipo de mensagem do LangChain -> campo do YAML do projeto
ROLE_TO_FIELD = {
    "SystemMessagePromptTemplate": "system_prompt",
    "HumanMessagePromptTemplate": "user_prompt",
}


def prompt_to_dict(prompt) -> dict:
    """
    Converte o ChatPromptTemplate do Hub no formato YAML usado pelo projeto
    (system_prompt / user_prompt + metadados).
    """
    data = {
        "description": "Prompt para converter relatos de bugs em User Stories",
        "system_prompt": "",
        "user_prompt": "",
    }

    for message in prompt.messages:
        field = ROLE_TO_FIELD.get(type(message).__name__)
        template = getattr(getattr(message, "prompt", None), "template", None)
        if field and template is not None:
            data[field] = template

    metadata = getattr(prompt, "metadata", None) or {}
    data["version"] = "v1"
    data["source"] = SOURCE_PROMPT
    if metadata.get("lc_hub_commit_hash"):
        data["commit_hash"] = metadata["lc_hub_commit_hash"]
    data["pulled_at"] = date.today().isoformat()
    data["input_variables"] = sorted(prompt.input_variables)
    data["tags"] = ["bug-analysis", "user-story", "product-management"]

    return data


def pull_prompts_from_langsmith():
    """
    Faz pull do prompt semente e devolve o dicionário pronto para salvar.
    Levanta exceção com mensagem clara em caso de falha.
    """
    client = Client()

    print(f"   Puxando prompt do LangSmith Hub: {SOURCE_PROMPT}")
    try:
        prompt = client.pull_prompt(SOURCE_PROMPT, dangerously_pull_public_prompt=True)
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg or "404" in error_msg:
            raise RuntimeError(f"Prompt '{SOURCE_PROMPT}' não encontrado no Hub.") from e
        if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg:
            raise RuntimeError("Credenciais inválidas: confira LANGSMITH_API_KEY no .env.") from e
        raise RuntimeError(f"Falha ao puxar '{SOURCE_PROMPT}': {e}") from e

    print(f"   ✓ Prompt carregado ({len(prompt.messages)} mensagens)")
    return {PROMPT_KEY: prompt_to_dict(prompt)}


def main():
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    try:
        data = pull_prompts_from_langsmith()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1

    if not save_yaml(data, str(OUTPUT_PATH)):
        return 1

    print(f"   ✓ Prompt salvo em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
