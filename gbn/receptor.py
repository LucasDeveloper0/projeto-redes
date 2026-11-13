"""Go-Back-N: receptor.

Conceitos da aula:
  * aceita SÓ o pacote esperado (seq == esperado), sem buffer de fora de ordem;
  * pacote fora de ordem (ou duplicado) é descartado e o receptor reenvia o ACK
    do último pacote entregue em ordem (ACK cumulativo);
  * pacote com checksum inválido é descartado como se nunca tivesse chegado.
"""
import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m gbn.receptor" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402
from rdt30.receptor import BUFFER, INATIVIDADE_PADRAO, LINGER_PADRAO  # noqa: E402

log = logging.getLogger("gbn.rx")


def _enviar_ack(sock, destino, ack):
    # ACK: seq_num não é usado; o número confirmado (cumulativo) vai em ack_num
    sock.sendto(Packet.make(ACK, 0, ack), destino)


def receber_arquivo(sock, saida, inatividade=INATIVIDADE_PADRAO, linger=LINGER_PADRAO):
    """Recebe o arquivo com Go-Back-N e devolve as estatísticas da recepção."""
    st = {
        "bytes_recebidos": 0,
        "pacotes_validos": 0,
        "pacotes_corrompidos": 0,
        "pacotes_fora_de_ordem": 0,
        "pacotes_duplicados": 0,
    }
    esperado = 0        # único seq aceito agora
    ultimo_ack = None   # seq do último pacote entregue em ordem (None = nada ainda)
    origem = None       # endereço do remetente, aprendido no primeiro pacote

    def repetir_ack():
        # ACK é unsigned (4 bytes): sem nada entregue ainda não há o que confirmar,
        # o remetente reenvia por timeout
        if ultimo_ack is not None:
            _enviar_ack(sock, origem, ultimo_ack)

    with open(saida, "wb") as f:
        sock.settimeout(inatividade)
        while True:
            try:
                dados, origem = sock.recvfrom(BUFFER)
            except socket.timeout:
                raise TimeoutError(f"nenhum pacote recebido em {inatividade}s") from None
            except ConnectionResetError:
                continue  # Windows: ICMP de um envio nosso a uma porta fechada

            resultado = Packet.extract(dados)
            if resultado is None:
                st["pacotes_corrompidos"] += 1
                log.info("PACOTE CORROMPIDO detectado pelo checksum -> descartado")
                repetir_ack()
                continue

            tipo, seq, _, _, payload = resultado
            if tipo != DADOS:
                continue

            if seq != esperado:
                # GBN descarta qualquer pacote fora de ordem e repete o último ACK
                if seq > esperado:
                    st["pacotes_fora_de_ordem"] += 1
                    log.info("FORA DE ORDEM seq=%d (esperado %d) -> descartado, reenvia ACK %s",
                             seq, esperado, ultimo_ack)
                else:
                    st["pacotes_duplicados"] += 1
                    log.info("DUPLICADO seq=%d (esperado %d) -> descartado, reenvia ACK %s",
                             seq, esperado, ultimo_ack)
                repetir_ack()
                continue

            # pacote esperado e íntegro: entrega e confirma cumulativamente
            ultimo_ack = seq
            esperado += 1
            _enviar_ack(sock, origem, seq)
            if not payload:
                log.info("FIM recebido (seq=%d), ACK enviado", seq)
                break
            f.write(payload)
            st["bytes_recebidos"] += len(payload)
            st["pacotes_validos"] += 1
            log.debug("entregue seq=%d (%d bytes), ACK %d enviado", seq, len(payload), seq)

    # linger: continua respondendo ACK se o ACK do FIM se perdeu e o remetente retransmite
    ultimo_pacote = time.perf_counter()
    while True:
        restante = linger - (time.perf_counter() - ultimo_pacote)
        if restante <= 0:
            break
        sock.settimeout(restante)
        try:
            _, origem = sock.recvfrom(BUFFER)
        except (socket.timeout, ConnectionResetError):
            continue
        log.info("pacote repetido após o FIM -> reenvia ACK %d", ultimo_ack)
        _enviar_ack(sock, origem, ultimo_ack)
        ultimo_pacote = time.perf_counter()

    st["sha256"] = sha256_arquivo(saida)
    return st


def main():
    ap = argparse.ArgumentParser(description="Go-Back-N receptor (janela deslizante sobre UDP)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=5000)
    ap.add_argument("--saida", default="recebido.bin", help="arquivo de saída")
    ap.add_argument("--perda", type=float, default=0.0, help="prob. de perda dos ACKs")
    ap.add_argument("--corrupcao", type=float, default=0.0, help="prob. de corrupção dos ACKs")
    ap.add_argument("--atraso", type=float, default=0.0, help="atraso do canal (s)")
    ap.add_argument("--seed", type=int, default=None, help="semente do canal (reprodutível)")
    ap.add_argument("--inatividade", type=float, default=INATIVIDADE_PADRAO)
    ap.add_argument("--linger", type=float, default=LINGER_PADRAO)
    ap.add_argument("-v", "--verbose", action="store_true", help="mostra o log de eventos")
    a = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    sock = UnreliableSocket(loss=a.perda, corrupt=a.corrupcao, delay=a.atraso, seed=a.seed)
    sock.bind((a.host, a.porta))
    print(f"aguardando arquivo em {a.host}:{a.porta} ...")
    try:
        st = receber_arquivo(sock, a.saida, a.inatividade, a.linger)
    finally:
        sock.close()

    print(f"recebido: {st['bytes_recebidos']} bytes em '{a.saida}'")
    print(f"pacotes válidos={st['pacotes_validos']} corrompidos={st['pacotes_corrompidos']} "
          f"fora de ordem={st['pacotes_fora_de_ordem']} duplicados={st['pacotes_duplicados']}")
    print(f"canal (receptor, só ACKs): enviados={sock.enviados} perdidos={sock.perdidos} "
          f"corrompidos={sock.corrompidos}")
    print(f"sha256: {st['sha256']}")


if __name__ == "__main__":
    main()
