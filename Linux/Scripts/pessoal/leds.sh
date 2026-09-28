#!/usr/bin/env bash
#
# leds.sh
#
# RGB do gabinete reativo ao som, via OpenRGB + Effects Plugin. Os arquivos
# instalados ficam em leds/ (ao lado deste script).
#
#   - "RGB Audio": entrada virtual do PipeWire com o que toca na saida
#     padrao (acompanha a troca fone/HDMI)
#   - rgb_config.py: gera do zero a configuracao do OpenRGB (detectores
#     ignorados, WLED da mesa, tamanho/nome das zonas ARGB) e o perfil
#     "Gabinete" com um efeito de audio por zona:
#       fan frontal = grave, fan superior 1 = medio, fan superior 2 = agudo,
#       H100 RGB, fonte, GPU e placa-mae discretos, WLED da mesa
#   - openrgb-gabinete: abre o OpenRGB na bandeja com o servidor ligado,
#     corrigindo antes o indice da "RGB Audio" no perfil e, depois, o
#     tamanho das zonas ARGB pelo SDK (fitas nao informam quantos LEDs tem)
#   - autostart do KDE so para o rgb-casa (na bandeja): abrir o rgb-casa sobe
#     o OpenRGB escondido e o dota-rgb; "Sair" nele apaga os LEDs e encerra tudo
#   - dota-rgb (servico de usuario): ao abrir o Dota 2 troca para o perfil
#     "Dota" e pinta teclado e gabinete com o estado da partida (Game State
#     Integration: habilidades/itens no teclado, vida/mana nos fans, cor do
#     time); ao fechar volta para o "Gabinete". dota-setup.py grava o arquivo
#     do GSI na pasta do Dota e a opcao -gamestateintegration no Steam.
#   - rgbsdk.py: cliente do SDK do OpenRGB usado pelos dois
#   - rgb-casa: janela simples (GTK4) para escolher o efeito de cada zona,
#     na bandeja do KDE; grava ~/.config/rgb-casa/config.json, gera os
#     perfis (rgb_config.py) e recarrega o OpenRGB na hora
#
# Os Logitech (G502/G733) ficam de fora do OpenRGB: os LEDs deles ficam sempre
# apagados pelo perifericos.sh. O teclado Redragon entra no OpenRGB como um
# dispositivo DDP (matriz 21x6) atraves da teclado-ponte do perifericos.sh.
#
# Roda como usuario (a configuracao e do usuario); so a instalacao de pacotes
# pede sudo.
#
# Maquina pessoal (pasta pessoal/: o FirstInstall so roda na pessoal).
#
# Uso:
#   ./leds.sh              instala / atualiza
#   ./leds.sh --remover    desfaz tudo (mantem os pacotes)

set -uo pipefail

if [ "$EUID" -eq 0 ]; then
  if [ -n "${SUDO_USER:-}" ]; then
    exec sudo -u "$SUDO_USER" bash "$0" "$@"
  fi
  echo "rode como usuario, nao como root"
  exit 1
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/leds"
CFG_DIR="$HOME/.config/rgb-gabinete"
PW_CONF="$HOME/.config/pipewire/pipewire.conf.d/90-rgb-audio.conf"
LIB="$HOME/.local/lib/rgb-gabinete"
LAUNCHER="$HOME/.local/bin/openrgb-gabinete"
DOTA_BIN="$HOME/.local/bin/dota-rgb"
DOTA_UNIT="$HOME/.config/systemd/user/dota-rgb.service"
AUTOSTART="$HOME/.config/autostart/openrgb-gabinete.desktop"
UI_BIN="$HOME/.local/bin/rgb-casa"
UI_DESKTOP="$HOME/.local/share/applications/rgb-casa.desktop"
UI_AUTOSTART="$HOME/.config/autostart/rgb-casa.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

stop_openrgb() {
  # o OpenRGB regrava a configuracao ao sair; fecha antes de mexer nela.
  # Primeiro o supervisor (openrgb-gabinete), senao ele reabre o OpenRGB.
  pkill -TERM -f "^python3 .*/openrgb-gabinete" 2>/dev/null
  sleep 1
  pkill -x openrgb 2>/dev/null || return 0
  for _ in $(seq 15); do
    pgrep -x openrgb >/dev/null || return 0
    sleep 1
  done
  pkill -9 -x openrgb 2>/dev/null || true
}

