#!/usr/bin/env python3
"""Prepara o Dota 2 para o dota-rgb (Game State Integration).

1. Grava game/dota/cfg/gamestate_integration/gamestate_integration_rgb.cfg
   em cada biblioteca do Steam que tenha o Dota, apontando para 127.0.0.1:3000.
2. Acrescenta -gamestateintegration nas opcoes de inicializacao do Dota
   (app 570) no localconfig.vdf de cada usuario do Steam. O Steam regrava esse
   arquivo ao fechar, entao so mexe com o Steam fechado (com backup .bak).
"""
import glob
import os
import re
import shutil
import subprocess
import sys

STEAM = os.path.expanduser("~/.local/share/Steam")
APP = "570"
OPTION = "-gamestateintegration"
GSI_CFG = '''"dota-rgb"
{
    "uri"           "http://127.0.0.1:3000/"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.1"
    "heartbeat"     "30.0"
    "data"
    {
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "1"
        "items"         "1"
    }
}
'''


# ---------------------------------------------------------------------------
# VDF (formato de texto do Steam): lista ordenada de [chave, valor]
# ---------------------------------------------------------------------------
def vdf_parse(text):
    tokens = re.findall(r'"((?:\\.|[^"\\])*)"|([{}])', text)
    pos = 0

    def block():
        nonlocal pos
        items = []
        while pos < len(tokens):
            s, brace = tokens[pos]
            pos += 1
            if brace == "}":
                return items
            key = s
            s2, brace2 = tokens[pos]
            pos += 1
            items.append([key, block() if brace2 == "{" else s2])
        return items

    return block()


def vdf_dump(items, depth=0):
    out = []
    tab = "\t" * depth
    for k, v in items:
        if isinstance(v, list):
            out.append(f'{tab}"{k}"\n{tab}{{\n{vdf_dump(v, depth + 1)}{tab}}}\n')
        else:
            out.append(f'{tab}"{k}"\t\t"{v}"\n')
    return "".join(out)


def vdf_child(items, key, create=False):
    for kv in items:
        if kv[0].lower() == key.lower() and isinstance(kv[1], list):
            return kv[1]
    if create:
        items.append([key, []])
        return items[-1][1]
    return None


# ---------------------------------------------------------------------------
def dota_dirs():
    libs = [STEAM]
    try:
        text = open(os.path.join(STEAM, "steamapps", "libraryfolders.vdf")).read()
        libs += re.findall(r'"path"\s+"([^"]+)"', text)
    except OSError:
        pass
    seen = []
    for lib in libs:
        d = os.path.join(lib, "steamapps", "common", "dota 2 beta", "game", "dota", "cfg")
        if os.path.isdir(d) and os.path.realpath(d) not in seen:
            seen.append(os.path.realpath(d))
    return seen


def write_gsi_cfg():
    dirs = dota_dirs()
    if not dirs:
        print("  Dota 2 nao encontrado nas bibliotecas do Steam; GSI nao configurado")
    for d in dirs:
        target = os.path.join(d, "gamestate_integration")
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, "gamestate_integration_rgb.cfg"), "w") as f:
            f.write(GSI_CFG)
        print(f"  GSI: {target}/gamestate_integration_rgb.cfg")


def steam_running():
    return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0


def set_launch_option():
    configs = glob.glob(os.path.join(STEAM, "userdata", "*", "config", "localconfig.vdf"))
    if not configs:
        print("  localconfig.vdf nao encontrado; adicione " + OPTION + " no Steam (Dota 2 > Propriedades)")
        return
    pending = []
    for path in configs:
        tree = vdf_parse(open(path, encoding="utf-8", errors="replace").read())
        root = vdf_child(tree, "UserLocalConfigStore")
        if root is None:
            continue
        apps = root
        for key in ("Software", "Valve", "Steam", "apps"):
            apps = vdf_child(apps, key, create=True)
        app = vdf_child(apps, APP, create=True)
        opt = next((kv for kv in app if kv[0] == "LaunchOptions"), None)
        current = opt[1] if opt else ""
        if OPTION in current.split():
            print(f"  opcao {OPTION} ja presente ({path})")
            continue
        pending.append((path, tree, app, opt, current))
    if not pending:
        return
    if steam_running():
        print(f"  Steam aberto: feche o Steam e rode de novo, ou adicione {OPTION}")
        print("  em Dota 2 > Propriedades > Opcoes de inicializacao")
        return
    for path, tree, app, opt, current in pending:
        new = (current + " " + OPTION).strip()
        if opt:
            opt[1] = new
        else:
            app.append(["LaunchOptions", new])
        shutil.copy2(path, path + ".bak")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(vdf_dump(tree))
        os.replace(tmp, path)
        print(f"  opcao de inicializacao do Dota: '{new}' ({path})")


if __name__ == "__main__":
    write_gsi_cfg()
    set_launch_option()
    sys.exit(0)
