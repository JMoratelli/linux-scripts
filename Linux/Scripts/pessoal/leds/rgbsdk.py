"""Cliente minimo do SDK do OpenRGB (protocolo 3), sem dependencias.

Usado pelo openrgb-gabinete e pelo dota-rgb.
"""
import socket
import struct

PROTO = 3


class Reader:
    def __init__(self, data):
        self.d, self.o = data, 0

    def take(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.o)
        self.o += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]

    def string(self):
        n = self.take("H")
        s = self.d[self.o:self.o + n].rstrip(b"\0").decode(errors="replace")
        self.o += n
        return s


class Zone:
    def __init__(self, name, count, lmin, lmax, start):
        self.name, self.count, self.min, self.max, self.start = name, count, lmin, lmax, start


class Controller:
    def __init__(self, index, data):
        self.index = index
        r = Reader(data)
        r.take("Ii")                                  # tamanho, tipo
        self.name = r.string()
        for _ in range(5):                            # vendor, descricao, versao, serial, local
            r.string()
        nmodes = r.take("H")
        r.take("i")                                   # modo ativo
        for _ in range(nmodes):
            r.string()
            r.take("iIIIIIIIIIII")
            ncolors = r.take("H")
            r.o += 4 * ncolors
        self.zones = []
        start = 0
        for _ in range(r.take("H")):
            zname = r.string()
            _, lmin, lmax, count = r.take("iIII")
            mlen = r.take("H")
            r.o += mlen
            self.zones.append(Zone(zname, count, lmin, lmax, start))
            start += count
        self.num_leds = r.take("H")


class SDK:
    def __init__(self, client_name, host="127.0.0.1", port=6742):
        self.s = socket.create_connection((host, port), timeout=5)
        self.send(0, 40, struct.pack("<I", PROTO))
        self.proto = min(PROTO, struct.unpack("<I", self.recv(40))[0])
        self.send(0, 50, client_name.encode() + b"\0")

    def close(self):
        self.s.close()

    def send(self, dev, pkt, data=b""):
        self.s.sendall(b"ORGB" + struct.pack("<III", dev, pkt, len(data)) + data)

    def _exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("OpenRGB fechou a conexao")
            buf += chunk
        return buf

    def recv(self, want):
        while True:
            _, _, pkt, size = struct.unpack("<4sIII", self._exact(16))
            data = self._exact(size)
            if pkt == want:
                return data

    def controllers(self):
        self.send(0, 0)
        n = struct.unpack("<I", self.recv(0))[0]
        out = []
        for i in range(n):
            self.send(i, 1, struct.pack("<I", self.proto))
            out.append(Controller(i, self.recv(1)))
        return out

    def resize_zone(self, dev, zone, size):
        self.send(dev, 1000, struct.pack("<ii", zone, size))

    def custom_mode(self, dev):
        self.send(dev, 1100)

    def update_leds(self, dev, colors):
        """colors: sequencia de (r, g, b) com um item por LED do controlador."""
        body = struct.pack("<H", len(colors)) + b"".join(
            struct.pack("<BBBx", *c) for c in colors)
        self.send(dev, 1050, struct.pack("<I", len(body) + 4) + body)

    def load_profile(self, name):
        self.send(0, 152, name.encode() + b"\0")

    def active_profile(self):
        self.send(0, 156)
        return self.recv(156).rstrip(b"\0").decode(errors="replace")
