#!/usr/bin/env python3
"""Gera a configuracao do OpenRGB + Effects Plugin do gabinete, do zero.

Escreve em ~/.config/OpenRGB:
  - OpenRGB.json         detectores ignorados + perfil carregado na abertura
  - Configuration.json   tamanho e nome das zonas ARGB (se ja existir) e o
                         teclado K629 como matriz 21x6
  - profiles/Gabinete.json  efeitos de audio por zona (Effects Plugin)
  - profiles/Dota.json      sem efeitos (o dota-rgb pinta pelo SDK)
e ~/.config/rgb-gabinete/zonas.json, conferido pelo openrgb-gabinete.
"""
import json
import os

CFG = os.path.expanduser("~/.config/OpenRGB")
PROFILE = "Gabinete"
PROFILE_DOTA = "Dota"       # sem efeitos: quem pinta e o dota-rgb, pelo SDK
PLUGIN = "OpenRGB Effects Plugin"

# Detectores desligados: Logitech (G502/G733 ficam sempre apagados, ver perifericos.sh)
IGNORED_DETECTORS = [
    "Logitech G502 HERO Gaming Mouse",
    "Logitech G502 Proteus Spectrum Gaming Mouse",
    "Logitech G502 Wireless Gaming Mouse",
    "Logitech G502 Wireless Gaming Mouse (wired)",
    "Logitech G733 Gaming Headset",
    "Logitech HID++ 2.0",
]

RAZER = {
    "name": "Razer Chroma Addressable RGB Controller", "vendor": "Razer",
    "description": "Razer Addressable Device", "version": "v1.0",
    "serial": "IO2122U08302371       ", "location": "HID: /dev/hidraw1",
}
GPU = {
    "name": "Gigabyte Radeon RX 7600 GAMING OC 8G", "vendor": "Gigabyte",
    "description": "Gigabyte RGB Fusion 2 GPU Device", "version": "", "serial": "",
    "location": "I2C: AMDGPU DM i2c OEM bus (/dev/i2c-4), address 0x55",
}
WLED = {
    "name": "WLED Mesa", "vendor": "", "description": "Distributed Display Protocol Device",
    "version": "", "serial": "", "location": "DDP: 192.168.3.84:4048",
}
KEYBOARD = {
    "name": "Redragon K629", "vendor": "", "description": "Distributed Display Protocol Device",
    "version": "", "serial": "", "location": "DDP: 127.0.0.1:4049",
}
DDP_DEVICES = [
    {"name": "WLED Mesa", "ip": "192.168.3.84", "port": 4048, "num_leds": 66},
    # teclado Redragon K629 via teclado-ponte (perifericos.sh): o quadro inteiro
    # do teclado, 21 colunas x 6 linhas, posicao = coluna*6 + linha
    {"name": "Redragon K629", "ip": "127.0.0.1", "port": 4049, "num_leds": 126},
]
# posicoes do quadro que tem tecla (layout 75%, tirado do Cfg.ini do software oficial)
K629_KEYS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    24, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 42, 43, 44, 45, 46, 48, 49,
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 72, 73, 74,
    75, 76, 78, 79, 81, 82, 83, 84, 88, 89, 90, 91, 92, 93, 94, 95]
K629_COLS, K629_ROWS = 21, 6
MOBO = {
    "name": "X570 GAMING X", "vendor": "Gigabyte", "description": "IT8297BX-GBX570",
    "version": "1.0.6.0", "serial": "0x82970100", "location": "HID: /dev/hidraw0",
}

# Canais ARGB: (canal, LEDs, nome)
RAZER_CHANNELS = [
    ("Channel 1", 40, "Fonte Super Flower"),   # Leadex III ARGB: fan + conectores
    ("Channel 2", 35, "Fan superior 1"),
    ("Channel 3", 37, "Fan frontal"),
    ("Channel 4", 35, "Fan superior 2"),
    ("Channel 5", 29, "Corsair H100 RGB"),     # fan 2 (8), fan 1 (8), water block (13)
    ("Channel 6", 0, ""),
]
MOBO_HEADERS = [("D_LED1", 0, ""), ("D_LED2", 0, "")]

