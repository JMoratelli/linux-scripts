import os
import socket
import threading
import time
import unittest

from helpers import PERIFERICOS, load_script

ponte = load_script(os.path.join(PERIFERICOS, "teclado-ponte"), "teclado_ponte")


class FakeLed:
    """Substitui o redragon-led: conta leituras/gravacoes do bloco 0xB6."""

    def __init__(self):
        self.writes = 0

    def read_block(self, fd):
        return bytes(1032)

    def write_block(self, fd, cur):
        self.writes += 1


class FakeKeyboard(ponte.Keyboard):
    def __init__(self):                                  # sem hidraw de verdade
        self.fd = -1
        self.req = 0
        self.led = FakeLed()
        self.streaming = False
        self.frames = []

    def send(self, rgb):
        if not self.streaming:
            self.refresh_config()
            self.streaming = True
        self.frames.append(bytes(rgb))


def ddp(data, offset=0, push=True):
    flags = 0x41 if push else 0x40
    return bytes([flags, 1, 0x0B, 1]) + offset.to_bytes(4, "big") + len(data).to_bytes(2, "big") + data


class TestPonte(unittest.TestCase):
    def setUp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.listen = ponte.LISTEN
        ponte.LISTEN = ("127.0.0.1", self.port)
        self.kb = FakeKeyboard()
        threading.Thread(target=ponte.run, args=(self.kb,), daemon=True).start()
        time.sleep(0.2)
        self.out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def tearDown(self):
        ponte.LISTEN = self.listen
        self.out.close()

    def test_quadro_e_entrada_no_streaming(self):
        self.out.sendto(ddp(bytes([255, 0, 0]) * 126), ("127.0.0.1", self.port))
        time.sleep(0.3)
        self.assertTrue(self.kb.frames)
        self.assertEqual(self.kb.frames[-1][:3], b"\xff\x00\x00")
        self.assertEqual(len(self.kb.frames[-1]), 378)
        self.assertEqual(self.kb.led.writes, 1)          # regravou o 0xB6 ao entrar

    def test_pacote_parcial_com_deslocamento(self):
        self.out.sendto(ddp(b"\x01\x02\x03", offset=3), ("127.0.0.1", self.port))
        time.sleep(0.3)
        self.assertEqual(self.kb.frames[-1][:6], b"\x00\x00\x00\x01\x02\x03")

    def test_sai_do_streaming_sem_quadros(self):
        self.out.sendto(ddp(bytes(378)), ("127.0.0.1", self.port))
        time.sleep(ponte.IDLE + 0.8)
        self.assertFalse(self.kb.streaming)
        self.assertEqual(self.kb.led.writes, 2)          # entrou e saiu regravando o 0xB6

    def test_pacote_invalido_ignorado(self):
        self.out.sendto(b"\x00\x01", ("127.0.0.1", self.port))
        self.out.sendto(ddp(b"\xaa" * 5000, offset=10_000), ("127.0.0.1", self.port))
        time.sleep(0.3)
        self.assertEqual(self.kb.frames, [])


if __name__ == "__main__":
    unittest.main()
