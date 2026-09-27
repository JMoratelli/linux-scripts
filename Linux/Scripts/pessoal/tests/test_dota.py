import os
import unittest

from helpers import LEDS, load_script

dota = load_script(os.path.join(LEDS, "dota-rgb"), "dota_rgb")


class TestTeclado(unittest.TestCase):
    def setUp(self):
        self.p = dota.Painter()

    def test_so_verde_e_vermelho(self):
        self.assertEqual(self.p.slot_color({"name": "a", "level": 1, "can_cast": True, "cooldown": 0}), dota.READY)
        self.assertEqual(self.p.slot_color({"name": "a", "level": 1, "can_cast": False, "cooldown": 5}), dota.BLOCKED)
        self.assertEqual(self.p.slot_color({"name": "a", "level": 1, "can_cast": False, "cooldown": 0}), dota.BLOCKED)
        self.assertEqual(self.p.slot_color({"name": "a", "level": 1, "passive": True}), dota.READY)
        self.assertEqual(self.p.slot_color({"name": "a", "level": 0}), (0, 0, 0))
        self.assertEqual(self.p.slot_color({"name": "empty"}), (0, 0, 0))

    def test_teclas_de_acao(self):
        state = {"hero": {"alive": True},
                 "abilities": {"ability0": {"name": "q", "level": 1, "can_cast": True, "cooldown": 0},
                               "ability1": {"name": "plus_high_five", "level": 1, "can_cast": True},
                               "ability2": {"name": "ult", "level": 1, "can_cast": False, "cooldown": 9,
                                            "ultimate": True}},
                 "items": {"slot0": {"name": "item_blink", "can_cast": True, "cooldown": 0}}}
        px = self.p.keyboard(state, 126, 0)
        self.assertEqual(px[dota.KEY["Q"]], dota.READY)
        self.assertEqual(px[dota.KEY["W"]], (0, 0, 0))    # plus_* nao ocupa tecla
        self.assertEqual(px[dota.KEY["R"]], dota.BLOCKED)
        self.assertEqual(px[dota.KEY["Z"]], dota.READY)
        acesas = [i for i, c in enumerate(px) if c != (0, 0, 0)]
        self.assertEqual(sorted(acesas), sorted([dota.KEY["Q"], dota.KEY["R"], dota.KEY["Z"]]))


class TestFita(unittest.TestCase):
    def setUp(self):
        self.bar = dota.HealthBar()

    def test_cor_da_vida(self):
        cheia = self.bar.render({"alive": True, "health_percent": 100}, 66, 0)[0]
        self.assertEqual(cheia, (0, 255, 0))
        bar = dota.HealthBar()
        baixa = bar.render({"alive": True, "health_percent": 5}, 66, 0)[0]
        self.assertGreater(baixa[0], 200)
        self.assertLess(baixa[1], 60)

    def test_pulso_de_dano(self):
        self.bar.render({"alive": True, "health_percent": 80}, 66, 0.0)
        apaga = self.bar.render({"alive": True, "health_percent": 70}, 66, 0.01)
        self.assertEqual(apaga[0], (0, 0, 0))            # apaga um instante
        vermelho = self.bar.render({"alive": True, "health_percent": 70}, 66, 0.01 + dota.HealthBar.HIT_GAP)
        self.assertEqual(vermelho[0], (255, 0, 0))       # e acende vermelho puro
        depois = self.bar.render({"alive": True, "health_percent": 70}, 66, 5.0)
        self.assertNotEqual(depois[0], (255, 0, 0))      # volta a cor da vida

    def test_morte_scanner_e_renascer(self):
        self.bar.render({"alive": True, "health_percent": 50}, 66, 0)
        self.assertEqual(self.bar.render({"alive": False}, 66, 1.0), [(255, 0, 0)] * 66)
        scan = self.bar.render({"alive": False}, 66, 1.0 + dota.HealthBar.DEATH_RED + 0.3)
        head = max(scan)
        self.assertGreater(head[0], 200)                 # cabeca vermelha forte (pode cair entre LEDs)
        self.assertEqual(head[1:], (0, 0))
        self.assertIn((0, 0, 0), scan)                   # ponto com rastro, nao a fita toda
        pisca = self.bar.render({"alive": True, "health_percent": 100}, 66, 20.0)
        self.assertEqual(pisca[0], (0, 255, 0))          # renasceu: pisca verde

    def test_scanner_vai_e_volta(self):
        pos = []
        for i in range(0, 40):
            frame = dota.HealthBar.scanner(66, i * 0.05)
            pos.append(frame.index(max(frame)))
        self.assertLess(pos[0], 5)
        self.assertGreater(max(pos), 60)
        self.assertLess(pos[-1], max(pos))               # voltou depois de chegar na ponta


if __name__ == "__main__":
    unittest.main()
