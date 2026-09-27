#!/usr/bin/env bash
#
# perifericos.sh
#
# Integra os perifericos Logitech ao sistema:
#
#   - Headset G733 (dongle 046d:0b1f): o driver hid-logitech-hidpp do kernel
#     so conhece o G935. Este script instala um modulo DKMS que baixa o fonte
#     do driver da versao exata de cada kernel e acrescenta o ID do G733, de
#     modo que a bateria aparece no upower / applet de bateria do KDE.
#     O modulo e recompilado sozinho a cada atualizacao de kernel; se falhar,
#     o modulo original do kernel continua valendo.
#
#   - LEDs (G733 e G502 Lightspeed): os dispositivos nao guardam o estado dos
#     LEDs e acendem de novo sempre que ligam. Uma regra do udev detecta quando
#     o dispositivo fica online (bateria do hidpp com ONLINE=1) e dispara um
#     servico que apaga todas as zonas via HID++ (feature 0x8070).
#
# Uso:
#   chmod +x perifericos.sh
#   ./perifericos.sh              instala / atualiza
#   ./perifericos.sh --remover    desfaz tudo
#
# Apagar os LEDs na mao, a qualquer momento: logi-leds-off

set -uo pipefail

if [ "$EUID" -ne 0 ]; then
  exec sudo bash "$0" "$@"
fi

DKMS_NAME="hidpp-g733"
DKMS_VER="1.0"
DKMS_SRC="/usr/src/${DKMS_NAME}-${DKMS_VER}"
LED_BIN="/usr/local/bin/logi-leds-off"
UDEV_RULE="/etc/udev/rules.d/90-logi-leds-off.rules"
UNIT="/etc/systemd/system/logi-leds-off@.service"

reload_driver() {
  # O mouse continua funcionando durante a troca (cai no hid-generic por
  # alguns instantes).
  modprobe -r hid_logitech_hidpp 2>/dev/null || rmmod hid_logitech_hidpp 2>/dev/null || true
  modprobe hid_logitech_hidpp || echo "  [aviso] falha ao carregar hid_logitech_hidpp"
}

remover() {
  echo "=== Removendo integracao dos perifericos ==="
  dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all 2>/dev/null || true
  rm -rf "$DKMS_SRC"
  rm -f "$LED_BIN" "$UDEV_RULE" "$UNIT"
  rm -rf /run/logi-leds-off
  systemctl daemon-reload
  udevadm control --reload
  depmod -a
  reload_driver
  echo "Concluido."
}

if [ "${1:-}" = "--remover" ]; then
  remover
  exit 0
fi

# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
echo "=== Dependencias (dkms, headers do kernel, compilador) ==="
if command -v pacman >/dev/null 2>&1; then
  # headers para cada kernel instalado (linux, linux-lts, linux-cachyos...)
  headers=()
  for pkg in $(pacman -Qqo /usr/lib/modules/*/vmlinuz 2>/dev/null | sort -u); do
    headers+=("${pkg}-headers")
  done
  pacman -S --needed --noconfirm dkms python curl clang lld llvm "${headers[@]}" || \
    echo "  [aviso] falha ao instalar dependencias"
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y dkms kernel-devel python3 curl || echo "  [aviso] falha ao instalar dependencias"
elif command -v apt >/dev/null 2>&1; then
  apt install -y dkms "linux-headers-$(uname -r)" python3 curl || echo "  [aviso] falha ao instalar dependencias"
fi

# ---------------------------------------------------------------------------
# Modulo DKMS: hid-logitech-hidpp com o G733
# ---------------------------------------------------------------------------
echo "=== DKMS: ${DKMS_NAME} ${DKMS_VER} ==="
dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all 2>/dev/null || true
rm -rf "$DKMS_SRC"
mkdir -p "$DKMS_SRC"

cat > "$DKMS_SRC/dkms.conf" <<'EOF'
PACKAGE_NAME="hidpp-g733"
PACKAGE_VERSION="1.0"
PRE_BUILD="prep.sh ${kernelver}"
MAKE[0]="make KVER=${kernelver}"
CLEAN="true"
BUILT_MODULE_NAME[0]="hid-logitech-hidpp"
DEST_MODULE_LOCATION[0]="/updates/dkms"
AUTOINSTALL="yes"
EOF

# o dkms passa KERNELRELEASE na linha de comando, entao o obj-m fica no
# Kbuild e o Makefile so tem o alvo externo
echo 'obj-m := hid-logitech-hidpp.o' > "$DKMS_SRC/Kbuild"
cat > "$DKMS_SRC/Makefile" <<'EOF'
KVER ?= $(shell uname -r)
KDIR := /usr/lib/modules/$(KVER)/build
# o kernel do CachyOS e compilado com clang/LTO; o modulo precisa do mesmo
LLVMFLAG := $(if $(shell grep -s '^CONFIG_CC_IS_CLANG=y' $(KDIR)/.config),LLVM=1)
all:
	$(MAKE) -j2 -C $(KDIR) M=$(CURDIR) $(LLVMFLAG) modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVMFLAG) clean
EOF

cat > "$DKMS_SRC/prep.sh" <<'EOF'
#!/bin/sh
# Baixa o driver hid-logitech-hidpp da versao exata do kernel alvo e
# acrescenta o ID do G733 (046d:0b1f) com a mesma configuracao do G935.
set -e
kver="$1"
base="${kver%%-*}"                                 # 7.2.8-1-cachyos -> 7.2.8
case "$base" in *.*.0) base="${base%.0}" ;; esac   # 7.3.0 -> 7.3 (nome da tag)
url="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/hid"
mkdir -p usbhid
curl -fsSL --retry 3 -o hid-logitech-hidpp.c "$url/hid-logitech-hidpp.c?h=v$base"
curl -fsSL --retry 3 -o hid-ids.h            "$url/hid-ids.h?h=v$base"
curl -fsSL --retry 3 -o usbhid/usbhid.h      "$url/usbhid/usbhid.h?h=v$base"
if grep -q '0x0b1f' hid-logitech-hidpp.c; then
  echo "hidpp-g733: kernel $base ja suporta o G733, sem patch"
  exit 0
fi
python3 - <<'PY'
p = 'hid-logitech-hidpp.c'
s = open(p).read()
old = ("\t{ /* G935 Gaming Headset */\n"
       "\t  HID_USB_DEVICE(USB_VENDOR_ID_LOGITECH, 0x0a87),\n"
       "\t\t.driver_data = HIDPP_QUIRK_WIRELESS_STATUS },\n")
