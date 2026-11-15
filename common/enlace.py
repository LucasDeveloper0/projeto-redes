"""Enlace com taxa de transmissão e atraso de propagação (usado nos experimentos).

O UnreliableSocket (common/channel.py) só perde/corrompe pacotes. Para medir a
UTILIZAÇÃO do canal precisamos também de um enlace "de verdade", com:

  - taxa R (bits/s): cada pacote leva  L/R  segundos para ser colocado no enlace;
  - atraso de propagação: o pacote só chega ao outro lado depois desse tempo;
  - fila: pacotes enviados com o enlace ocupado esperam sua vez (um atrás do outro).

Assim, o RTT mínimo é 2 x atraso e um pipeline (GBN/SR) consegue ter várias
janelas de pacotes "no ar" ao mesmo tempo, enquanto o pare-e-espera deixa o
enlace parado esperando o ACK. É exatamente isso que o gráfico de utilização mostra.
"""
import queue
import threading
import time

from common.channel import UnreliableSocket


class EnlaceSocket(UnreliableSocket):
    """UnreliableSocket + taxa de transmissão + atraso de propagação + fila."""

    def __init__(self, loss=0.0, corrupt=0.0, atraso=0.0, taxa_bps=None, seed=None):
        """
        atraso   : propagação de UMA direção, em segundos (RTT = 2 x atraso)
        taxa_bps : taxa do enlace em bits/s; None = transmissão instantânea
        """
        # delay=0.0: o atraso NÃO é aplicado pela classe-mãe (ela bloquearia o
        # remetente com sleep). Aqui o atraso é aplicado por uma thread de entrega.
        super().__init__(loss=loss, corrupt=corrupt, delay=0.0, seed=seed)
        self.atraso = atraso
        self.taxa_bps = taxa_bps
        self._livre = 0.0                  # instante em que o enlace fica livre
        self._fila = queue.Queue()         # pacotes à espera da hora de chegar
        # Thread em segundo plano que entrega cada pacote no instante certo
        self._thread = threading.Thread(target=self._entregar, daemon=True)
        self._thread.start()

    def sendto(self, data, addr):
        """Aceita o pacote sem bloquear e agenda a sua chegada ao destino."""
        self.enviados += 1
        agora = time.perf_counter()
        # Tempo para "empurrar" os bits no enlace: L / R
        tx = (len(data) * 8 / self.taxa_bps) if self.taxa_bps else 0.0
        # O pacote só começa a sair quando o enlace está livre (fila FIFO) ...
        saida = max(agora, self._livre) + tx   # espera o enlace ficar livre
        self._livre = saida                    # ... e o ocupa até terminar de sair
        # Chega ao destino depois do atraso de propagação
        chegada = saida + self.atraso

        if self.rng.random() < self.loss:      # perdido, mas já ocupou o enlace
            self.perdidos += 1                 # (perda não "devolve" o tempo de enlace)
            return len(data)
        # Só corrompe pacotes com dados (não mexe em datagramas vazios)
        if data and self.rng.random() < self.corrupt:
            self.corrompidos += 1
            data = self._inverter_bit(data)    # inverte 1 bit; o checksum deve detectar
        self._fila.put((chegada, data, addr))  # não bloqueia o remetente
        return len(data)

    def _entregar(self):
        """Thread de entrega: espera até a hora de chegada e envia pelo UDP real."""
        while True:
            item = self._fila.get()
            if item is None:                   # sinal de encerramento (ver close)
                return
            chegada, data, addr = item
            # Como o enlace é FIFO, as chegadas já saem em ordem crescente
            espera = chegada - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass  # o outro lado já fechou

    def close(self):
        """Entrega o que ainda estiver na fila, encerra a thread e fecha o socket."""
        self._fila.put(None)                   # termina depois de entregar o que falta
        self._thread.join(timeout=2.0)
        super().close()
