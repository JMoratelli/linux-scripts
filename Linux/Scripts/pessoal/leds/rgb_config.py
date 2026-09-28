#!/usr/bin/env python3
"""Gera a configuracao do OpenRGB + Effects Plugin do gabinete, do zero.

Escreve em ~/.config/OpenRGB:
  - OpenRGB.json         detectores ignorados + perfil carregado na abertura
  - Configuration.json   tamanho e nome das zonas ARGB (se ja existir) e o
                         teclado K629 como matriz 21x6
  - profiles/Gabinete.json  efeitos de audio por zona (Effects Plugin)
  - profiles/Dota.json      o mesmo sem teclado e WLED (o dota-rgb pinta os dois)
e ~/.config/rgb-gabinete/zonas.json, conferido pelo openrgb-gabinete.
"""
import json
import os
import sys
import time
from colorsys import hsv_to_rgb

CFG = os.path.expanduser("~/.config/OpenRGB")
PROFILE = "Gabinete"
PROFILE_OFF = "Desligado"   # sem efeitos: usado pelo rgb-casa para apagar tudo ao sair
PROFILE_DOTA = "Dota"       # teclado e WLED ficam com o dota-rgb; o resto segue o audio
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
# WLED da mesa por E1.31 (universo 1): diferente do DDP do OpenRGB, o E1.31
# nao tem keepalive, entao sem efeito o PC para de mandar e a WLED volta aos
# efeitos dela (ex.: audio vindo do celular). A localizacao e a que o OpenRGB
# monta para esse dispositivo.
WLED = {
    "name": "WLED Mesa", "vendor": "", "description": "E1.31 Streaming ACN Device",
    "version": "", "serial": "", "location": "E1.31: Unicast 192.168.3.84, Universe 1",
}
E131_DEVICES = [
    {"name": "WLED Mesa", "ip": "192.168.3.84", "num_leds": 66, "start_universe": 1,
     "start_channel": 1, "universe_size": 510, "keepalive_time": 0},
]
KEYBOARD = {
    "name": "Redragon K629", "vendor": "", "description": "Distributed Display Protocol Device",
    "version": "", "serial": "", "location": "DDP: 127.0.0.1:4049",
}
DDP_DEVICES = [
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


# ---------------------------------------------------------------------------
# Zonas mostradas na interface (rgb-casa): id, rotulo, zonas do OpenRGB
# ---------------------------------------------------------------------------
ZONES = [
    ("fan_frontal", "Fan frontal", [(RAZER, 2)]),
    ("fan_superior_1", "Fan superior 1", [(RAZER, 1)]),
    ("fan_superior_2", "Fan superior 2", [(RAZER, 3)]),
    ("h100", "Corsair H100 RGB", [(RAZER, 4)]),
    ("fonte", "Fonte Super Flower", [(RAZER, 0)]),
    ("gpu", "Placa de vídeo", [(GPU, z) for z in range(5)]),
    ("placa_mae", "Placa-mãe", [(MOBO, 2), (MOBO, 3)]),
    ("wled", "WLED da mesa", [(WLED, 0)]),
    ("teclado", "Teclado Redragon", [(KEYBOARD, 0)]),
]
GAME_ZONES = ("teclado", "wled")   # no perfil Dota ficam com o dota-rgb

BANDS = {"grave": GRAVE, "medio": MEDIO, "agudo": AGUDO, "tudo": range(16)}
BAND_LABELS = {"grave": "Grave", "medio": "Médio", "agudo": "Agudo", "tudo": "Tudo"}

# efeito -> (rotulo, grupo, parametros que a interface mostra)
# Grupos: "audio" reage ao som, "tela" segue a tela, "ambiente" anima sozinho,
# "livre" o PC nao manda nada e o dispositivo fica com os efeitos dele (ex.: a
# WLED recebendo audio do celular).
CATALOG = {
    "vu": ("VU: enche com o som", "audio", ("band", "hue", "hue_spread")),
    "estrela": ("Estrela: cor girando, flash na batida", "audio", ("band",)),
    "sincronia": ("Cor pela frequência", "audio", ("band",)),
    "festa": ("Festa: movimento e cor pelo som", "audio", ("band",)),
    "barras": ("Barras de espectro", "audio", ("band",)),
    "ondas": ("Ondas: senoide do som", "audio", ("band", "hue")),
    "bolhas": ("Bolhas: surgem com o som", "audio", ("band", "hue", "hue_spread")),
    "redemoinho": ("Redemoinho: círculos girando com o som", "audio", ("band", "hue", "hue_spread", "speed")),
    "tela": ("Tela: segue as cores da tela", "tela", ()),
    "arco-iris": ("Arco-íris", "ambiente", ("speed",)),
    "ciclo": ("Ciclo de cores", "ambiente", ("speed",)),
    "respirar": ("Respirar", "ambiente", ("hue", "speed")),
    "cometa": ("Cometa", "ambiente", ("hue", "speed")),
    "estrelado": ("Céu estrelado", "ambiente", ("hue", "hue_spread")),
    "apagado": ("Apagado", "ambiente", ()),
    "livre": ("Livre: efeitos do próprio dispositivo", "livre", ()),
}
# faixa de velocidade aceita por cada efeito do plugin (ele nao limita sozinho)
SPEED_RANGE = {"RainbowWave": (1, 100), "SpectrumCycling": (1, 100), "Breathing": (10, 200),
               "Comet": (1, 50), "SwirlCirclesAudio": (1, 100), "AudioSine": (1, 100)}

# o que foi aprovado em 2026-09-27
DEFAULT_ZONES = {
    "fan_frontal": {"effect": "vu", "band": "grave", "hue": 270, "hue_spread": 90, "brightness": 100},
    "fan_superior_1": {"effect": "estrela", "band": "medio", "brightness": 100},
    "fan_superior_2": {"effect": "vu", "band": "agudo", "hue": 180, "hue_spread": 60, "brightness": 100},
    "h100": {"effect": "festa", "brightness": 45},
    "fonte": {"effect": "sincronia", "band": "tudo", "brightness": 35},
    "gpu": {"effect": "sincronia", "band": "tudo", "brightness": 35},
    "placa_mae": {"effect": "sincronia", "band": "tudo", "brightness": 35},
    "wled": {"effect": "estrela", "band": "tudo", "brightness": 100},
    "teclado": {"effect": "barras", "brightness": 100},
}
USER_CONFIG = os.path.expanduser("~/.config/rgb-casa/config.json")


def band_audio(band, effect):
    eq = BANDS.get(band, BANDS["tudo"])
    if effect == "vu" and band == "agudo":
        return audio(eq, amplitude=60, nrml_scl=1.0)   # soma 11 bandas: menos ganho
    if effect == "vu" and band == "grave":
        return audio(eq, decay=85)
    if effect == "barras":
        return audio(eq, amplitude=250)
    return audio(eq)


def hue_rgb(hue, sat=1.0):
    """RGBColor do OpenRGB a partir da matiz em graus."""
    r, g, b = hsv_to_rgb((hue % 360) / 360, sat, 1.0)
    return rgb(int(r * 255), int(g * 255), int(b * 255))


def palette(zcfg, n=5):
    """Cores de usuario: sempre 5, porque alguns efeitos do plugin leem
    UserColors[0] e [1] sem conferir o tamanho (lista vazia derruba o OpenRGB)."""
    hue, spread = zcfg.get("hue", 270), zcfg.get("hue_spread", 90)
    return [hue_rgb(hue + spread * i / max(1, n - 1)) for i in range(n)]


def plugin_effect(zcfg):
    """Traduz a escolha da interface para (classe, CustomSettings, brilho).
    Efeito desconhecido vira "apagado"."""
    eff = zcfg.get("effect", "apagado")
    band = zcfg.get("band", "tudo")
    brightness = max(0, min(100, int(zcfg.get("brightness", 100))))
    colors = palette(zcfg)
    if eff == "vu":
        return "AudioVUMeter", {
            "color_offset": int(zcfg.get("hue", 270)), "color_spread": int(zcfg.get("hue_spread", 90)),
            "saturation": 255, "invert_hue": False, "audio_settings": band_audio(band, eff)}, brightness
    if eff == "estrela":
        # numa zona linear o AudioStar le so ~625 Hz (banda 4 do equalizador):
        # a faixa escolhida sempre inclui essa banda para ele nao apagar
        eq = sorted(set(BANDS.get(band, BANDS["tudo"])) | {4})
        return "AudioStar", {
            "edge_beat": True, "edge_beat_sensivity": 100, "edge_beat_saturation": 0, "edge_beat_hue": 120,
            "audio_settings": audio(eq)}, brightness
    if eff == "sincronia":
        return "AudioSync", {
            "fade_step": 10, "hue_shift": 0, "bypass_min": 0, "bypass_max": 255, "roll_mode": 0,
            "saturation_mode": 0, "silent_color": False, "silent_color_value": 0,
            "audio_settings": band_audio(band, eff)}, brightness
    if eff == "festa":
        return "AudioParty", {
            "divisions": 2.0, "effect_threshold": 0.2, "motion_zone_stop": 64, "color_zone_stop": 192,
            "audio_settings": band_audio(band, eff)}, brightness
    if eff == "barras":
        return "AudioVisualizer", {
            "ForegroundMode": 18, "BackgroundMode": 0, "BackgroundBrightness": 0,   # arco-iris / preto
            "SingleColorMode": 12, "AnimationSpeed": 100.0, "ReactiveBackground": False,
            "SilentBackground": False, "BackgroundTimeout": 120.0,
            "audio_settings": band_audio(band, eff)}, brightness
    if eff == "ondas":
        return "AudioSine", {
            "color_mode": 1, "repeat": 1, "glow": 20, "thickness": 2, "oscillation": 0,
            "color_change_speed": 0, "background": 0, "wave_color": colors[0],
            "audio_settings": band_audio(band, eff)}, brightness
    if eff == "bolhas":
        return "AudioBubbles", {
            "colors": colors, "trigger": 25, "max_bubbles": 10, "speed_mult": 2, "max_expansion": 100,
            "bubbles_thickness": 10, "spawnMode": 0, "audio_settings": band_audio(band, eff)}, brightness
    if eff == "redemoinho":
        return "SwirlCirclesAudio", {"radius": 0, "audio_settings": band_audio(band, eff)}, brightness
    if eff == "tela":
        # "Screen copy": serve para zona de 1 LED, fita e matriz; tela inteira
        return "Ambient", {
            "mode": 1, "screen_index": 0, "left": 0, "top": 0, "width": 1920, "height": 1080,
            "smoothness": 70, "framerate": 30, "crop_stream": False}, brightness
    if eff == "arco-iris":
        return "RainbowWave", {}, brightness
    if eff == "ciclo":
        return "SpectrumCycling", {"saturation": 255}, brightness
    if eff == "respirar":
        return "Breathing", {"colors": colors[:1]}, brightness
    if eff == "cometa":
        return "Comet", {}, brightness
    if eff == "estrelado":
        return "StarryNight", {
            "starColors": colors, "starDensity": 30, "backgroundColors": 0, "fadeInSpeed": 10,
            "fadeOutSpeed": 10, "starOnTime": 10, "backColorBrightness": 0}, brightness
    return "RainbowWave", {}, 0                          # apagado: efeito com brilho 0


def plugin_speed(cls, zcfg):
    lo, hi = SPEED_RANGE.get(cls, (1, 100))
    frac = max(0, min(100, int(zcfg.get("speed", 50)))) / 100
    return int(round(lo + (hi - lo) * frac))


def user_config():
    cfg = {"dota": True, "zones": json.loads(json.dumps(DEFAULT_ZONES))}
    try:
        with open(USER_CONFIG) as f:
            user = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return cfg
    cfg["dota"] = user.get("dota", True)
    for zid, zcfg in user.get("zones", {}).items():
        if zid in cfg["zones"]:
            cfg["zones"][zid].update(zcfg)
    return cfg


def save_user_config(cfg):
    save(USER_CONFIG, cfg)


def effects_for(cfg, skip=()):
    """Um efeito do plugin por configuracao distinta; zonas com a mesma
    configuracao dividem a instancia (menos carga e um pedido de captura de
    tela so, no caso do "tela")."""
    groups = {}
    for zid, label, zone_list in ZONES:
        if zid in skip:
            continue
        zcfg = cfg["zones"][zid]
        if zcfg.get("effect") == "livre":                # o PC nao manda nada para a zona
            continue
        cls, custom, brightness = plugin_effect(zcfg)
        speed, colors = plugin_speed(cls, zcfg), palette(zcfg)
        key = (cls, json.dumps(custom, sort_keys=True), brightness, speed, tuple(colors))
        if cls == "Ambient":
            key = (cls,)                                 # uma captura de tela para todas
        g = groups.setdefault(key, {"labels": [], "zones": [], "args": (cls, custom, brightness, speed, colors)})
        g["labels"].append(label)
        g["zones"] += zone_list
    out = []
    for g in groups.values():
        cls, custom, brightness, speed, colors = g["args"]
        out.append(effect_json(", ".join(g["labels"]), cls, g["zones"], custom, brightness, speed, colors))
    return out


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
    d["E131Devices"] = {"devices": E131_DEVICES}
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


def effect_json(name, cls, zone_list, custom, brightness, speed=50, colors=()):
    return {
        "EffectClassName": cls,
        "CustomName": name,
        "FPS": 60,
        "Speed": speed,
        "Slider2Val": 1,
        "RandomColors": False,
        "AllowOnlyFirst": False,
        "Brightness": brightness,
        "Temperature": 0,
        "Tint": 0,
        "UserColors": list(colors) or [rgb(255, 255, 255)] * 5,
        "AutoStart": True,
        "SelectAll": False,
        "ControllerZones": [dict(ident, zone_idx=z, reverse=False, self_brightness=100,
                                 is_segment=False, segment_idx=-1) for ident, z in zone_list],
        "CustomSettings": custom,
    }


def profile_path(name):
    return os.path.join(CFG, "profiles", name + ".json")


def screen_token(name):
    """Token do portal de captura de tela guardado no perfil (efeito Ambient)."""
    effects = load(profile_path(name)).get("plugins", {}).get(PLUGIN, {}).get("Effects", [])
    return next((e.get("CustomSettings", {}).get("restore_token") for e in effects
                 if e.get("EffectClassName") == "Ambient" and e.get("CustomSettings", {}).get("restore_token")),
                None)


def write_profile(name, effects):
    """Grava o perfil preservando o token de captura de tela ja concedido
    (sem ele o KDE pede permissao de novo)."""
    token = screen_token(PROFILE) or screen_token(PROFILE_DOTA)
    if token:
        for e in effects:
            if e["EffectClassName"] == "Ambient":
                e["CustomSettings"] = dict(e["CustomSettings"], restore_token=token)
    save(profile_path(name), {
        "profile_name": name,
        "profile_version": 6,
        "controllers": [],
        "plugins": {PLUGIN: {"version": 2, "Effects": effects}},
    })


def uses_screen(cfg):
    return any(z.get("effect") == "tela" for z in cfg["zones"].values())


def persist_screen_token(name, delay=12):
    """O token do portal so vale uma vez: cada vez que o Ambient inicia, o
    plugin recebe um novo, que so existe na memoria do OpenRGB. Pede ao
    OpenRGB para salvar o perfil (grava o token novo) e copia o token para o
    outro perfil. Confere o resultado e restaura o arquivo se algo sair errado."""
    time.sleep(delay)
    path = profile_path(name)
    before = load(path)
    expected = [e.get("CustomName") for e in before.get("plugins", {}).get(PLUGIN, {}).get("Effects", [])]
    try:
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        from rgbsdk import SDK
        sdk = SDK("rgb-casa-token")
        if sdk.active_profile() != name:
            sdk.close()
            return False
        sdk.send(0, 151, name.encode() + b"\0")         # PROFILEMANAGER_SAVE_PROFILE
        time.sleep(2)
        sdk.close()
    except OSError:
        return False
    after = load(path)
    got = [e.get("CustomName") for e in after.get("plugins", {}).get(PLUGIN, {}).get("Effects", [])]
    if got != expected:                                  # plugin nao respondeu: volta o original
        save(path, before)
        return False
    token = screen_token(name)
    other = PROFILE_DOTA if name == PROFILE else PROFILE
    data = load(profile_path(other))
    for e in data.get("plugins", {}).get(PLUGIN, {}).get("Effects", []):
        if e.get("EffectClassName") == "Ambient" and token:
            e.setdefault("CustomSettings", {})["restore_token"] = token
    if data:
        save(profile_path(other), data)
    return True


def profile_json(cfg=None):
    write_profile(PROFILE, effects_for(cfg or user_config()))


def dota_profile_json(cfg=None):
    """Igual ao Gabinete, sem teclado e WLED: esses dois o dota-rgb pinta com o
    estado da partida; o resto segue o audio."""
    write_profile(PROFILE_DOTA, effects_for(cfg or user_config(), skip=GAME_ZONES))


def release_wled(ips=None):
    """Tira a WLED do modo realtime na hora ({"live": false} na API JSON), em
    vez de esperar o tempo limite dela: volta sozinha aos proprios efeitos."""
    import urllib.request
    done = []
    for ip in ips if ips is not None else [d["ip"] for d in E131_DEVICES]:
        req = urllib.request.Request(f"http://{ip}/json/state", data=b'{"live":false}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=2):
                done.append(ip)
        except OSError:
            pass                                         # WLED desligada/fora da rede
    return done


def off_profile_json():
    write_profile(PROFILE_OFF, [])


def apply(cfg):
    """Grava a configuracao, gera os perfis e recarrega o perfil ativo no
    OpenRGB (a mudanca aparece na hora). Bloqueia alguns segundos se houver
    efeito de tela (salva o token do portal): chamar fora da thread da
    interface. Retorna False se o OpenRGB estiver fechado."""
    save_user_config(cfg)
    profile_json(cfg)
    dota_profile_json(cfg)
    try:
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        from rgbsdk import SDK
        sdk = SDK("rgb-casa")
        active = sdk.active_profile()
        active = active if active in (PROFILE, PROFILE_DOTA) else PROFILE
        sdk.load_profile(active)
        sdk.close()
    except OSError:
        return False                                     # OpenRGB fechado: vale na proxima abertura
    if cfg["zones"].get("wled", {}).get("effect") == "livre" and active == PROFILE:
        time.sleep(0.5)                                  # depois do ultimo quadro do OpenRGB
        release_wled()
    if uses_screen(cfg):
        persist_screen_token(active)
    return True


if __name__ == "__main__":
    openrgb_json()
    configuration_json()
    zones_json()
    profile_json()
    dota_profile_json()
    off_profile_json()
    print("configuracao do OpenRGB gerada")