new = old + ("\t{ /* G733 Gaming Headset */\n"
             "\t  HID_USB_DEVICE(USB_VENDOR_ID_LOGITECH, 0x0b1f),\n"
             "\t\t.driver_data = HIDPP_QUIRK_WIRELESS_STATUS },\n")
if s.count(old) != 1:
    raise SystemExit("hidpp-g733: entrada do G935 nao encontrada, patch nao aplicado")
open(p, 'w').write(s.replace(old, new))
PY
EOF
chmod +x "$DKMS_SRC/prep.sh"

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
# LEDs apagados ao conectar
# ---------------------------------------------------------------------------
echo "=== LEDs: ${LED_BIN} + udev + systemd ==="
cat > "$LED_BIN" <<'EOF'
#!/usr/bin/env python3
"""Apaga todos os LEDs dos perifericos Logitech via HID++ 2.0 (feature 0x8070).

  logi-leds-off              apaga em todos os dispositivos conhecidos
  logi-leds-off --ps NOME    chamado pelo udev: apaga so no dispositivo da
                             bateria NOME (ex. hidpp_battery_1), e so quando
                             ele acabou de ficar online
"""
import glob
import os
import select
import sys
import time

VID = 0x046D
# product id USB -> indices de dispositivo HID++ a tentar
TARGETS = {
    0x0B1F: [0xFF],              # G733 (dongle proprio)
    0xC539: [1, 2, 3, 4, 5, 6],  # receptor Lightspeed (G502 no slot 1)
}
SWID = 0x0E
FEAT_LED = 0x8070
EFFECT_OFF = 0x0000
TIMEOUT = 1.0
STATE_DIR = "/run/logi-leds-off"


class HidppError(Exception):
    pass


def hid_pid(hid_dir):
    with open(os.path.join(hid_dir, "uevent")) as f:
        ids = dict(l.strip().split("=", 1) for l in f if "=" in l)
    vid, pid = ids.get("HID_ID", "0:0:0").split(":")[1:]
    return int(vid, 16), int(pid, 16)


def hidraw_nodes(pid):
    for dev in sorted(glob.glob("/sys/class/hidraw/hidraw*/device")):
        if hid_pid(dev) == (VID, pid):
            yield "/dev/" + dev.split("/")[4]


