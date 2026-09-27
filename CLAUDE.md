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
- Arquivos de apoio de um script ficam numa subpasta com o mesmo nome, ao lado
  dele (`perifericos.sh` → `perifericos/`, `leds.sh` → `leds/`). O FirstInstall
  só roda os `*.sh` do nível de cima, nunca o que está nas subpastas; o script
  acha a pasta pelo próprio caminho (`dirname "${BASH_SOURCE[0]}"`).
- Perfil da máquina: o FirstInstall pergunta uma vez se é pessoal ou
  corporativa e passa `--pessoal` ou `--corporativo` para cada script (com
  stdin em `/dev/null`). Tudo que é do computador de casa (RGB, teclado,
  periféricos específicos) só instala com `--pessoal`. Rodando um script
  sozinho sem a flag, ele pergunta se houver terminal; sem terminal, assume
  corporativo.
- `perifericos.sh` roda como root (sudo sozinho); `leds.sh` roda como usuário
  (configuração do OpenRGB e do PipeWire ficam no home) e só usa sudo para
  instalar pacotes.
