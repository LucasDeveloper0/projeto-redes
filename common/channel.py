import queue
import random
import socket
import threading
import time

class UnreliableSocket:

    def __init__(self, loss=0.0, corrupt=0.0, delay=0.0, seed=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loss = loss
        self.corrupt = corrupt
        self.delay = delay
        self.rng = random.Random(seed)
        self.enviados = self.perdidos = self.corrompidos = 0
        self._fila_atraso = None  # criada sob demanda quando delay > 0

    def sendto(self, data, addr):
        self.enviados += 1
        if self.rng.random() < self.loss:
            self.perdidos += 1
            return len(data)
        if data and self.rng.random() < self.corrupt:
            self.corrompidos += 1
            data = self._inverter_bit(data)
        if self.delay > 0:
            # Atraso de propagação simulado sem bloquear o remetente:
            # o pacote fica "em trânsito" e a janela continua enviando.
            if self._fila_atraso is None:
                self._fila_atraso = queue.Queue()
                threading.Thread(target=self._entregar_atraso, daemon=True).start()
            self._fila_atraso.put((time.monotonic() + self.delay, data, addr))
            return len(data)
        return self.sock.sendto(data, addr)

    def _entregar_atraso(self):
        # Uma única thread entrega em FIFO: como o atraso é constante,
        # a ordem de envio é preservada (sem reordenar pacotes).
        while True:
            item = self._fila_atraso.get()
            if item is None:
                return
            vencimento, data, addr = item
            espera = vencimento - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            try:
                self.sock.sendto(data, addr)
            except OSError:
                return  # socket já foi fechado

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
        if self._fila_atraso is not None:
            self._fila_atraso.put(None)  # encerra a thread de entrega
        self.sock.close()
