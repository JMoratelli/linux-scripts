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
