import json
import os
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401  (ajusta o sys.path)
import rgb_config as rc

PLUGIN = rc.PLUGIN


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(rc, "CFG", self.tmp.name),
                        mock.patch.object(rc, "USER_CONFIG", os.path.join(self.tmp.name, "rgb-casa.json"))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def effects(self, name):
        with open(rc.profile_path(name)) as f:
            return json.load(f)["plugins"][PLUGIN]["Effects"]


class TestCatalogo(Base):
    def test_todo_efeito_gera_configuracao_valida(self):
        for eff in rc.CATALOG:
            for band in rc.BANDS:
                cls, custom, brightness = rc.plugin_effect({"effect": eff, "band": band})
                self.assertIsInstance(cls, str)
                self.assertIsInstance(custom, dict)
                self.assertTrue(0 <= brightness <= 100)
                if "audio_settings" in custom:
                    self.assertEqual(len(custom["audio_settings"]["equalizer"]), 16)
                    self.assertTrue(any(custom["audio_settings"]["equalizer"]), (eff, band))

    def test_efeito_desconhecido_vira_apagado(self):
        self.assertEqual(rc.plugin_effect({"effect": "nao-existe"})[2], 0)
        self.assertEqual(rc.plugin_effect({"effect": "apagado", "brightness": 80})[2], 0)

    def test_estrela_sempre_inclui_banda_4(self):
        # numa zona linear o AudioStar le so a banda 4; sem ela o fan apaga
        for band in rc.BANDS:
            eq = rc.plugin_effect({"effect": "estrela", "band": band})[1]["audio_settings"]["equalizer"]
            self.assertEqual(eq[4], 1.0, band)

    def test_brilho_limitado(self):
        self.assertEqual(rc.plugin_effect({"effect": "vu", "brightness": 250})[2], 100)
        self.assertEqual(rc.plugin_effect({"effect": "vu", "brightness": -5})[2], 0)

    def test_velocidade_dentro_da_faixa_do_efeito(self):
        for cls, (lo, hi) in rc.SPEED_RANGE.items():
            for speed in (0, 50, 100, 500, -3):
                v = rc.plugin_speed(cls, {"speed": speed})
                self.assertTrue(lo <= v <= hi, (cls, speed, v))

    def test_paleta_sempre_com_cinco_cores(self):
        # alguns efeitos leem UserColors[0] e [1] sem conferir: lista vazia derruba o OpenRGB
        for zcfg in ({}, {"hue": 0}, {"hue": 359, "hue_spread": 360}):
            self.assertEqual(len(rc.palette(zcfg)), 5)
        for e in rc.effects_for(rc.user_config()):
            self.assertGreaterEqual(len(e["UserColors"]), 2)