def request(fd, devidx, feat_idx, func, params=b""):
    msg = bytes([0x11, devidx, feat_idx, (func << 4) | SWID]) + params
    os.write(fd, msg.ljust(20, b"\0"))
    deadline = time.monotonic() + TIMEOUT
    while (left := deadline - time.monotonic()) > 0:
        if not select.select([fd], [], [], left)[0]:
            break
        r = os.read(fd, 64)
        if len(r) < 4 or r[0] not in (0x10, 0x11) or r[1] != devidx:
            continue
        if r[2] == 0xFF and r[3] == feat_idx:          # erro HID++ 2.0
            raise HidppError(f"erro 0x{r[5]:02x}")
        if r[0] == 0x10 and r[2] == 0x8F:              # erro HID++ 1.0 (slot vazio)
            raise HidppError("dispositivo nao responde")
        if r[2] == feat_idx and r[3] == msg[3]:
            return r[4:]
    raise HidppError("timeout")


def leds_off(fd, devidx):
    idx = request(fd, devidx, 0x00, 0, FEAT_LED.to_bytes(2, "big"))[0]
    if idx == 0:
        raise HidppError("sem feature de LED")
    zones = request(fd, devidx, idx, 0)[0]
    request(fd, devidx, idx, 8, b"\x01")               # LED controlado pelo host
    for zone in range(zones):
        count = request(fd, devidx, idx, 1, bytes([zone, 0xFF, 0]))[3]
        for eff in range(count):
            info = request(fd, devidx, idx, 2, bytes([zone, eff, 0]))
            if int.from_bytes(info[2:4], "big") == EFFECT_OFF:
                request(fd, devidx, idx, 3, bytes([zone, eff]) + bytes(10))
                break
    return zones


def apply(pids):
    ok = False
    for pid in pids:
        for node in hidraw_nodes(pid):
            try:
                fd = os.open(node, os.O_RDWR)
            except OSError:
                continue
            try:
                for devidx in TARGETS[pid]:
                    try:
                        zones = leds_off(fd, devidx)
                        print(f"{node} dev {devidx:#04x}: {zones} zona(s) apagada(s)")
                        ok = True
                    except (HidppError, OSError):
                        pass
            finally:
                os.close(fd)
    return ok


def usb_pid_of(ps_name):
    # sobe da bateria ate o dispositivo USB (dongle ou receptor)
    path = os.path.realpath(f"/sys/class/power_supply/{ps_name}")
    while path != "/":
        f = os.path.join(path, "idProduct")
        if os.path.exists(f):
            return int(open(f).read(), 16)
        path = os.path.dirname(path)
    return None


def from_udev(ps_name):
    try:
        online = open(f"/sys/class/power_supply/{ps_name}/online").read().strip()
    except OSError:
        return 0
    os.makedirs(STATE_DIR, exist_ok=True)
    state = os.path.join(STATE_DIR, ps_name)
    prev = open(state).read().strip() if os.path.exists(state) else "0"
    open(state, "w").write(online)
    if online != "1" or prev == "1":
        return 0                         # so age na transicao offline -> online
    pid = usb_pid_of(ps_name)
    if pid not in TARGETS:
        return 0
    for _ in range(5):                   # o dispositivo pode ainda estar acordando
        time.sleep(1)
        if apply([pid]):
            return 0
    return 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--ps":
        return from_udev(sys.argv[2])
    return 0 if apply(TARGETS) else 1


if __name__ == "__main__":
    sys.exit(main())
EOF
chmod 755 "$LED_BIN"

cat > "$UNIT" <<EOF
[Unit]
Description=Apaga os LEDs do periferico Logitech (%i)

[Service]
Type=oneshot
ExecStart=${LED_BIN} --ps %i
EOF

cat > "$UDEV_RULE" <<'EOF'
# Apaga os LEDs dos perifericos Logitech quando ficam online (perifericos.sh)
SUBSYSTEM=="power_supply", KERNEL=="hidpp_battery_*", ACTION=="add|change", ENV{POWER_SUPPLY_ONLINE}=="1", RUN+="/usr/bin/systemctl --no-block start logi-leds-off@%k.service"
# ao desligar, grava o estado para a proxima transicao ser detectada
SUBSYSTEM=="power_supply", KERNEL=="hidpp_battery_*", ACTION=="change", ENV{POWER_SUPPLY_ONLINE}=="0", RUN+="/usr/bin/systemctl --no-block start logi-leds-off@%k.service"
EOF

rm -rf /run/logi-leds-off
systemctl daemon-reload
udevadm control --reload
"$LED_BIN" || echo "  (nenhum dispositivo ligado agora; os LEDs serao apagados ao conectar)"

echo ""
echo "======================================"
echo " Concluido."
echo " Bateria do G733/G502: applet de bateria do KDE (upower)."
echo " LEDs: apagados automaticamente sempre que o dispositivo conectar."
echo " Para desfazer: ./perifericos.sh --remover"
echo "======================================"
