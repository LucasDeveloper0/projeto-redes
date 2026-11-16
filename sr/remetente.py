"""Repetição Seletiva (SR) - REMETENTE (janela deslizante sobre UDP).

Ideia do protocolo (Kurose & Ross, cap. 3):
  1. envia até N pacotes sem esperar ACK (a JANELA): base <= seq < base + N;
  2. cada pacote tem o SEU PRÓPRIO temporizador (dicionário {seq: prazo});
  3. ACK individual: ack == k confirma SÓ o pacote k (não é cumulativo como no GBN);
  4. a janela desliza quando os primeiros pacotes dela estão todos confirmados;
  5. timeout de um pacote -> RETRANSMITE SÓ aquele pacote, não a janela inteira.
O receptor guarda os pacotes que chegam fora de ordem (ver sr/receptor.py), então
cada perda custa um único reenvio.

Uma thread só: o laço alterna entre encher a janela e esperar ACK até o MENOR prazo
entre os temporizadores, então não é preciso travar (lock) nenhuma estrutura.
FSM correspondente: graficos/fsm_sr_remetente.png e relatorio/fsm_sr.md.
"""
import argparse
import logging
import socket
import sys
import time
from pathlib import Path

# permite rodar tanto com "python -m sr.remetente" quanto direto pelo arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.packet import ACK, DADOS, Packet  # noqa: E402
# mesmos valores padrão do rdt3.0, para a comparação entre protocolos ser justa
from rdt30.remetente import BUFFER, MAX_TENTATIVAS, TAMANHO_PADRAO, TIMEOUT_PADRAO  # noqa: E402

# Logger do remetente. Com -v mostra cada evento (ENVIA, TIMEOUT, RETRANSMISSÃO ...)
log = logging.getLogger("sr.tx")

JANELA_PADRAO = 8  # N: pacotes em trânsito ao mesmo tempo (o mesmo do GBN)


