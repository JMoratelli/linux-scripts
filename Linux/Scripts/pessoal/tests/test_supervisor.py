import os
import unittest

from helpers import LEDS, load_script

launcher = load_script(os.path.join(LEDS, "openrgb-gabinete"), "openrgb_gabinete")


class Fake:
    def __init__(self, codes):
        self.codes = list(codes)
        self.runs = 0
        self.t = 0.0

    def run(self):
        self.runs += 1
        return self.codes.pop(0)

    def sleep(self, s):
        self.t += s

    def clock(self):
        return self.t


class TestSupervisor(unittest.TestCase):
    def test_saida_normal_nao_reabre(self):
        f = Fake([0])
        self.assertEqual(launcher.supervise(f.run, f.sleep, f.clock), 0)
        self.assertEqual(f.runs, 1)

    def test_queda_reabre(self):
        f = Fake([-6, -6, 0])                      # abortou duas vezes, depois saiu normal
        self.assertEqual(launcher.supervise(f.run, f.sleep, f.clock), 0)
        self.assertEqual(f.runs, 3)

    def test_desiste_se_cair_demais(self):
        f = Fake([-6] * 50)
        code = launcher.supervise(f.run, f.sleep, f.clock)
        self.assertEqual(code, -6)
        self.assertEqual(f.runs, launcher.MAX_RESTARTS + 1)

    def test_quedas_espacadas_nao_esgotam(self):
        f = Fake([-6] * 20 + [0])
        orig = f.sleep
        f.sleep = lambda s: orig(launcher.RESTART_WINDOW)   # cada queda bem depois da outra
        self.assertEqual(launcher.supervise(f.run, f.sleep, f.clock), 0)
        self.assertEqual(f.runs, 21)


class TestDesligar(unittest.TestCase):
    def test_encerra_o_openrgb_sem_reabrir(self):
        import subprocess
        proc = subprocess.Popen(["sleep", "30"])
        launcher.stop_child(proc)
        self.assertIsNotNone(proc.poll())            # encerrou

    def test_forca_se_nao_sair(self):
        import subprocess
        proc = subprocess.Popen(["sh", "-c", "trap '' TERM; sleep 30"])
        old = launcher.STOP_TIMEOUT
        launcher.STOP_TIMEOUT = 0.5
        try:
            launcher.stop_child(proc)
        finally:
            launcher.STOP_TIMEOUT = old
        self.assertIsNotNone(proc.poll())


if __name__ == "__main__":
    unittest.main()