restart_audio() {
  systemctl --user restart pipewire pipewire-pulse wireplumber 2>/dev/null || \
    echo "  [aviso] reinicie a sessao para ativar a entrada 'RGB Audio'"
}

remover() {
  echo "=== Removendo RGB do gabinete ==="
  systemctl --user disable --now dota-rgb.service 2>/dev/null
  pkill -f "^python3 .*/rgb-casa" 2>/dev/null
  stop_openrgb
  rm -f "$LAUNCHER" "$DOTA_BIN" "$DOTA_UNIT" "$AUTOSTART" "$PW_CONF" \
        "$UI_BIN" "$UI_DESKTOP" "$UI_AUTOSTART" "$ICON_DIR/rgb-casa.svg" \
        "$HOME/.config/OpenRGB/profiles/Gabinete.json" "$HOME/.config/OpenRGB/profiles/Dota.json"
  rm -rf "$CFG_DIR" "$LIB"
  systemctl --user daemon-reload
  restart_audio
  echo "Concluido (pacotes e o restante da configuracao do OpenRGB foram mantidos)."
}

REMOVER=0
[ "${1:-}" = "--remover" ] && REMOVER=1

if [ "$REMOVER" -eq 1 ]; then
  remover
  exit 0
fi


if [ ! -d "$SRC" ]; then
  echo "pasta $SRC nao encontrada (o script precisa da pasta leds/ ao lado)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Pacotes
# ---------------------------------------------------------------------------
echo "=== Pacotes: OpenRGB, OpenAL, PipeWire/Pulse, Effects Plugin ==="
if command -v pacman >/dev/null 2>&1; then
  missing=()
  # OpenRGB + captura de audio (OpenAL/PipeWire) + janela GTK4 + ferramentas do menu
  for pkg in openrgb openal libpulse pipewire pipewire-pulse wireplumber \
             python python-gobject gtk4 libadwaita adwaita-icon-theme \
             gtk-update-icon-cache desktop-file-utils; do
    pacman -Q "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    sudo pacman -S --needed --noconfirm "${missing[@]}" || echo "  [aviso] falha ao instalar: ${missing[*]}"
  fi
  if ! pacman -Q openrgb-plugin-effects >/dev/null 2>&1; then
    AUR_HELPER=$(command -v paru || command -v yay || true)
    if [ -z "$AUR_HELPER" ]; then
      # sem ajudante do AUR (rodando fora do FirstInstall): instala o paru
      sudo pacman -S --needed --noconfirm base-devel git && {
        tmpdir=$(mktemp -d)
        git clone https://aur.archlinux.org/paru-bin.git "$tmpdir/paru-bin" && \
          (cd "$tmpdir/paru-bin" && makepkg -si --noconfirm)
        rm -rf "$tmpdir"
      }
      AUR_HELPER=$(command -v paru || command -v yay || true)
    fi
    if [ -n "$AUR_HELPER" ]; then
      # compilacao do plugin (Qt) limitada para nao estourar a memoria
      MAKEFLAGS="-j4" "$AUR_HELPER" -S --needed --noconfirm openrgb-plugin-effects || \
        echo "  [aviso] falha ao instalar openrgb-plugin-effects (AUR)"
    else
      echo "  [aviso] sem paru/yay: instale openrgb-plugin-effects do AUR"
    fi
  fi
else
  echo "  [aviso] distro sem pacman: instale OpenRGB 1.0, openal e o OpenRGB Effects Plugin manualmente"
fi

# ---------------------------------------------------------------------------
# Entrada de audio "RGB Audio"
# ---------------------------------------------------------------------------
echo "=== PipeWire: entrada 'RGB Audio' ==="
mkdir -p "$(dirname "$PW_CONF")"
if ! cmp -s "$SRC/90-rgb-audio.conf" "$PW_CONF"; then
  install -m644 "$SRC/90-rgb-audio.conf" "$PW_CONF"
  restart_audio
