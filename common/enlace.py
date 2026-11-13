import queue
import threading
import time

from common.channel import UnreliableSocket


class EnlaceSocket(UnreliableSocket):

    def __init__(self, loss=0.0, corrupt=0.0, atraso=0.0, taxa_bps=None, seed=None):
        """
        atraso   : propagação de UMA direção, em segundos (RTT = 2 x atraso)
        taxa_bps : taxa do enlace em bits/s; None = transmissão instantânea
        """
        super().__init__(loss=loss, corrupt=corrupt, delay=0.0, seed=seed)
        self.atraso = atraso
        self.taxa_bps = taxa_bps
        self._livre = 0.0                  # instante em que o enlace fica livre
        self._fila = queue.Queue()
        self._thread = threading.Thread(target=self._entregar, daemon=True)
        self._thread.start()

    def sendto(self, data, addr):
        self.enviados += 1
        agora = time.perf_counter()
        tx = (len(data) * 8 / self.taxa_bps) if self.taxa_bps else 0.0
        saida = max(agora, self._livre) + tx   # espera o enlace ficar livre
        self._livre = saida
        chegada = saida + self.atraso

        if self.rng.random() < self.loss:      # perdido, mas já ocupou o enlace
            self.perdidos += 1
            return len(data)
        if data and self.rng.random() < self.corrupt:
            self.corrompidos += 1
            data = self._inverter_bit(data)
        self._fila.put((chegada, data, addr))  # não bloqueia o remetente
        return len(data)

    def _entregar(self):
        while True:
            item = self._fila.get()
            if item is None:
                return
            chegada, data, addr = item
            espera = chegada - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass  # o outro lado já fechou

    def close(self):
        self._fila.put(None)                   # termina depois de entregar o que falta
        self._thread.join(timeout=2.0)
        super().close()
