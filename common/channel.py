"""Canal não confiável: simula, sobre um socket UDP, uma rede que perde e corrompe pacotes.

Conceito da aula: o canal subjacente do rdt3.0 (Kurose) pode corromper bits e perder
pacotes. Em localhost o UDP quase nunca falha, então este canal injeta as falhas de
propósito e de forma controlada, para mostrar os mecanismos de recuperação funcionando:

    corrupção -> o checksum do receptor detecta -> pacote descartado
    perda     -> nenhum ACK volta              -> timeout do remetente -> retransmissão

A classe tem a mesma interface de um socket UDP (sendto, recvfrom, bind, settimeout,
close), então os protocolos a usam no lugar do socket comum, sem outra mudança.
"""
import queue
import random
import socket
import threading
import time


class UnreliableSocket:
    """Socket UDP que perde, corrompe e atrasa os pacotes que ENVIA.

    loss    : probabilidade (0 a 1) de perder cada pacote enviado
    corrupt : probabilidade (0 a 1) de corromper (inverter 1 bit) um pacote não perdido
    delay   : atraso de propagação, em segundos (0 = sem atraso)
    seed    : semente do gerador aleatório; com a mesma semente, as mesmas perdas e
              corrupções acontecem sempre (testes reproduzíveis)

    A falha é aplicada no envio. Por isso, para falhar nos dois sentidos (dados e ACKs),
    tanto o remetente quanto o receptor usam um UnreliableSocket.
    """

    def __init__(self, loss=0.0, corrupt=0.0, delay=0.0, seed=None):
        # Socket UDP de verdade, por baixo: o canal só decide o que sai por ele.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loss = loss
        self.corrupt = corrupt
        self.delay = delay
        # Gerador próprio (e não o global) para a semente fixa valer só para este canal.
        self.rng = random.Random(seed)
        # Contadores usados pelos testes para provar que a falha realmente aconteceu.
        self.enviados = self.perdidos = self.corrompidos = 0
        self._fila_atraso = None  # criada sob demanda quando delay > 0

    def sendto(self, data, addr):
        """Envia um pacote, aplicando perda, corrupção e atraso, nesta ordem."""
        self.enviados += 1
        # Perda: o pacote some no caminho. Devolve len(data) como se tivesse sido enviado,
        # porque quem envia não fica sabendo; só percebe pela falta do ACK (timeout).
        if self.rng.random() < self.loss:
            self.perdidos += 1
            return len(data)
        # Corrupção: o pacote chega, mas com 1 bit trocado. O checksum do receptor
        # (Packet.extract) vai detectar e descartar. Só pacotes não perdidos são corrompidos.
        if data and self.rng.random() < self.corrupt:
            self.corrompidos += 1
            data = self._inverter_bit(data)
        if self.delay > 0:
            # Atraso de propagação simulado sem bloquear o remetente:
            # o pacote fica "em trânsito" e a janela continua enviando.
            # (Um time.sleep aqui travaria o envio de toda a janela no GBN e na SR.)
            if self._fila_atraso is None:
                self._fila_atraso = queue.Queue()
                threading.Thread(target=self._entregar_atraso, daemon=True).start()
            # Guarda o instante em que o pacote deve sair, junto com os dados.
            self._fila_atraso.put((time.monotonic() + self.delay, data, addr))
            return len(data)
        return self.sock.sendto(data, addr)

    def _entregar_atraso(self):
        """Thread que entrega os pacotes atrasados, na hora certa."""
        # Uma única thread entrega em FIFO: como o atraso é constante,
        # a ordem de envio é preservada (sem reordenar pacotes).
        while True:
            item = self._fila_atraso.get()
            if item is None:  # sinal de encerramento enviado por close()
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
        """Simula ruído no meio físico: inverte 1 bit, em byte e posição sorteados."""
        b = bytearray(data)
        # XOR com uma máscara de um único bit (1 << 0 até 1 << 7) troca só aquele bit.
        b[self.rng.randrange(len(b))] ^= 1 << self.rng.randrange(8)
        return bytes(b)

    # Os métodos abaixo apenas repassam ao socket UDP real. Eles existem para o canal ter
    # a mesma interface de um socket e poder substituí-lo nos protocolos.

    def recvfrom(self, n):
        """Recebe um pacote (de até n bytes). A falha é aplicada no envio, não aqui."""
        return self.sock.recvfrom(n)

    def settimeout(self, t):
        """Define o tempo máximo de espera do recvfrom; base do temporizador do protocolo."""
        self.sock.settimeout(t)

    def bind(self, addr):
        self.sock.bind(addr)

    def close(self):
        if self._fila_atraso is not None:
            self._fila_atraso.put(None)  # encerra a thread de entrega
        self.sock.close()
