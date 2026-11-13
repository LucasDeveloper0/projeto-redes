import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m rdt30.receptor" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402

log = logging.getLogger("rdt30.rx")

BUFFER = 2048
INATIVIDADE_PADRAO = 30.0  # s sem receber nada antes de desistir
LINGER_PADRAO = 1.0        # s de silêncio após o FIM antes de encerrar


def _enviar_ack(sock, destino, ack):
    # ACK: seq_num não é usado; o número confirmado vai em ack_num
    sock.sendto(Packet.make(ACK, 0, ack), destino)


def receber_arquivo(sock, saida, inatividade=INATIVIDADE_PADRAO, linger=LINGER_PADRAO):
    st = {
        "bytes_recebidos": 0,
        "pacotes_validos": 0,
        "pacotes_corrompidos": 0,
        "pacotes_duplicados": 0,
    }
    esperado = 0     # FSM do receptor: "espera 0" / "espera 1"
    ultimo_ack = 1   # ACK do último pacote em ordem (1 = nada entregue ainda)
    origem = None    # endereço do remetente, aprendido no primeiro pacote

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
                # corrompido: descarta e repete o ACK anterior
                st["pacotes_corrompidos"] += 1
                log.info("PACOTE CORROMPIDO detectado pelo checksum -> descartado, reenvia ACK %d",
                         ultimo_ack)
                _enviar_ack(sock, origem, ultimo_ack)
                continue

            tipo, seq, _, _, payload = resultado
            if tipo != DADOS:
                continue

            if seq != esperado:
                # duplicado: o ACK anterior se perdeu; reenvia sem entregar de novo
                st["pacotes_duplicados"] += 1
                log.info("DUPLICADO seq=%d (esperado %d) -> descartado, reenvia ACK %d",
                         seq, esperado, ultimo_ack)
                _enviar_ack(sock, origem, ultimo_ack)
                continue

            # pacote esperado e íntegro
            _enviar_ack(sock, origem, seq)
            ultimo_ack = seq
            if not payload:
                log.info("FIM recebido (seq=%d), ACK enviado", seq)
                break
            f.write(payload)
            st["bytes_recebidos"] += len(payload)
            st["pacotes_validos"] += 1
            log.debug("entregue seq=%d (%d bytes), ACK %d enviado", seq, len(payload), seq)
            esperado ^= 1

    # linger: continua respondendo ACK a retransmissões do FIM
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
        log.info("FIM repetido -> reenvia ACK %d", ultimo_ack)
        _enviar_ack(sock, origem, ultimo_ack)
        ultimo_pacote = time.perf_counter()

    st["sha256"] = sha256_arquivo(saida)
    return st


def main():
    ap = argparse.ArgumentParser(description="rdt3.0 receptor (pare-e-espera sobre UDP)")
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
          f"duplicados={st['pacotes_duplicados']}")
    print(f"canal (receptor, só ACKs): enviados={sock.enviados} perdidos={sock.perdidos} "
          f"corrompidos={sock.corrompidos}")
    print(f"sha256: {st['sha256']}")


if __name__ == "__main__":
    main()
