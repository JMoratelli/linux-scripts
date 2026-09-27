#!/usr/bin/env bash
#
# perifericos.sh
#
# Integra os perifericos ao sistema. Os arquivos instalados ficam em
# perifericos/ (ao lado deste script).
#
#   1. Headset Logitech G733 (dongle 046d:0b1f): o driver hid-logitech-hidpp
#      do kernel so conhece o G935. Instala um modulo DKMS que baixa o fonte
#      do driver da versao exata de cada kernel e acrescenta o ID do G733;
#      a bateria aparece no upower / applet de bateria do KDE. Recompila
#      sozinho a cada atualizacao de kernel; se falhar, vale o modulo original.
#
#   2. LEDs Logitech (G733 e G502 Lightspeed) sempre apagados: os
#      dispositivos nao guardam o estado dos LEDs, entao uma regra do udev
#      detecta quando ficam online e apaga todas as zonas via HID++ (0x8070).
#
#   3. Audio automatico: quando o G733 liga, a saida padrao vira o fone;
#      quando desliga, volta para o HDMI (servico de usuario fone-audio-auto).
#
#   4. Teclado Redragon K629 Phantom Pro (so no cabo USB, 258a:0049):
#        - regra udev: acesso pelo usuario logado (cabo e dongle sem fio) e
#          link fixo /dev/redragon-k629 na interface de controle
#        - redragon-led: cor/efeito gravados no teclado (blocos 0xB6/0xB8;
#          NUNCA o 0xD4, que tem o keymap e o firmware)
#        - teclado-barras: espectro de audio em barras, cor por tecla ao vivo
#          (report 0x08, nao grava nada no teclado); sobe sozinho quando o
#          cabo conecta e para quando desconecta
#
# Uso:
#   chmod +x perifericos.sh
#   ./perifericos.sh              instala / atualiza
#   ./perifericos.sh --remover    desfaz tudo
#
# Na mao: logi-leds-off, redragon-led status|off|set ...

set -uo pipefail

if [ "$EUID" -ne 0 ]; then
  exec sudo bash "$0" "$@"
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/perifericos"
REAL_USER="${SUDO_USER:-}"

DKMS_NAME="hidpp-g733"
DKMS_VER="1.0"
DKMS_SRC="/usr/src/${DKMS_NAME}-${DKMS_VER}"
LED_BIN="/usr/local/bin/logi-leds-off"
LED_RULE="/etc/udev/rules.d/90-logi-leds-off.rules"
LED_UNIT="/etc/systemd/system/logi-leds-off@.service"
AUDIO_BIN="/usr/local/bin/fone-audio-auto"
AUDIO_UNIT="/etc/systemd/user/fone-audio-auto.service"
KB_LIB="/usr/local/lib/redragon"
KB_RULE="/etc/udev/rules.d/60-redragon-k629.rules"
KB_UNIT="/etc/systemd/user/teclado-barras.service"

user_systemctl() {
  # servicos de usuario na sessao de quem chamou o sudo (se houver)
  [ -n "$REAL_USER" ] && systemctl --user -M "${REAL_USER}@" "$@" 2>/dev/null
}

reload_driver() {
  # O mouse continua funcionando durante a troca (cai no hid-generic por
  # alguns instantes).
  modprobe -r hid_logitech_hidpp 2>/dev/null || rmmod hid_logitech_hidpp 2>/dev/null || true
  modprobe hid_logitech_hidpp || echo "  [aviso] falha ao carregar hid_logitech_hidpp"
}

remover() {
  echo "=== Removendo integracao dos perifericos ==="
  user_systemctl disable --now fone-audio-auto.service
  user_systemctl stop teclado-barras.service
  systemctl --global disable fone-audio-auto.service 2>/dev/null
  dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all 2>/dev/null || true
  rm -rf "$DKMS_SRC" "$KB_LIB" /run/logi-leds-off
  rm -f "$LED_BIN" "$LED_RULE" "$LED_UNIT" "$AUDIO_BIN" "$AUDIO_UNIT" \
        "$KB_RULE" "$KB_UNIT" /usr/local/bin/redragon-led /usr/local/bin/teclado-barras
  systemctl daemon-reload
  user_systemctl daemon-reload
  udevadm control --reload
  depmod -a
  reload_driver
  echo "Concluido."
}

