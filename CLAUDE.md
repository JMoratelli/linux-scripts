# Diretrizes para trabalhar neste repositório

- Não mencionar Claude, Anthropic ou IA/assistente em nenhum lugar do código,
  comentários, mensagens de commit ou descrições de PR deste projeto.
- Não adicionar linhas de `Co-Authored-By: Claude ...` (ou equivalentes) nos
  commits.
- `Linux/Scripts/FirstInstall.sh` é o script principal de instalação e, ao
  final, executa todos os outros `*.sh` de `Linux/Scripts/` (função
  `run_extra_scripts`). Todo script novo nessa pasta precisa, portanto:
  - rodar sozinho, sem argumentos e sem perguntas obrigatórias;
  - ser idempotente (rodar de novo atualiza, não quebra);
  - pedir root por conta própria quando precisar (`exec sudo bash "$0"`);
  - avisar e seguir em vez de abortar quando um passo falhar.
  Scripts auxiliares que não devem ser chamados pelo FirstInstall ficam fora
  dessa pasta ou sem a extensão `.sh`.
