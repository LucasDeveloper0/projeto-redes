"""Formato do pacote usado por rdt3.0, Go-Back-N e Repetição Seletiva.

Todo pacote é um CABEÇALHO de 13 bytes seguido pelos DADOS (0 a ~1024 bytes):

    campo      bytes  formato  para que serve
    ---------  -----  -------  -------------------------------------------------
    tipo         1    B        DADOS (0) ou ACK (1)
    seq_num      4    I        número de sequência do pacote de dados
    ack_num      4    I        número confirmado (só tem sentido nos ACKs)
    checksum     2    H        soma de verificação de 16 bits (detecta corrupção)
    tamanho      2    H        quantos bytes de dados vêm depois do cabeçalho

O "!" no formato "!BIIHH" significa ordem de bytes de REDE (big-endian), a mesma
em qualquer máquina. Sem ele, dois computadores poderiam ler os números ao contrário.

Pacote DADOS com 0 byte de dados = marcador de FIM do arquivo (usado pelos protocolos).
"""
import struct

DADOS = 0  # pacote que carrega um pedaço do arquivo
ACK = 1    # pacote de confirmação (acknowledgment)


class Packet:
    """Monta (make) e valida/decodifica (extract) pacotes. Não guarda estado."""

    HEADER_FORMAT = "!BIIHH"                        # tipo, seq, ack, checksum, tamanho
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)    # 1+4+4+2+2 = 13 bytes

    @staticmethod
    def _checksum(b: bytes) -> int:
        """Checksum da Internet: soma de palavras de 16 bits em complemento de um.

        Passos (iguais aos do UDP/TCP, cap. 3 do Kurose & Ross):
          1. divide os bytes em palavras de 16 bits (completa com 0 se o tamanho for ímpar);
          2. soma tudo; se a soma passar de 16 bits, o "vai um" é somado de volta
             (isso é o complemento de um);
          3. inverte todos os bits do resultado.
        O receptor refaz a conta: se um único bit mudou no caminho, o valor difere.
        """
        if len(b) % 2:
            b += b"\x00"                            # padding: número par de bytes
        s = 0
        for i in range(0, len(b), 2):
            s += (b[i] << 8) | b[i + 1]             # junta 2 bytes em 1 palavra de 16 bits
            s = (s & 0xFFFF) + (s >> 16)            # "vai um": soma o excesso de volta
        return ~s & 0xFFFF                          # inverte os bits, mantém 16 bits

    @staticmethod
    def make(pkt_type, seq_num, ack_num, data: bytes = b"") -> bytes:
        """Monta o pacote: cabeçalho (com checksum calculado) + dados."""
        length = len(data)
        # O checksum cobre cabeçalho + dados, mas o próprio campo checksum ainda não
        # existe. Por isso ele entra ZERADO no cálculo; o valor real só é gravado depois.
        sem_checksum = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, 0, length)
        checksum = Packet._checksum(sem_checksum + data)
        header = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, checksum, length)
        return header + data

    @staticmethod
    def extract(packet_bytes: bytes):
        """Valida e decodifica um pacote recebido.

        Devolve (tipo, seq_num, ack_num, checksum, dados) se estiver íntegro, ou None
        se estiver corrompido. Quem chama trata None como pacote perdido (descarta).
        """
        if len(packet_bytes) < Packet.HEADER_SIZE:
            return None                             # menor que o cabeçalho: lixo
        header = packet_bytes[:Packet.HEADER_SIZE]
        data = packet_bytes[Packet.HEADER_SIZE:]
        pkt_type, seq_num, ack_num, checksum, length = struct.unpack(Packet.HEADER_FORMAT, header)
        if length != len(data):
            return None                             # o campo "tamanho" não bate com os dados
        # Refaz o cálculo do emissor: zera o campo checksum e recalcula. Se o resultado
        # for diferente do valor recebido, algum bit mudou no caminho.
        sem_checksum = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, 0, length)
        if Packet._checksum(sem_checksum + data) != checksum:
            return None
        return pkt_type, seq_num, ack_num, checksum, data

    @staticmethod
    def is_valid(packet_bytes: bytes) -> bool:
        """Atalho: True se o pacote passa na verificação do checksum."""
        return Packet.extract(packet_bytes) is not None
