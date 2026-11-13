import random
import socket
import time

class UnreliableSocket:

    def __init__(self, loss=0.0, corrupt=0.0, delay=0.0, seed=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loss = loss
        self.corrupt = corrupt
        self.delay = delay 
        self.rng = random.Random(seed)
        self.enviados = self.perdidos = self.corrompidos = 0

    def sendto(self, data, addr):
        self.enviados += 1
        if self.delay > 0:
            time.sleep(self.delay)  # atraso de propagação simulado
        if self.rng.random() < self.loss:
            self.perdidos += 1
            return len(data)
        if data and self.rng.random() < self.corrupt:
            self.corrompidos += 1
            data = self._inverter_bit(data)
        return self.sock.sendto(data, addr)

    def _inverter_bit(self, data):
        b = bytearray(data)
        b[self.rng.randrange(len(b))] ^= 1 << self.rng.randrange(8)
        return bytes(b)

    def recvfrom(self, n):
        return self.sock.recvfrom(n)

    def settimeout(self, t):
        self.sock.settimeout(t)

    def bind(self, addr):
        self.sock.bind(addr)

    def close(self):
        self.sock.close()