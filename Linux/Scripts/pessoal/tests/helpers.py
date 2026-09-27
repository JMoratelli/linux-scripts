"""Utilitarios dos testes: carregar scripts sem extensao e um OpenRGB falso."""
import importlib.machinery
import importlib.util
import os
import socket
import struct
import sys
import threading

PESSOAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDS = os.path.join(PESSOAL, "leds")
PERIFERICOS = os.path.join(PESSOAL, "perifericos")
sys.path.insert(0, LEDS)


def load_script(path, name):
    """Importa um script executavel (sem .py) como modulo."""
    loader = importlib.machinery.SourceFileLoader(name, path)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# OpenRGB falso: fala o suficiente do SDK (protocolo 3) para os testes
# ---------------------------------------------------------------------------
def _string(s):
    b = s.encode() + b"\0"
    return struct.pack("<H", len(b)) + b


def controller_blob(name, zones, ctype=4):
    """Descricao de controlador no formato do SDK. zones: [(nome, leds, min, max)]."""
    body = struct.pack("<i", ctype) + _string(name)
    for extra in ("vendor", "descricao", "v1", "serial", "local"):
        body += _string(extra)
    # um modo "Direct" sem cores
    body += struct.pack("<H", 1) + struct.pack("<i", 0)
    body += _string("Direct") + struct.pack("<iIIIIIIIIIII", 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    body += struct.pack("<H", 0)
    body += struct.pack("<H", len(zones))
    total = 0
    for zname, count, lmin, lmax in zones:
        body += _string(zname) + struct.pack("<iIII", 1, lmin, lmax, count) + struct.pack("<H", 0)
        total += count
    body += struct.pack("<H", total)
    return struct.pack("<I", len(body) + 4) + body


class FakeOpenRGB:
    """Servidor TCP que responde contagem/dados de controladores e guarda os
    pacotes recebidos (perfis carregados, LEDs, redimensionamentos)."""

    def __init__(self, controllers):
        self.controllers = controllers                 # [(nome, zonas)]
        self.active = "Gabinete"
        self.received = []                             # (dev, pkt, data)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.running = True
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self):
        self.running = False
        self.sock.close()

    def _serve(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    @staticmethod
    def _exact(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError
            buf += chunk
        return buf

    def _reply(self, conn, dev, pkt, data):
        conn.sendall(b"ORGB" + struct.pack("<III", dev, pkt, len(data)) + data)

    def _client(self, conn):
        try:
            while True:
                _, dev, pkt, size = struct.unpack("<4sIII", self._exact(conn, 16))
                data = self._exact(conn, size)
                self.received.append((dev, pkt, data))
                if pkt == 40:
                    self._reply(conn, 0, 40, struct.pack("<I", 4))
                elif pkt == 0:
                    self._reply(conn, 0, 0, struct.pack("<I", len(self.controllers)))
                elif pkt == 1:
                    name, zones = self.controllers[dev]
                    self._reply(conn, dev, 1, controller_blob(name, zones))
                elif pkt == 152:
                    self.active = data.rstrip(b"\0").decode()
                elif pkt == 156:
                    self._reply(conn, 0, 156, self.active.encode() + b"\0")
        except (ConnectionError, OSError, struct.error):
            conn.close()