def enviar_arquivo(sock, destino, caminho, janela=JANELA_PADRAO, timeout=TIMEOUT_PADRAO,
                   tamanho=TAMANHO_PADRAO, max_tentativas=MAX_TENTATIVAS):
    """Envia o arquivo com Repetição Seletiva e devolve as estatísticas da transferência.

    Métricas: retransmissoes, pacotes_enviados, acks_corrompidos, acks_duplicados,
    bytes_uteis (só dados, sem cabeçalho), tempo_total e sha256 do arquivo enviado
    (as mesmas chaves do rdt3.0 e do GBN).
    """
    st = {
        "retransmissoes": 0,
        "pacotes_enviados": 0,
        "acks_corrompidos": 0,
        "acks_duplicados": 0,
        "bytes_uteis": 0,
    }

    buffer = {}         # seq -> pacote em bytes (os da janela, até a base passar por eles)
    prazos = {}         # seq -> instante do timeout: UM TEMPORIZADOR POR PACOTE sem ACK
    tentativas = {}     # seq -> timeouts já sofridos por aquele pacote
    confirmados = set() # seqs que já receberam ACK, mas ainda esperam a base chegar neles
    base = 0            # pacote mais antigo sem ACK (início da janela)
    proximo = 0         # próximo número de sequência a enviar
    seq_fim = None      # seq do pacote FIM (DADOS sem dados); None até o arquivo acabar

    def transmitir(seq, retransmissao=False):
        """Envia o pacote `seq` (que já está no buffer) e (re)liga o temporizador dele."""
        sock.sendto(buffer[seq], destino)
        st["pacotes_enviados"] += 1
        prazos[seq] = time.perf_counter() + timeout  # temporizador SÓ deste pacote
        if retransmissao:
            st["retransmissoes"] += 1
            log.info("RETRANSMISSÃO seq=%d (tentativa %d)", seq, tentativas[seq] + 1)
        else:
            log.debug("ENVIA seq=%d", seq)

    inicio = time.perf_counter()

    with open(caminho, "rb") as f:
        # termina quando a base passa do FIM, ou seja, quando o FIM foi confirmado
        while seq_fim is None or base <= seq_fim:
            # 1) enche a janela: envia enquanto proximo < base + N
            while seq_fim is None and proximo < base + janela:
                chunk = f.read(tamanho)
                buffer[proximo] = Packet.make(DADOS, proximo, 0, chunk)
                tentativas[proximo] = 0
                if chunk:
                    st["bytes_uteis"] += len(chunk)
                else:
                    seq_fim = proximo  # chunk vazio = fim do arquivo: manda o FIM
                transmitir(proximo)
                proximo += 1

            # 2) espera ACK até o MENOR prazo entre os temporizadores ligados.
            #    (Sempre há pelo menos um: o pacote base nunca está confirmado aqui.)
            restante = min(prazos.values()) - time.perf_counter()
            if restante > 0:
                sock.settimeout(restante)  # recvfrom espera no máximo o tempo que resta
                try:
                    dados, _ = sock.recvfrom(BUFFER)
                except socket.timeout:
                    continue  # recalcula o prazo; cai no timeout lá embaixo
                except ConnectionResetError:
                    continue  # Windows: ICMP "porta inalcançável" (receptor ainda não subiu)

                # Packet.extract confere o checksum; devolve None se o ACK chegou corrompido
                resultado = Packet.extract(dados)
                if resultado is None:
                    st["acks_corrompidos"] += 1
                    log.info("DESCARTA ACK corrompido (checksum inválido)")
                    continue  # não faz nada: o temporizador do pacote cuida da recuperação
                tipo, _, ack, _, _ = resultado
                if tipo != ACK or not (base <= ack < proximo) or ack in confirmados:
                    # ACK repetido (já confirmado ou abaixo da base) ou fora da janela:
                    # não muda nada na janela
                    st["acks_duplicados"] += 1
                    log.info("DESCARTA ACK %s duplicado/fora da janela (base=%d)", ack, base)
                    continue

                # ACK individual: marca SÓ este pacote e desliga o temporizador dele
                confirmados.add(ack)
                del prazos[ack]
                log.debug("ACK %d recebido (individual)", ack)

                # a janela desliza enquanto os primeiros pacotes dela estão confirmados.
                # Ex.: base=3 e confirmados={4, 5}: o ACK 3 faz a base pular para 6.
                base_antiga = base
                while base in confirmados:
                    confirmados.remove(base)
                    del buffer[base]      # não precisa mais guardar: nunca será reenviado
                    del tentativas[base]
                    base += 1
                if base != base_antiga:
                    log.debug("janela desliza: base %d -> %d", base_antiga, base)
                continue  # volta ao passo 1: a janela pode ter aberto espaço

            # 3) timeout: reenvia SÓ os pacotes cujo temporizador venceu
            #    (no GBN, aqui seria reenviada a janela inteira, de base a proximo - 1)
            agora = time.perf_counter()
            for seq in sorted(s for s, p in prazos.items() if p <= agora):
                tentativas[seq] += 1
                if tentativas[seq] > max_tentativas:
                    # o mesmo pacote estourou o tempo vezes demais: o receptor sumiu
                    raise ConnectionError(
                        f"sem ACK para seq={seq} após {max_tentativas} retransmissões"
                    )
                log.info("TIMEOUT seq=%d", seq)
                transmitir(seq, retransmissao=True)  # religa só o temporizador deste

    st["tempo_total"] = time.perf_counter() - inicio
    st["sha256"] = sha256_arquivo(caminho)  # para comparar com o hash do receptor
    return st


def main():
    """Interface de linha de comando: monta o canal e chama enviar_arquivo."""
    ap = argparse.ArgumentParser(description="Repetição Seletiva remetente (janela deslizante sobre UDP)")
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

    # -v liga o nível DEBUG (mostra também cada ENVIA e cada ACK); sem -v, só avisos
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # canal não confiável: perde e corrompe os pacotes de DADOS que o remetente envia
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