else
  echo "  ja configurada"
fi

# ---------------------------------------------------------------------------
# Configuracao do OpenRGB + perfil de efeitos
# ---------------------------------------------------------------------------
echo "=== OpenRGB: configuracao e perfil 'Gabinete' ==="
stop_openrgb
mkdir -p "$CFG_DIR" "$LIB" "$HOME/.local/bin"
rm -f "$CFG_DIR/rgb-config.py"                      # versao antiga ficava aqui
install -m644 "$SRC/rgbsdk.py" "$SRC/rgb_config.py" "$SRC/tray.py" "$LIB/"
python3 "$LIB/rgb_config.py" || echo "  [aviso] falha ao gerar a configuracao do OpenRGB"

# ---------------------------------------------------------------------------
# Inicializacao
# ---------------------------------------------------------------------------
echo "=== Inicializacao: openrgb-gabinete (o rgb-casa e quem abre) ==="
install -m755 "$SRC/openrgb-gabinete" "$SRC/dota-rgb" "$SRC/dota-setup.py" "$SRC/rgb-casa" "$LIB/"
rm -f "$LAUNCHER"                                   # versao antiga era um arquivo solto
ln -sf "$LIB/openrgb-gabinete" "$LAUNCHER"
ln -sf "$LIB/dota-rgb" "$DOTA_BIN"
ln -sf "$LIB/rgb-casa" "$UI_BIN"
# o OpenRGB nao tem mais autostart proprio: o rgb-casa abre e fecha ele
rm -f "$HOME/.config/autostart/OpenRGB.desktop" "$AUTOSTART"

# ---------------------------------------------------------------------------
# rgb-casa: janela + icone + bandeja
# ---------------------------------------------------------------------------
echo "=== rgb-casa: janela, icone e bandeja ==="
install -Dm644 "$SRC/icons/hicolor/scalable/apps/rgb-casa.svg" "$ICON_DIR/rgb-casa.svg"
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
mkdir -p "$(dirname "$UI_DESKTOP")"
cat > "$UI_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=RGB de casa
Comment=Efeitos de LED do gabinete, teclado e fita
Exec=${UI_BIN}
Icon=rgb-casa
Categories=Settings;HardwareSettings;
StartupWMClass=br.com.jurandir.RgbCasa
EOF
cat > "$UI_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=RGB de casa (bandeja)
Exec=${UI_BIN} --tray
Icon=rgb-casa
X-KDE-autostart-after=panel
EOF
update-desktop-database -q "$(dirname "$UI_DESKTOP")" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Dota 2
# ---------------------------------------------------------------------------
echo "=== Dota 2: GSI + servico dota-rgb ==="
python3 "$LIB/dota-setup.py" || echo "  [aviso] falha ao configurar o GSI do Dota"
mkdir -p "$(dirname "$DOTA_UNIT")"
cat > "$DOTA_UNIT" <<EOF
[Unit]
Description=RGB seguindo o Dota 2 (OpenRGB + Game State Integration)
After=graphical-session.target

[Service]
ExecStart=${DOTA_BIN}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
# quem liga e desliga o dota-rgb e o rgb-casa (conforme o modo Dota dele)
systemctl --user disable --now dota-rgb.service 2>/dev/null

if [ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
  pkill -f "^python3 .*/rgb-casa" 2>/dev/null          # versao nova do rgb-casa
  sleep 1
  setsid "$UI_BIN" --tray >/dev/null 2>&1 < /dev/null &   # ele sobe o resto
  echo "  rgb-casa (bandeja) iniciado; ele abre o OpenRGB escondido"
fi

echo ""
echo "======================================"
echo " Concluido."
echo " O rgb-casa abre no login (bandeja) e sobe os efeitos; Sair desliga tudo."
echo " Com o Dota 2 aberto, o perfil muda sozinho para o do jogo."
echo " Para trocar os efeitos: RGB de casa (menu ou bandeja)."
echo " Para desfazer: ./leds.sh --remover"
echo "======================================"
