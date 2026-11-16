"""Repetição Seletiva (SR) - RECEPTOR.

Ideia do protocolo (Kurose & Ross, cap. 3):
  * o receptor também tem uma JANELA: [rcv_base, rcv_base + N - 1], onde rcv_base
    é o menor número de sequência ainda não entregue ao arquivo;
  * todo pacote íntegro dentro da janela recebe ACK INDIVIDUAL (ack = seq dele);
  * pacote fora de ordem: vai para o BUFFER; quando o buraco fecha (chega rcv_base),
    entrega em ordem tudo o que estiver contíguo;
  * pacote já entregue (seq < rcv_base, DUPLICADO): o ACK dele se perdeu, então
    reenvia o ACK, sem entregar os dados de novo;
  * pacote acima da janela (seq >= rcv_base + N): ignorado, sem ACK;
  * pacote corrompido: descartado, sem ACK. Na SR não existe "último ACK" para
    repetir (como no GBN); o remetente reenvia aquele pacote quando o timer dele vence.
FSM correspondente: graficos/fsm_sr_receptor.png e relatorio/fsm_sr.md.
"""
import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m sr.receptor" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402
# mesmos valores padrão do rdt3.0 (inatividade e linger) e a mesma janela do remetente
from rdt30.receptor import BUFFER, INATIVIDADE_PADRAO, LINGER_PADRAO  # noqa: E402
from sr.remetente import JANELA_PADRAO  # noqa: E402

# Logger do receptor. Com -v mostra cada evento (FORA DE ORDEM, DUPLICADO, DESCARTA ...)
log = logging.getLogger("sr.rx")


def _enviar_ack(sock, destino, ack):
    """Envia o ACK individual do pacote `ack`.

    O número confirmado vai no campo ack_num; o seq_num do ACK não é usado (fica 0).
    """
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
        "pacotes_validos": 0,        # entregues ao arquivo (em ordem, sem repetição)
        "pacotes_corrompidos": 0,    # descartados pelo checksum
        "pacotes_fora_de_ordem": 0,  # chegaram antes de um buraco e foram para o buffer
        "pacotes_duplicados": 0,     # já entregues ou já no buffer: só repete o ACK
        "pacotes_fora_da_janela": 0, # acima de rcv_base + N - 1: ignorados
    }
    rcv_base = 0     # menor seq ainda não entregue (início da janela de recepção)
    guardados = {}   # BUFFER: seq -> dados dos pacotes que esperam o buraco fechar
    seq_fim = None   # seq do FIM, conhecido quando ele chega (mesmo fora de ordem)
    origem = None    # endereço do remetente, aprendido no primeiro pacote

    with open(saida, "wb") as f:
        sock.settimeout(inatividade)  # desiste se o remetente sumir por muito tempo
        # termina quando o FIM foi entregue, ou seja, quando rcv_base passou dele
        while seq_fim is None or rcv_base <= seq_fim:
            try:
                dados, origem = sock.recvfrom(BUFFER)
            except socket.timeout:
                raise TimeoutError(f"nenhum pacote recebido em {inatividade}s") from None
            except ConnectionResetError:
                continue  # Windows: ICMP de um envio nosso a uma porta fechada

            # Packet.extract confere o checksum; devolve None se o pacote chegou corrompido
            resultado = Packet.extract(dados)
            if resultado is None:
                st["pacotes_corrompidos"] += 1
                log.info("DESCARTA pacote corrompido (checksum inválido), sem ACK")
                continue  # sem ACK: o remetente recupera pelo temporizador do pacote

            tipo, seq, _, _, payload = resultado
            if tipo != DADOS:
                continue  # o receptor só espera DADOS

            # acima da janela: não cabe no buffer. Ignora sem ACK; o pacote volta depois.
            if seq >= rcv_base + janela:
                st["pacotes_fora_da_janela"] += 1
                log.info("DESCARTA seq=%d fora da janela [%d, %d], sem ACK",
                         seq, rcv_base, rcv_base + janela - 1)
                continue

            # daqui para baixo o pacote é íntegro e está na janela ou abaixo dela:
            # SEMPRE recebe o ACK individual (inclusive os duplicados)
            _enviar_ack(sock, origem, seq)

            # duplicado: já entregue (abaixo da janela) ou já guardado no buffer.
            # O ACK anterior se perdeu; o ACK acima resolve, e os dados são descartados.
            if seq < rcv_base or seq in guardados:
                st["pacotes_duplicados"] += 1
                log.info("DUPLICADO seq=%d (rcv_base=%d) -> DESCARTA, reenvia ACK %d",
                         seq, rcv_base, seq)
                continue

            # pacote novo dentro da janela: guarda no buffer
            guardados[seq] = payload
            if not payload:
                seq_fim = seq  # payload vazio = FIM (pode chegar fora de ordem também)
                log.info("FIM recebido (seq=%d), ACK enviado", seq)
            if seq != rcv_base:
                # chegou antes de um buraco: fica no buffer esperando o rcv_base chegar
                # (no GBN, este pacote seria descartado)
                st["pacotes_fora_de_ordem"] += 1
                log.info("FORA DE ORDEM seq=%d (rcv_base=%d) -> guardado no buffer, ACK %d",
                         seq, rcv_base, seq)
                continue

            # seq == rcv_base: o buraco fechou. Entrega em ordem tudo o que estiver
            # contíguo no buffer. Ex.: rcv_base=3 e guardados={3, 4, 5, 7}: entrega
            # 3, 4 e 5 e para no buraco do 6 (rcv_base passa a ser 6).
            log.debug("recebido seq=%d, ACK %d enviado", seq, seq)
            while rcv_base in guardados:
                dados_entrega = guardados.pop(rcv_base)
                if dados_entrega:  # o FIM não tem dados: só avança o rcv_base
                    f.write(dados_entrega)
                    st["bytes_recebidos"] += len(dados_entrega)
                    st["pacotes_validos"] += 1
                    log.debug("entregue seq=%d (%d bytes)", rcv_base, len(dados_entrega))
                rcv_base += 1  # a janela de recepção desliza

    # linger: o arquivo está completo, mas o remetente pode ainda estar sem o ACK de
    # algum pacote da última janela (inclusive o do FIM). Por um tempo, cada repetição
    # recebe de novo o ACK dela. O prazo recomeça a cada pacote que chega.
    ultimo_pacote = time.perf_counter()
    while True:
        restante = linger - (time.perf_counter() - ultimo_pacote)
        if restante <= 0:
            break  # ficou `linger` segundos sem receber nada: o remetente terminou
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
            # pacote que já foi entregue: só repete o ACK individual dele
            st["pacotes_duplicados"] += 1
            log.info("pacote repetido após o FIM seq=%d -> reenvia ACK %d", seq, seq)
            _enviar_ack(sock, origem, seq)

    st["sha256"] = sha256_arquivo(saida)  # para comparar com o hash do remetente
    return st


def main():
    """Interface de linha de comando: abre a porta e chama receber_arquivo."""
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

    # -v liga o nível DEBUG (mostra também cada entrega); sem -v, só avisos
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # canal não confiável do lado do receptor: perde e corrompe os ACKs que ele envia
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