# O plugin captura a 10 kHz com FFT de 256 pontos: o espectro util vai de
# 0 a ~2,5 kHz e cada uma das 16 bandas do equalizador cobre ~156 Hz.
# Zerar bandas no equalizador de um efeito faz ele reagir so a uma faixa.
def audio(bands=range(16), amplitude=100, decay=80, nrml_scl=0.5):
    return {
        "audio_device": 1,      # corrigido na inicializacao pelo openrgb-gabinete
        "amplitude": amplitude,
        "avg_mode": 0,
        "avg_size": 8,
        "window_mode": 1,       # Hanning
        "decay": decay,
        "filter_constant": 1.0,
        "nrml_ofst": 0.04,
        "nrml_scl": nrml_scl,   # ganho progressivo nas frequencias altas
        "equalizer": [1.0 if b in bands else 0.0 for b in range(16)],
    }


GRAVE = range(0, 2)     # 0-310 Hz
MEDIO = range(2, 6)     # 310-940 Hz
AGUDO = range(5, 16)    # 780 Hz-2,5 kHz


def rgb(r, g, b):
    return r | (g << 8) | (b << 16)     # RGBColor do OpenRGB (0x00BBGGRR)


# (nome, classe do efeito, zonas, CustomSettings, brilho %)
# Os 3 fans grandes sao o destaque; fonte, H100 e o resto ficam discretos.
EFFECTS = [
    ("Fan frontal - grave", "AudioVUMeter", [(RAZER, 2)], {
        "color_offset": 270, "color_spread": 90, "saturation": 255, "invert_hue": False,
        "audio_settings": audio(GRAVE, decay=85)}, 100),
    ("Fan superior 1 - medio", "AudioStar", [(RAZER, 1)], {
        "edge_beat": True, "edge_beat_sensivity": 100, "edge_beat_saturation": 0, "edge_beat_hue": 120,
        "audio_settings": audio(MEDIO)}, 100),
    # O AudioStar numa zona linear le uma frequencia so (~625 Hz), entao nos
    # agudos quem funciona e o VU Meter, que soma a faixa inteira.
    ("Fan superior 2 - agudo", "AudioVUMeter", [(RAZER, 3)], {
        "color_offset": 180, "color_spread": 60, "saturation": 255, "invert_hue": False,
        "audio_settings": audio(AGUDO, amplitude=60, nrml_scl=1.0)}, 100),
    ("H100 RGB - festa", "AudioParty", [(RAZER, 4)], {
        "divisions": 2.0, "effect_threshold": 0.2, "motion_zone_stop": 64, "color_zone_stop": 192,
        "audio_settings": audio()}, 45),
    ("WLED Mesa - audio", "AudioStar", [(WLED, 0)], {
        "edge_beat": True, "edge_beat_sensivity": 100, "edge_beat_saturation": 0, "edge_beat_hue": 300,
        "audio_settings": audio()}, 100),
    ("Teclado - barras", "AudioVisualizer", [(KEYBOARD, 0)], {
        "ForegroundMode": 18, "BackgroundMode": 0, "BackgroundBrightness": 0,   # arco-iris / preto
        "SingleColorMode": 12, "AnimationSpeed": 100.0, "ReactiveBackground": False,
        "SilentBackground": False, "BackgroundTimeout": 120.0,
        "audio_settings": audio(amplitude=250)}, 100),
    ("Fonte, GPU e placa-mae", "AudioSync",
     [(RAZER, 0)] + [(GPU, z) for z in range(5)] + [(MOBO, 2), (MOBO, 3)], {
         "fade_step": 10, "hue_shift": 0, "bypass_min": 0, "bypass_max": 255,
         "roll_mode": 0, "saturation_mode": 0, "silent_color": False, "silent_color_value": 0,
         "audio_settings": audio()}, 35),
]


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


def openrgb_json():
    path = os.path.join(CFG, "OpenRGB.json")
    d = load(path)
    det = d.setdefault("Detectors", {}).setdefault("detectors", {})
    for name in IGNORED_DETECTORS:
        det[name] = False
    d["DDPDevices"] = {"devices": DDP_DEVICES}
    pm = d.setdefault("ProfileManager", {})
    pm["open_profile"] = {"enabled": True, "name": PROFILE}
    save(path, d)


