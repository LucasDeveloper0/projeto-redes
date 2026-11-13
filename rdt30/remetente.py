import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m rdt30.remetente" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402

log = logging.getLogger("rdt30.tx")

BUFFER = 2048
TAMANHO_PADRAO = 1024   # bytes de dados por pacote
TIMEOUT_PADRAO = 0.1    # segundos
MAX_TENTATIVAS = 100    # timeouts seguidos no mesmo pacote antes de desistir


def _enviar_e_esperar_ack(sock, destino, pacote, seq, timeout, max_tentativas, st):
    tentativas = 0
    while True:
        sock.sendto(pacote, destino)
        st["pacotes_enviados"] += 1
        if tentativas > 0:
            st["retransmissoes"] += 1
            log.info("RETRANSMISSÃO seq=%d (tentativa %d)", seq, tentativas + 1)
        else:
            log.debug("envio seq=%d", seq)

        prazo = time.perf_counter() + timeout  # temporizador do pacote
        while True:
            restante = prazo - time.perf_counter()
            if restante <= 0:
                log.info("TIMEOUT seq=%d", seq)
                break
            sock.settimeout(restante)
            try:
                dados, _ = sock.recvfrom(BUFFER)
            except socket.timeout:
                continue  # recalcula o prazo; cai no timeout acima
            except ConnectionResetError:
                continue  # Windows: ICMP "porta inalcançável" (receptor ainda não subiu)

            resultado = Packet.extract(dados)
            if resultado is None:
                st["acks_corrompidos"] += 1
                log.info("ACK CORROMPIDO detectado pelo checksum -> descartado")
                continue
            tipo, _, ack, _, _ = resultado
            if tipo == ACK and ack == seq:
                log.debug("ACK %d recebido", ack)
                return
            st["acks_duplicados"] += 1
            log.info("ACK %s inesperado (esperado %d) -> ignorado", ack, seq)

        tentativas += 1
        if tentativas > max_tentativas:
            raise ConnectionError(
                f"sem ACK para seq={seq} após {max_tentativas} retransmissões"
            )


def enviar_arquivo(sock, destino, caminho, timeout=TIMEOUT_PADRAO,
                   tamanho=TAMANHO_PADRAO, max_tentativas=MAX_TENTATIVAS):
    
    st = {
        "retransmissoes": 0,
        "pacotes_enviados": 0,
        "acks_corrompidos": 0,
        "acks_duplicados": 0,
        "bytes_uteis": 0,
    }
    seq = 0
    inicio = time.perf_counter()
    with open(caminho, "rb") as f:
        while True:
            chunk = f.read(tamanho)
            # chunk vazio = fim do arquivo: manda o pacote FIM (DADOS sem dados)
            pacote = Packet.make(DADOS, seq, 0, chunk)
            _enviar_e_esperar_ack(sock, destino, pacote, seq, timeout, max_tentativas, st)
            if not chunk:
                break
            st["bytes_uteis"] += len(chunk)
            seq ^= 1  # alterna 0/1
    st["tempo_total"] = time.perf_counter() - inicio
    st["sha256"] = sha256_arquivo(caminho)
    return st


def main():
    ap = argparse.ArgumentParser(description="rdt3.0 remetente (pare-e-espera sobre UDP)")
    ap.add_argument("arquivo", help="arquivo a enviar")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=5000)
    ap.add_argument("--perda", type=float, default=0.0, help="prob. de perda (0 a 1)")
    ap.add_argument("--corrupcao", type=float, default=0.0, help="prob. de corrupção (0 a 1)")
    ap.add_argument("--atraso", type=float, default=0.0, help="atraso do canal (s)")
    ap.add_argument("--seed", type=int, default=None, help="semente do canal (reprodutível)")
    ap.add_argument("--timeout", type=float, default=TIMEOUT_PADRAO, help="timeout (s)")
    ap.add_argument("--tamanho", type=int, default=TAMANHO_PADRAO, help="bytes por pacote")
    ap.add_argument("-v", "--verbose", action="store_true", help="mostra o log de eventos")
    a = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    sock = UnreliableSocket(loss=a.perda, corrupt=a.corrupcao, delay=a.atraso, seed=a.seed)
    try:
        st = enviar_arquivo(sock, (a.host, a.porta), a.arquivo, a.timeout, a.tamanho)
    finally:
        sock.close()

    print(f"enviado: {st['bytes_uteis']} bytes em {st['tempo_total']:.3f}s")
    print(f"pacotes enviados={st['pacotes_enviados']} retransmissões={st['retransmissoes']} "
          f"acks corrompidos={st['acks_corrompidos']} acks duplicados={st['acks_duplicados']}")
    print(f"canal (remetente): enviados={sock.enviados} perdidos={sock.perdidos} "
          f"corrompidos={sock.corrompidos}")
    print(f"sha256: {st['sha256']}")


if __name__ == "__main__":
    main()
