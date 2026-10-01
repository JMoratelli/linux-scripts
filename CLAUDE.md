# Diretrizes para trabalhar neste repositório

- Não mencionar Claude, Anthropic ou IA/assistente em nenhum lugar do código,
  comentários, mensagens de commit ou descrições de PR deste projeto.
- Não adicionar linhas de `Co-Authored-By: Claude ...` (ou equivalentes) nos
  commits.
- Estrutura de `Linux/Scripts/`:
  - `FirstInstall.sh`: script principal, comum às duas máquinas. Pergunta a
    distro e se a máquina é pessoal ou corporativa, faz a instalação base
    (pacotes, extensões do VS Code, configurações do VS Code seguindo
    github.com/JMoratelli/VSCode, clonado em ~/projetos/vscode, login do
    GitHub CLI) e no fim roda os
    `*.sh` de `comum/` e depois os de `pessoal/` ou `corporativo/`.
  - `comum/`: scripts para as duas máquinas.
  - `pessoal/`: só a máquina de casa (periféricos, RGB, teclado, Dota).
  - `corporativo/`: só a máquina do trabalho.
  O perfil é decidido pela pasta: os scripts não recebem flag nem perguntam.
- Todo script nessas pastas precisa:
  - rodar sozinho, sem argumentos e sem perguntas (o FirstInstall o chama com
    stdin em `/dev/null`);
  - ser idempotente (rodar de novo atualiza, não quebra);
  - pedir root por conta própria quando precisar (`exec sudo bash "$0"`);
  - avisar e seguir em vez de abortar quando um passo falhar.
- Arquivos de apoio de um script ficam numa subpasta com o mesmo nome, ao lado
  dele (`pessoal/perifericos.sh` → `pessoal/perifericos/`). O FirstInstall só
  roda os `*.sh` do primeiro nível de cada pasta; o script acha a subpasta
  pelo próprio caminho (`dirname "${BASH_SOURCE[0]}"`).
- `pessoal/perifericos.sh` roda como root (sudo sozinho); `pessoal/leds.sh`
  roda como usuário (configuração do OpenRGB e do PipeWire ficam no home) e só
  usa sudo para instalar pacotes.
- Testes automáticos de `pessoal/` ficam em `Linux/Scripts/pessoal/tests/` e
  rodam antes de todo push: `cd Linux/Scripts/pessoal/tests && python3 -m
  unittest`. Eles nunca tocam na configuração real (pastas temporárias e um
  OpenRGB falso); os de interface precisam de sessão gráfica e são pulados sem
  ela.
