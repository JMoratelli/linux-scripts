"""Ligar/desligar tudo pelo rgb-casa (sem sessao grafica: so a classe Engine)."""
import os
import signal
import unittest
from unittest import mock

from helpers import LEDS, load_script

if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
    raise unittest.SkipTest("sem sessao grafica (o modulo importa o GTK)")

ui = load_script(os.path.join(LEDS, "rgb-casa"), "rgb_casa_motor")


class TestMotor(unittest.TestCase):
    def test_abrir_sobe_o_supervisor_se_nao_existir(self):
        eng = ui.Engine("/x/openrgb-gabinete")
        with mock.patch.object(ui, "process_pids", return_value=[]), \
             mock.patch.object(ui.subprocess, "Popen") as popen, \
             mock.patch.object(ui, "systemctl_user") as sysctl:
            eng.start(dota=True)
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0], ["/x/openrgb-gabinete"])
        sysctl.assert_called_with("start", "dota-rgb.service")

    def test_abrir_nao_duplica_o_supervisor(self):
        eng = ui.Engine("/x/openrgb-gabinete")
        with mock.patch.object(ui, "process_pids", return_value=[123]), \
             mock.patch.object(ui.subprocess, "Popen") as popen, \
             mock.patch.object(ui, "systemctl_user") as sysctl:
            eng.start(dota=False)
        popen.assert_not_called()
        sysctl.assert_not_called()

    def test_sair_apaga_e_encerra_tudo(self):
        eng = ui.Engine("/x/openrgb-gabinete")
        calls = []
        with mock.patch.object(ui.Engine, "blackout", side_effect=lambda: calls.append("preto")), \
             mock.patch.object(ui, "process_pids", return_value=[111]), \
             mock.patch.object(ui, "openrgb_pids", side_effect=[[222], [], []]), \
             mock.patch.object(ui.os, "kill", side_effect=lambda p, s: calls.append((p, s))), \
             mock.patch.object(ui, "systemctl_user", side_effect=lambda *a: calls.append(a)), \
             mock.patch.object(ui.rc, "release_wled", side_effect=lambda: calls.append("solta wled")), \
             mock.patch.object(ui.time, "sleep"):
            eng.stop(timeout=2)
        self.assertEqual(calls[0], ("stop", "dota-rgb.service"))
        self.assertEqual(calls[1], "preto")               # apaga antes de encerrar
        self.assertIn((111, signal.SIGTERM), calls)       # supervisor desligado de proposito
        self.assertNotIn((222, signal.SIGKILL), calls)    # saiu a tempo: nada forcado
        self.assertEqual(calls[-1], "solta wled")         # WLED volta aos efeitos dela no fim

    def test_sair_forca_openrgb_que_nao_fecha(self):
        eng = ui.Engine("/x/openrgb-gabinete")
        mortos = []
        with mock.patch.object(ui.Engine, "blackout"), \
             mock.patch.object(ui, "process_pids", return_value=[]), \
             mock.patch.object(ui, "openrgb_pids", return_value=[222]), \
             mock.patch.object(ui.os, "kill", side_effect=lambda p, s: mortos.append((p, s))), \
             mock.patch.object(ui, "systemctl_user"), \
             mock.patch.object(ui.time, "sleep"), \
             mock.patch.object(ui.rc, "release_wled"), \
             mock.patch.object(ui.time, "monotonic", side_effect=[0, 1, 5, 99, 99]):
            eng.stop(timeout=2)
        self.assertIn((222, signal.SIGKILL), mortos)

    def test_sair_com_openrgb_ja_fechado(self):
        eng = ui.Engine("/x/openrgb-gabinete")
        with mock.patch.object(ui.Engine, "blackout", side_effect=ConnectionRefusedError), \
             mock.patch.object(ui, "process_pids", return_value=[]), \
             mock.patch.object(ui, "openrgb_pids", return_value=[]), \
             mock.patch.object(ui.rc, "release_wled"), \
             mock.patch.object(ui, "systemctl_user"):
            eng.stop()                                    # nao levanta erro

    def test_blackout_apaga_tudo_menos_a_wled(self):
        import tempfile
        from helpers import FakeOpenRGB
        import rgbsdk
        fake = FakeOpenRGB([("Razer Chroma Addressable RGB Controller", [("Channel 1", 3, 0, 80)]),
                            (ui.rc.WLED["name"], [("WLED", 2, 2, 2)])])
        orig = rgbsdk.SDK.__init__
        tmp = tempfile.TemporaryDirectory()
        try:
            with mock.patch.object(rgbsdk.SDK, "__init__",
                                   lambda self, n, host="127.0.0.1", port=6742: orig(self, n, port=fake.port)), \
                 mock.patch.object(ui.rc, "CFG", tmp.name), \
                 mock.patch.object(ui.time, "sleep"):
                ui.Engine.blackout()
            import time as _t
            _t.sleep(0.2)
            leds = [dev for dev, pkt, _ in fake.received if pkt == 1050]
            self.assertEqual(leds, [0])                   # so a Razer; a WLED nao
            self.assertIn(152, [pkt for _, pkt, _ in fake.received])   # carregou o perfil sem efeitos
        finally:
            fake.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
