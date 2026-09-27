# Backlog — LEDs

## Dota 2: efeitos de habilidade na WLED

Animações curtas por cima da barra de vida quando o herói usa algo.

### Regras (padrão das integrações de jogo: Chroma, LIGHTSYNC, GameSense)

1. Curtos e por cima da base: 0,2 a 1 s, desenhados sobre o estado atual e
   voltando para a cor da vida; a informação crítica nunca some por muito
   tempo.
2. Prioridade fixa: morte > dano > ultimate > habilidade/item > base. Evento
   de prioridade menor não interrompe um maior (o pulso de dano sempre
   aparece).
3. Uma assinatura por tipo de evento: mesmo movimento e mesma cor sempre
   significam a mesma coisa, para ler de relance.
4. Sem estrobo: no máximo 3 piscadas por segundo (limite de fotossensibilidade
   do WCAG).
5. Detecção pelo GSI: o jogo não avisa "usou X"; o uso é deduzido pela recarga
   saltando de 0 para um valor alto. Habilidade sem recarga não é detectável.

### Eventos sugeridos

| Evento | Detecção | Animação | Duração |
|---|---|---|---|
| Ultimate usado | recarga do R salta | explosão do centro para as pontas, dourado/branco | ~0,8 s |
| Habilidade usada | recarga de Q/W/E/D/F salta | varredura rápida de uma ponta à outra, ciano | ~0,3 s |
| Blink | recarga do `item_blink` | ponto branco "teleportando" de um lado para o outro | ~0,3 s |
| BKB | recarga do `item_black_king_bar` | fita dourada pulsando devagar enquanto dura | ~9 s |
| Abate | `player.kills` sobe | faíscas douradas | ~1 s |
| Subir de nível | `hero.level` sobe | preenchimento branco de baixo para cima | ~0,6 s |

Referência de dados reais do GSI: `~/.cache/dota-rgb/gsi.json` (o dota-rgb
grava o último estado recebido).
