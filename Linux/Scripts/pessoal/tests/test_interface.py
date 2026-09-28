"""Testes da janela: precisam de uma sessao grafica (Wayland/X11)."""
import copy
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from helpers import LEDS, load_script

if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
    raise unittest.SkipTest("sem sessao grafica")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib  # noqa: E402

ui = load_script(os.path.join(LEDS, "rgb-casa"), "rgb_casa_ui")
Adw.init()


class TestZona(unittest.TestCase):
    def setUp(self):
        self.cfg = ui.rc.user_config()
        self.changes = 0

    def changed(self):
        self.changes += 1

    def test_controles_certos_para_cada_efeito(self):
        row = ui.ZoneRow("fan_frontal", "Fan frontal", self.cfg, self.changed)
        for i, eff in enumerate(row.effects):
            row.effect_row.set_selected(i)
            params = ui.rc.CATALOG[eff][2]
            self.assertEqual(self.cfg["zones"]["fan_frontal"]["effect"], eff)
            self.assertEqual(row.band_row.get_visible(), "band" in params, eff)
            self.assertEqual(row.hue_row.get_visible(), "hue" in params, eff)
            self.assertEqual(row.spread_row.get_visible(), "hue_spread" in params, eff)
            self.assertEqual(row.speed_row.get_visible(), "speed" in params, eff)
            self.assertEqual(row.bright_row.get_visible(), eff not in ("apagado", "livre"), eff)
        self.assertGreater(self.changes, 0)

    def test_efeitos_agrupados_som_tela_ambiente(self):
        row = ui.ZoneRow("wled", "WLED", self.cfg, self.changed)
        grupos = [ui.rc.CATALOG[e][1] for e in row.effects]
        self.assertEqual(grupos, sorted(grupos, key=("audio", "tela", "ambiente", "livre").index))

    def test_efeito_salvo_desconhecido_nao_quebra(self):
        self.cfg["zones"]["gpu"]["effect"] = "removido"
        row = ui.ZoneRow("gpu", "GPU", self.cfg, self.changed)
        self.assertEqual(row.effect_row.get_selected(), 0)


class TestRolagem(unittest.TestCase):
    def test_rodinha_rola_a_pagina_e_nao_o_controle(self):
        from gi.repository import Gtk
        valores = []
        row, scale = ui.slider_row("Brilho", 0, 100, 50, valores.append)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(row)
        sw = Gtk.ScrolledWindow()
        sw.set_child(box)
        adj = sw.get_vadjustment()
        adj.configure(0, 0, 1000, 10, 100, 100)
        self.assertTrue(ui._scroll_page(None, 0, 2, scale))
        self.assertEqual(adj.get_value(), 120)            # a pagina rolou
        self.assertEqual(scale.get_value(), 50)          # o controle nao mudou
        self.assertEqual(valores, [])


class TestAplicacao(unittest.TestCase):
    def test_mudancas_seguidas_viram_uma_aplicacao(self):
        feitas = []
        entrou = threading.Event()
        libera = threading.Event()

        def lenta(cfg):
            feitas.append(cfg["zones"]["fonte"]["brightness"])
            entrou.set()
            libera.wait(2)
            return True

        cfg = ui.rc.user_config()
        with mock.patch.object(ui.rc, "apply", side_effect=lenta):
            app = ui.Applier(lambda ok: None)
            cfg["zones"]["fonte"]["brightness"] = 10
            app.submit(cfg)
            entrou.wait(2)
            for b in (20, 30, 40):                         # chegam durante a aplicacao
                cfg["zones"]["fonte"]["brightness"] = b
                app.submit(copy.deepcopy(cfg))
            libera.set()
            for _ in range(50):
                if not app.busy:
                    break
                time.sleep(0.05)
        self.assertEqual(feitas, [10, 40])                 # so a ultima depois da primeira

    def test_erro_na_aplicacao_nao_derruba(self):
        resultados = []
        with mock.patch.object(ui.rc, "apply", side_effect=RuntimeError("falhou")):
            app = ui.Applier(resultados.append)
            app.submit(ui.rc.user_config())
            ctx = GLib.MainContext.default()
            for _ in range(100):
                ctx.iteration(False)
                if resultados:
                    break
                time.sleep(0.02)
        self.assertIsInstance(resultados[0], RuntimeError)


class TestBandeja(unittest.TestCase):
    def test_menu_da_bandeja(self):
        from tray import Tray
        t = Tray.__new__(Tray)                           # sem registrar no barramento
        t.items = [(1, "Abrir", None, None), (2, "Modo Dota", None, lambda: True),
                   (3, None, None, None), (4, "Sair", None, None)]
        t.revision = 7
        layout = t._layout().unpack()
        self.assertEqual(layout[0], 7)
        filhos = layout[1][2]
        self.assertEqual([f[1].get("label") for f in filhos], ["Abrir", "Modo Dota", None, "Sair"])
        self.assertEqual(filhos[1][1]["toggle-state"], 1)
        self.assertEqual(filhos[2][1]["type"], "separator")


class TestAcordeao(unittest.TestCase):
    def test_abrir_uma_fecha_as_outras(self):
        tmp = tempfile.TemporaryDirectory()
        with mock.patch.object(ui.rc, "USER_CONFIG", os.path.join(tmp.name, "c.json")):
            app = mock.MagicMock()
            app.cfg = ui.rc.user_config()
            win = ui.Window.__new__(ui.Window)
            win.rows = [ui.ZoneRow(z, l, app.cfg, lambda: None) for z, l, _ in ui.rc.ZONES[:3]]
            for r in win.rows:
                r.expander.connect("notify::expanded", win._accordion)
            win.rows[0].expander.set_expanded(True)
            win.rows[1].expander.set_expanded(True)
            self.assertEqual([r.expander.get_expanded() for r in win.rows], [False, True, False])
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
