import argparse
import logging
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402
from rdt30.receptor import BUFFER, INATIVIDADE_PADRAO, LINGER_PADRAO  # noqa: E402
from sr.remetente import JANELA_PADRAO  # noqa: E402

log = logging.getLogger("sr.rx")


def _enviar_ack(sock, destino, ack):
    sock.sendto(Packet.make(ACK, 0, ack), destino)


def receber_arquivo(sock, saida, inatividade=INATIVIDADE_PADRAO, linger=LINGER_PADRAO,
                    janela=JANELA_PADRAO):
    """Recebe o arquivo com Repetição Seletiva e devolve as estatísticas da recepção.

    janela: tamanho N da janela de recepção. Use o mesmo N do remetente; se for
    menor, o protocolo continua correto, mas pacotes acima da janela são ignorados
    e só chegam depois, por retransmissão.
    """
    st = {
        "bytes_recebidos": 0,
        "pacotes_validos": 0,        
        "pacotes_corrompidos": 0,
        "pacotes_fora_de_ordem": 0,  
        "pacotes_duplicados": 0,     
        "pacotes_fora_da_janela": 0, 
    }
    rcv_base = 0     
    guardados = {}   
    seq_fim = None   
    origem = None    

    with open(saida, "wb") as f:
        sock.settimeout(inatividade)
        while seq_fim is None or rcv_base <= seq_fim:
            try:
                dados, origem = sock.recvfrom(BUFFER)
            except socket.timeout:
                raise TimeoutError(f"nenhum pacote recebido em {inatividade}s") from None
            except ConnectionResetError:
                continue  # Windows: ICMP de um envio nosso a uma porta fechada

            resultado = Packet.extract(dados)
            if resultado is None:
                st["pacotes_corrompidos"] += 1
                log.info("DESCARTA pacote corrompido (checksum inválido), sem ACK")
                continue

            tipo, seq, _, _, payload = resultado
            if tipo != DADOS:
                continue

            if seq >= rcv_base + janela:
                st["pacotes_fora_da_janela"] += 1
                log.info("DESCARTA seq=%d fora da janela [%d, %d], sem ACK",
                         seq, rcv_base, rcv_base + janela - 1)
                continue

            _enviar_ack(sock, origem, seq)

            if seq < rcv_base or seq in guardados:
                st["pacotes_duplicados"] += 1
                log.info("DUPLICADO seq=%d (rcv_base=%d) -> DESCARTA, reenvia ACK %d",
                         seq, rcv_base, seq)
                continue

            guardados[seq] = payload
            if not payload:
                seq_fim = seq
                log.info("FIM recebido (seq=%d), ACK enviado", seq)
            if seq != rcv_base:
                st["pacotes_fora_de_ordem"] += 1
                log.info("FORA DE ORDEM seq=%d (rcv_base=%d) -> guardado no buffer, ACK %d",
                         seq, rcv_base, seq)
                continue

            log.debug("recebido seq=%d, ACK %d enviado", seq, seq)
            while rcv_base in guardados:
                dados_entrega = guardados.pop(rcv_base)
                if dados_entrega:
                    f.write(dados_entrega)
                    st["bytes_recebidos"] += len(dados_entrega)
                    st["pacotes_validos"] += 1
                    log.debug("entregue seq=%d (%d bytes)", rcv_base, len(dados_entrega))
                rcv_base += 1

    ultimo_pacote = time.perf_counter()
    while True:
        restante = linger - (time.perf_counter() - ultimo_pacote)
        if restante <= 0:
            break
        sock.settimeout(restante)
        try:
            dados, origem = sock.recvfrom(BUFFER)
        except (socket.timeout, ConnectionResetError):
            continue
        ultimo_pacote = time.perf_counter()
        resultado = Packet.extract(dados)
        if resultado is None:
            st["pacotes_corrompidos"] += 1
            log.info("DESCARTA pacote corrompido (checksum inválido), sem ACK")
            continue
        tipo, seq, _, _, _ = resultado
        if tipo == DADOS and seq <= seq_fim:
            st["pacotes_duplicados"] += 1
            log.info("pacote repetido após o FIM seq=%d -> reenvia ACK %d", seq, seq)
            _enviar_ack(sock, origem, seq)

    st["sha256"] = sha256_arquivo(saida)
    return st


def main():
    ap = argparse.ArgumentParser(description="Repetição Seletiva receptor (janela deslizante sobre UDP)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=5000)
    ap.add_argument("--saida", default="recebido.bin", help="arquivo de saída")
    ap.add_argument("--janela", type=int, default=JANELA_PADRAO,
                    help="tamanho N da janela de recepção (use o mesmo do remetente)")
    ap.add_argument("--perda", type=float, default=0.0, help="prob. de perda dos ACKs")
    ap.add_argument("--corrupcao", type=float, default=0.0, help="prob. de corrupção dos ACKs")
    ap.add_argument("--atraso", type=float, default=0.0, help="atraso do canal (s)")
    ap.add_argument("--seed", type=int, default=None, help="semente do canal (reprodutível)")
    ap.add_argument("--inatividade", type=float, default=INATIVIDADE_PADRAO)
    ap.add_argument("--linger", type=float, default=LINGER_PADRAO)
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
    sock.bind((a.host, a.porta))
    print(f"aguardando arquivo em {a.host}:{a.porta} (janela N={a.janela}) ...")
    try:
        st = receber_arquivo(sock, a.saida, a.inatividade, a.linger, a.janela)
    finally:
        sock.close()

    print(f"recebido: {st['bytes_recebidos']} bytes em '{a.saida}'")
    print(f"pacotes válidos={st['pacotes_validos']} corrompidos={st['pacotes_corrompidos']} "
          f"fora de ordem={st['pacotes_fora_de_ordem']} duplicados={st['pacotes_duplicados']} "
          f"fora da janela={st['pacotes_fora_da_janela']}")
    print(f"canal (receptor, só ACKs): enviados={sock.enviados} perdidos={sock.perdidos} "
          f"corrompidos={sock.corrompidos}")
    print(f"sha256: {st['sha256']}")


if __name__ == "__main__":
    main()