def configuration_json():
    """Tamanho/nome das zonas redimensionaveis (o OpenRGB aplica ao detectar)."""
    path = os.path.join(CFG, "Configuration.json")
    d = load(path)
    ctrls = d.get("controllers", [])

    def zones(sizes):
        return [{"name": n, "leds_count": c, "display_name": dn} for n, c, dn in sizes]

    # So o que interessa para o casamento e o redimensionamento; o OpenRGB
    # completa o resto ao salvar.
    for ident, sizes in ((RAZER, RAZER_CHANNELS), (MOBO, MOBO_HEADERS)):
        existing = next((c for c in ctrls if c.get("name") == ident["name"]), None)
        if existing and existing.get("zones"):
            by_name = {z["name"]: z for z in existing["zones"]}
            for n, count, dn in sizes:
                if n in by_name:
                    by_name[n]["leds_count"] = count
                    by_name[n]["display_name"] = dn
        else:
            # instalacao nova: o openrgb-gabinete ajusta o tamanho pelo SDK na
            # primeira abertura; os nomes entram quando este script rodar de novo
            pass
    ctrls = [c for c in ctrls if c.get("name") != KEYBOARD["name"]]
    ctrls.append(keyboard_controller())
    d["controllers"] = ctrls
    save(path, d)


def keyboard_controller():
    """Teclado como matriz 21x6: o OpenRGB cria o DDP como fita linear, e o
    tipo/mapa da zona sao configuraveis (flags MANUALLY_CONFIGURED_*)."""
    present = set(K629_KEYS)
    none = 0xFFFFFFFF
    matrix = [(c * K629_ROWS + r) if (c * K629_ROWS + r) in present else none
              for r in range(K629_ROWS) for c in range(K629_COLS)]
    configurable = (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)   # nome, tipo, matriz, segmentos
    configured = (1 << 14) | (1 << 15)                         # tipo e matriz configurados
    return dict(KEYBOARD, type=4, flags=1, configuration=None, zones=[{
        "name": KEYBOARD["name"], "display_name": "", "type": 2,   # ZONE_TYPE_MATRIX
        "leds_count": 126, "leds_min": 126, "leds_max": 126,
        "matrix_map": {"height": K629_ROWS, "width": K629_COLS, "map": matrix},
        "flags": configurable | configured,
    }])


def zones_json():
    """Tamanhos que o openrgb-gabinete confere/corrige pelo SDK a cada abertura."""
    wanted = [{"match": RAZER["name"], "zone": i, "size": n} for i, (_, n, _) in enumerate(RAZER_CHANNELS)]
    wanted += [{"match": MOBO["name"], "zone": i, "size": n} for i, (_, n, _) in enumerate(MOBO_HEADERS)]
    save(os.path.expanduser("~/.config/rgb-gabinete/zonas.json"), wanted)


def profile_json():
    path = os.path.join(CFG, "profiles", PROFILE + ".json")
    effects = []
    for name, cls, zone_list, custom, brightness in EFFECTS:
        effects.append({
            "EffectClassName": cls,
            "CustomName": name,
            "FPS": 60,
            "Speed": 50,
            "Slider2Val": 1,
            "RandomColors": False,
            "AllowOnlyFirst": False,
            "Brightness": brightness,
            "Temperature": 0,
            "Tint": 0,
            "UserColors": [],
            "AutoStart": True,
            "SelectAll": False,
            "ControllerZones": [dict(ident, zone_idx=z, reverse=False, self_brightness=100,
                                     is_segment=False, segment_idx=-1) for ident, z in zone_list],
            "CustomSettings": custom,
        })
    profile = {
        "profile_name": PROFILE,
        "profile_version": 6,
        "controllers": [],
        "plugins": {PLUGIN: {"version": 2, "Effects": effects}},
    }
    save(path, profile)


def dota_profile_json():
    save(os.path.join(CFG, "profiles", PROFILE_DOTA + ".json"), {
        "profile_name": PROFILE_DOTA,
        "profile_version": 6,
        "controllers": [],
        "plugins": {PLUGIN: {"version": 2, "Effects": []}},
    })


if __name__ == "__main__":
    openrgb_json()
    configuration_json()
    zones_json()
    profile_json()
    dota_profile_json()
    print("configuracao do OpenRGB gerada")