if [ "${1:-}" = "--remover" ]; then
  remover
  exit 0
fi

if [ ! -d "$SRC" ]; then
  echo "pasta $SRC nao encontrada (o script precisa da pasta perifericos/ ao lado)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
echo "=== Dependencias (dkms, headers do kernel, compilador, python) ==="
if command -v pacman >/dev/null 2>&1; then
  # headers para cada kernel instalado (linux, linux-lts, linux-cachyos...)
  headers=()
  for pkg in $(pacman -Qqo /usr/lib/modules/*/vmlinuz 2>/dev/null | sort -u); do
    headers+=("${pkg}-headers")
  done
  pacman -S --needed --noconfirm dkms python python-numpy libpulse curl clang lld llvm "${headers[@]}" || \
    echo "  [aviso] falha ao instalar dependencias"
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y dkms kernel-devel python3 python3-numpy pulseaudio-utils curl || \
    echo "  [aviso] falha ao instalar dependencias"
elif command -v apt >/dev/null 2>&1; then
  apt install -y dkms "linux-headers-$(uname -r)" python3 python3-numpy pulseaudio-utils curl || \
    echo "  [aviso] falha ao instalar dependencias"
fi

# ---------------------------------------------------------------------------
# 1. Headset G733: modulo DKMS com a bateria
# ---------------------------------------------------------------------------
echo "=== [1] G733: DKMS ${DKMS_NAME} ${DKMS_VER} ==="
dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all 2>/dev/null || true
rm -rf "$DKMS_SRC"
mkdir -p "$DKMS_SRC"
install -m644 "$SRC/hidpp-g733/dkms.conf" "$SRC/hidpp-g733/Makefile" "$SRC/hidpp-g733/Kbuild" "$DKMS_SRC/"
install -m755 "$SRC/hidpp-g733/prep.sh" "$DKMS_SRC/"

dkms add -m "$DKMS_NAME" -v "$DKMS_VER" || echo "  [aviso] dkms add falhou"
for build in /usr/lib/modules/*/build; do
  [ -d "$build" ] || continue
  kver=$(basename "$(dirname "$build")")
  echo "  compilando para $kver"
  nice -n 19 dkms install -m "$DKMS_NAME" -v "$DKMS_VER" -k "$kver" || \
    echo "  [aviso] falha no kernel $kver (o modulo original continua valendo)"
done
reload_driver

# ---------------------------------------------------------------------------
# 2. LEDs Logitech apagados ao conectar
# ---------------------------------------------------------------------------
echo "=== [2] LEDs Logitech: ${LED_BIN} + udev + systemd ==="
install -m755 "$SRC/logi-leds-off" "$LED_BIN"

cat > "$LED_UNIT" <<EOF
[Unit]
Description=Apaga os LEDs do periferico Logitech (%i)

[Service]
Type=oneshot
ExecStart=${LED_BIN} --ps %i
EOF

cat > "$LED_RULE" <<'EOF'
# Apaga os LEDs dos perifericos Logitech quando ficam online (perifericos.sh)
SUBSYSTEM=="power_supply", KERNEL=="hidpp_battery_*", ACTION=="add|change", ENV{POWER_SUPPLY_ONLINE}=="1", RUN+="/usr/bin/systemctl --no-block start logi-leds-off@%k.service"
# ao desligar, grava o estado para a proxima transicao ser detectada
SUBSYSTEM=="power_supply", KERNEL=="hidpp_battery_*", ACTION=="change", ENV{POWER_SUPPLY_ONLINE}=="0", RUN+="/usr/bin/systemctl --no-block start logi-leds-off@%k.service"
EOF

# ---------------------------------------------------------------------------
# 3. Audio automatico: G733 ligado -> fone; desligado -> HDMI
# ---------------------------------------------------------------------------
echo "=== [3] Audio automatico: ${AUDIO_BIN} (servico de usuario) ==="
install -m755 "$SRC/fone-audio-auto" "$AUDIO_BIN"
cat > "$AUDIO_UNIT" <<EOF
[Unit]
Description=Troca a saida de audio quando o headset G733 liga/desliga
After=pipewire-pulse.service

[Service]
ExecStart=${AUDIO_BIN}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --global enable fone-audio-auto.service

# ---------------------------------------------------------------------------
# 4. Teclado Redragon K629 (cabo USB)
# ---------------------------------------------------------------------------
echo "=== [4] Teclado Redragon K629: udev + redragon-led + teclado-barras ==="
mkdir -p "$KB_LIB"
install -m755 "$SRC/redragon-led" "$SRC/teclado-barras" "$KB_LIB/"
install -m644 "$SRC/b8-modelo.bin" "$KB_LIB/"
ln -sf "$KB_LIB/redragon-led" /usr/local/bin/redragon-led
ln -sf "$KB_LIB/teclado-barras" /usr/local/bin/teclado-barras

rm -f /etc/udev/rules.d/60-redragon-compx.rules       # nome antigo desta regra
cat > "$KB_RULE" <<'EOF'
# Redragon K629 Phantom Pro (perifericos.sh)
# acesso pelo usuario logado: dongle sem fio (Compx 25a7:fa70) e cabo USB (Sinowealth 258a:0049)
SUBSYSTEMS=="usb|hidraw", ATTRS{idVendor}=="25a7", ATTRS{idProduct}=="fa70", TAG+="uaccess"
SUBSYSTEMS=="usb|hidraw", ATTRS{idVendor}=="258a", ATTRS{idProduct}=="0049", TAG+="uaccess"
# interface de controle no cabo (feature reports 5, 6 e 8): link fixo e barras de audio.
# Em duas regras porque os ATTRS de uma mesma regra precisam casar no mesmo pai
# (idVendor fica no dispositivo USB, bInterfaceNumber na interface).
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="258a", ATTRS{idProduct}=="0049", ENV{REDRAGON_K629}="1"
SUBSYSTEM=="hidraw", ENV{REDRAGON_K629}=="1", ATTRS{bInterfaceNumber}=="01", SYMLINK+="redragon-k629", TAG+="systemd", ENV{SYSTEMD_USER_WANTS}+="teclado-barras.service"
EOF

cat > "$KB_UNIT" <<EOF
[Unit]
Description=Barras de audio no teclado Redragon K629 (cabo USB)
BindsTo=dev-redragon\\x2dk629.device
After=dev-redragon\\x2dk629.device pipewire-pulse.service

[Service]
ExecStart=${KB_LIB}/teclado-barras
Restart=on-failure
RestartSec=3
EOF

# ---------------------------------------------------------------------------
# Aplicar
# ---------------------------------------------------------------------------
rm -rf /run/logi-leds-off
systemctl daemon-reload
udevadm control --reload
udevadm trigger --subsystem-match=hidraw --action=add
user_systemctl daemon-reload
user_systemctl start fone-audio-auto.service
"$LED_BIN" || echo "  (nenhum dispositivo Logitech ligado agora; os LEDs serao apagados ao conectar)"

echo ""
echo "======================================"
echo " Concluido."
echo " Bateria do G733/G502: applet de bateria do KDE (upower)."
echo " LEDs Logitech: apagados automaticamente sempre que o dispositivo conectar."
echo " Audio: G733 ligado -> fone; desligado -> HDMI."
echo " Teclado K629: barras de audio sempre que estiver no cabo USB."
echo " Para desfazer: ./perifericos.sh --remover"
echo "======================================"
