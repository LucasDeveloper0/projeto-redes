"""Go-Back-N: remetente (janela deslizante sobre UDP).

Conceitos da aula:
  * janela de tamanho N: até N pacotes enviados e ainda não confirmados;
  * base: seq do pacote mais antigo sem ACK; proximo: próximo seq a enviar;
  * ACK cumulativo: ack=k confirma todos os pacotes até k;
  * um único temporizador, associado ao pacote base;
  * no timeout, retransmite TODOS os pacotes da janela, a partir de base.

Uma thread só: o laço alterna entre encher a janela e esperar ACK até o prazo
do temporizador, então não é preciso travar (lock) nenhuma estrutura.
"""
import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m gbn.remetente" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402
# mesmos valores padrão do rdt3.0, para a comparação entre protocolos ser justa
from rdt30.remetente import BUFFER, MAX_TENTATIVAS, TAMANHO_PADRAO, TIMEOUT_PADRAO  # noqa: E402

log = logging.getLogger("gbn.tx")

JANELA_PADRAO = 8  # N: pacotes em trânsito ao mesmo tempo


def enviar_arquivo(sock, destino, caminho, janela=JANELA_PADRAO, timeout=TIMEOUT_PADRAO,
                   tamanho=TAMANHO_PADRAO, max_tentativas=MAX_TENTATIVAS):
    """Envia o arquivo com Go-Back-N e devolve as estatísticas da transferência."""
    st = {
        "retransmissoes": 0,
        "pacotes_enviados": 0,
        "acks_corrompidos": 0,
        "acks_duplicados": 0,
        "bytes_uteis": 0,
    }

    def transmitir(seq, retransmissao=False):
        sock.sendto(buffer[seq], destino)
        st["pacotes_enviados"] += 1
        if retransmissao:
            st["retransmissoes"] += 1
            log.info("RETRANSMISSÃO seq=%d", seq)
        else:
            log.debug("envio seq=%d", seq)

    buffer = {}        # seq -> pacote em bytes (só os da janela, ainda sem ACK)
    base = 0           # pacote mais antigo sem ACK
    proximo = 0        # próximo número de sequência a enviar
    seq_fim = None     # seq do pacote FIM (DADOS sem dados); None até o arquivo acabar
    prazo = None       # instante do timeout do pacote base (temporizador único)
    timeouts_seguidos = 0
    inicio = time.perf_counter()

    with open(caminho, "rb") as f:
        while seq_fim is None or base <= seq_fim:
            # 1) enche a janela: envia enquanto proximo < base + N
            while seq_fim is None and proximo < base + janela:
                chunk = f.read(tamanho)
                buffer[proximo] = Packet.make(DADOS, proximo, 0, chunk)
                if chunk:
                    st["bytes_uteis"] += len(chunk)
                else:
                    seq_fim = proximo  # chunk vazio = fim do arquivo: manda o FIM
                transmitir(proximo)
                if base == proximo:
                    prazo = time.perf_counter() + timeout  # janela estava vazia: liga o timer
                proximo += 1

            # 2) espera ACK até o prazo do temporizador
            restante = prazo - time.perf_counter()
            if restante > 0:
                sock.settimeout(restante)
                try:
                    dados, _ = sock.recvfrom(BUFFER)
                except socket.timeout:
                    continue  # recalcula o prazo; cai no timeout abaixo
                except ConnectionResetError:
                    continue  # Windows: ICMP "porta inalcançável" (receptor ainda não subiu)

                resultado = Packet.extract(dados)
                if resultado is None:
                    st["acks_corrompidos"] += 1
                    log.info("ACK CORROMPIDO detectado pelo checksum -> descartado")
                    continue
                tipo, _, ack, _, _ = resultado
                if tipo == ACK and base <= ack < proximo:
                    # ACK cumulativo: confirma tudo até ack, a janela desliza
                    log.debug("ACK %d (cumulativo): base %d -> %d", ack, base, ack + 1)
                    for s in range(base, ack + 1):
                        del buffer[s]
                    base = ack + 1
                    timeouts_seguidos = 0
                    # há pacotes em trânsito: reinicia o timer; senão, para
                    prazo = time.perf_counter() + timeout if base < proximo else None
                else:
                    st["acks_duplicados"] += 1
                    log.info("ACK %s duplicado/inesperado (base=%d) -> ignorado", ack, base)
                continue

            # 3) timeout: go back N, reenvia todos os pacotes da janela a partir de base
            timeouts_seguidos += 1
            if timeouts_seguidos > max_tentativas:
                raise ConnectionError(
                    f"sem progresso na base={base} após {max_tentativas} timeouts seguidos"
                )
            log.info("TIMEOUT base=%d -> reenvia %d..%d", base, base, proximo - 1)
            for seq in range(base, proximo):
                transmitir(seq, retransmissao=True)
            prazo = time.perf_counter() + timeout

    st["tempo_total"] = time.perf_counter() - inicio
    st["sha256"] = sha256_arquivo(caminho)
    return st


def main():
    ap = argparse.ArgumentParser(description="Go-Back-N remetente (janela deslizante sobre UDP)")
    ap.add_argument("arquivo", help="arquivo a enviar")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=5000)
    ap.add_argument("--janela", type=int, default=JANELA_PADRAO, help="tamanho N da janela")
    ap.add_argument("--perda", type=float, default=0.0, help="prob. de perda (0 a 1)")
    ap.add_argument("--corrupcao", type=float, default=0.0, help="prob. de corrupção (0 a 1)")
    ap.add_argument("--atraso", type=float, default=0.0, help="atraso do canal (s)")
    ap.add_argument("--seed", type=int, default=None, help="semente do canal (reprodutível)")
    ap.add_argument("--timeout", type=float, default=TIMEOUT_PADRAO, help="timeout (s)")
    ap.add_argument("--tamanho", type=int, default=TAMANHO_PADRAO, help="bytes por pacote")
    ap.add_argument("-v", "--verbose", action="store_true", help="mostra o log de eventos")
    a = ap.parse_args()
    if a.janela < 1:
        ap.error("--janela deve ser >= 1")

    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    sock = UnreliableSocket(loss=a.perda, corrupt=a.corrupcao, delay=a.atraso, seed=a.seed)
    try:
        st = enviar_arquivo(sock, (a.host, a.porta), a.arquivo, a.janela, a.timeout, a.tamanho)
    finally:
        sock.close()

    print(f"enviado: {st['bytes_uteis']} bytes em {st['tempo_total']:.3f}s (janela N={a.janela})")
    print(f"pacotes enviados={st['pacotes_enviados']} retransmissões={st['retransmissoes']} "
          f"acks corrompidos={st['acks_corrompidos']} acks duplicados={st['acks_duplicados']}")
    print(f"canal (remetente): enviados={sock.enviados} perdidos={sock.perdidos} "
          f"corrompidos={sock.corrompidos}")
    print(f"sha256: {st['sha256']}")


if __name__ == "__main__":
    main()