class TestPerfis(Base):
    def test_padroes_sao_os_aprovados(self):
        rc.profile_json()
        por_zona = {}
        for e in self.effects(rc.PROFILE):
            for z in e["ControllerZones"]:
                por_zona[(z["name"], z["zone_idx"])] = e["EffectClassName"]
        self.assertEqual(por_zona[(rc.RAZER["name"], 2)], "AudioVUMeter")      # fan frontal
        self.assertEqual(por_zona[(rc.RAZER["name"], 1)], "AudioStar")         # fan superior 1
        self.assertEqual(por_zona[(rc.RAZER["name"], 3)], "AudioVUMeter")      # fan superior 2
        self.assertEqual(por_zona[(rc.RAZER["name"], 4)], "AudioParty")        # H100
        self.assertEqual(por_zona[(rc.KEYBOARD["name"], 0)], "AudioVisualizer")
        self.assertEqual(por_zona[(rc.WLED["name"], 0)], "AudioStar")

    def test_dota_sem_teclado_e_wled(self):
        rc.dota_profile_json()
        nomes = {z["name"] for e in self.effects(rc.PROFILE_DOTA) for z in e["ControllerZones"]}
        self.assertNotIn(rc.KEYBOARD["name"], nomes)
        self.assertNotIn(rc.WLED["name"], nomes)
        self.assertIn(rc.RAZER["name"], nomes)

    def test_zonas_iguais_dividem_a_instancia(self):
        cfg = rc.user_config()
        efeitos = rc.effects_for(cfg)
        sync = [e for e in efeitos if e["EffectClassName"] == "AudioSync"]
        self.assertEqual(len(sync), 1)                  # fonte, GPU e placa-mae juntos
        self.assertEqual(len(sync[0]["ControllerZones"]), 1 + 5 + 2)

    def test_tela_numa_instancia_so(self):
        cfg = rc.user_config()
        for zid in ("fan_frontal", "wled", "teclado"):
            cfg["zones"][zid] = {"effect": "tela", "brightness": 100}
        cfg["zones"]["wled"]["brightness"] = 40        # mesmo com brilhos diferentes
        ambient = [e for e in rc.effects_for(cfg) if e["EffectClassName"] == "Ambient"]
        self.assertEqual(len(ambient), 1)
        self.assertEqual(len(ambient[0]["ControllerZones"]), 3)

    def test_token_da_tela_preservado(self):
        cfg = rc.user_config()
        cfg["zones"]["wled"] = {"effect": "tela"}
        rc.profile_json(cfg)
        with open(rc.profile_path(rc.PROFILE)) as f:
            data = json.load(f)
        for e in data["plugins"][PLUGIN]["Effects"]:
            if e["EffectClassName"] == "Ambient":
                e["CustomSettings"]["restore_token"] = "tok-123"
        rc.save(rc.profile_path(rc.PROFILE), data)
        rc.profile_json(cfg)                              # regravar nao perde o token
        rc.dota_profile_json(cfg)
        self.assertEqual(rc.screen_token(rc.PROFILE), "tok-123")

    def test_configuracao_mesclada_com_padroes(self):
        rc.save_user_config({"dota": False, "zones": {"fan_frontal": {"effect": "arco-iris"},
                                                      "zona_velha": {"effect": "vu"}}})
        cfg = rc.user_config()
        self.assertFalse(cfg["dota"])
        self.assertEqual(cfg["zones"]["fan_frontal"]["effect"], "arco-iris")
        self.assertEqual(cfg["zones"]["fan_frontal"]["band"], "grave")    # resto do padrao fica
        self.assertNotIn("zona_velha", cfg["zones"])
        self.assertEqual(set(cfg["zones"]), {z[0] for z in rc.ZONES})

    def test_configuracao_corrompida_usa_padroes(self):
        os.makedirs(os.path.dirname(rc.USER_CONFIG), exist_ok=True)
        with open(rc.USER_CONFIG, "w") as f:
            f.write("{nao e json")
        self.assertEqual(rc.user_config()["zones"]["teclado"]["effect"], "barras")

    def test_apply_com_openrgb_fechado(self):
        with mock.patch("rgbsdk.SDK", side_effect=ConnectionRefusedError):
            self.assertFalse(rc.apply(rc.user_config()))
        self.assertTrue(os.path.exists(rc.profile_path(rc.PROFILE)))

    def test_apply_recarrega_o_perfil_ativo(self):
        from helpers import FakeOpenRGB
        import rgbsdk
        fake = FakeOpenRGB([])
        fake.active = rc.PROFILE_DOTA
        orig = rgbsdk.SDK.__init__
        try:
            with mock.patch.object(rgbsdk.SDK, "__init__",
                                   lambda self, name, host="127.0.0.1", port=6742: orig(self, name, port=fake.port)):
                self.assertTrue(rc.apply(rc.user_config()))
            loads = [d for _, pkt, d in fake.received if pkt == 152]
            self.assertEqual(loads[-1].rstrip(b"\0").decode(), rc.PROFILE_DOTA)
        finally:
            fake.close()


if __name__ == "__main__":
    unittest.main()
