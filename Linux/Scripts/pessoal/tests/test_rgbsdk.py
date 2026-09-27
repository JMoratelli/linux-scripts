import time
import unittest

from helpers import FakeOpenRGB
from rgbsdk import SDK


class TestSDK(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOpenRGB([
            ("Razer Chroma Addressable RGB Controller", [("Channel 1", 40, 0, 80), ("Channel 2", 35, 0, 80)]),
            ("Redragon K629", [("Redragon K629", 126, 126, 126)]),
        ])
        self.sdk = SDK("teste", port=self.fake.port)

    def tearDown(self):
        self.sdk.close()
        self.fake.close()

    def test_negocia_protocolo_3(self):
        self.assertEqual(self.sdk.proto, 3)             # servidor diz 4, cliente fica no 3

    def test_le_controladores_e_zonas(self):
        ctrls = self.sdk.controllers()
        self.assertEqual([c.name for c in ctrls], ["Razer Chroma Addressable RGB Controller", "Redragon K629"])
        razer = ctrls[0]
        self.assertEqual([(z.name, z.count, z.start) for z in razer.zones],
                         [("Channel 1", 40, 0), ("Channel 2", 35, 40)])
        self.assertEqual(razer.num_leds, 75)

    def test_perfil_ativo_e_troca(self):
        self.assertEqual(self.sdk.active_profile(), "Gabinete")
        self.sdk.load_profile("Dota")
        self.assertEqual(self.sdk.active_profile(), "Dota")

    def test_update_leds_empacota_cores(self):
        self.sdk.update_leds(1, [(255, 0, 0), (0, 255, 0)])
        time.sleep(0.2)
        dev, pkt, data = next(r for r in self.fake.received if r[1] == 1050)
        self.assertEqual(dev, 1)
        self.assertEqual(data[4:6], b"\x02\x00")
        self.assertEqual(data[6:14], b"\xff\x00\x00\x00\x00\xff\x00\x00")


if __name__ == "__main__":
    unittest.main()
