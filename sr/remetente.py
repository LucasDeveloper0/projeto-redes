import argparse
import logging
import socket
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  
from common.channel import UnreliableSocket  
from common.packet import ACK, DADOS, Packet  
from rdt30.remetente import BUFFER, MAX_TENTATIVAS, TAMANHO_PADRAO, TIMEOUT_PADRAO  

log = logging.getLogger("sr.tx")

JANELA_PADRAO = 8  


def enviar_arquivo(sock, destino, caminho, janela=JANELA_PADRAO, timeout=TIMEOUT_PADRAO,
                   tamanho=TAMANHO_PADRAO, max_tentativas=MAX_TENTATIVAS):
    """Envia o arquivo com Repetição Seletiva e devolve as estatísticas da transferência."""
    st = {
        "retransmissoes": 0,
        "pacotes_enviados": 0,
        "acks_corrompidos": 0,
        "acks_duplicados": 0,
        "bytes_uteis": 0,
    }

    buffer = {}         
    prazos = {}         
    tentativas = {}     
    confirmados = set()
    base = 0            
    proximo = 0         
    seq_fim = None      

    def transmitir(seq, retransmissao=False):
        sock.sendto(buffer[seq], destino)
        st["pacotes_enviados"] += 1
        prazos[seq] = time.perf_counter() + timeout  
        if retransmissao:
            st["retransmissoes"] += 1
            log.info("RETRANSMISSÃO seq=%d (tentativa %d)", seq, tentativas[seq] + 1)
        else:
            log.debug("ENVIA seq=%d", seq)

    inicio = time.perf_counter()

    with open(caminho, "rb") as f:
        while seq_fim is None or base <= seq_fim:
            
            while seq_fim is None and proximo < base + janela:
                chunk = f.read(tamanho)
                buffer[proximo] = Packet.make(DADOS, proximo, 0, chunk)
                tentativas[proximo] = 0
                if chunk:
                    st["bytes_uteis"] += len(chunk)
                else:
                    seq_fim = proximo 
                transmitir(proximo)
                proximo += 1

            
            restante = min(prazos.values()) - time.perf_counter()
            if restante > 0:
                sock.settimeout(restante)
                try:
                    dados, _ = sock.recvfrom(BUFFER)
                except socket.timeout:
                    continue 
                except ConnectionResetError:
                    continue 

                resultado = Packet.extract(dados)
                if resultado is None:
                    st["acks_corrompidos"] += 1
                    log.info("DESCARTA ACK corrompido (checksum inválido)")
                    continue
                tipo, _, ack, _, _ = resultado
                if tipo != ACK or not (base <= ack < proximo) or ack in confirmados:
                    
                    st["acks_duplicados"] += 1
                    log.info("DESCARTA ACK %s duplicado/fora da janela (base=%d)", ack, base)
                    continue

                
                confirmados.add(ack)
                del prazos[ack]
                log.debug("ACK %d recebido (individual)", ack)

                
                base_antiga = base
                while base in confirmados:
                    confirmados.remove(base)
                    del buffer[base]
                    del tentativas[base]
                    base += 1
                if base != base_antiga:
                    log.debug("janela desliza: base %d -> %d", base_antiga, base)
                continue

           
            agora = time.perf_counter()
            for seq in sorted(s for s, p in prazos.items() if p <= agora):
                tentativas[seq] += 1
                if tentativas[seq] > max_tentativas:
                    raise ConnectionError(
                        f"sem ACK para seq={seq} após {max_tentativas} retransmissões"
                    )
                log.info("TIMEOUT seq=%d", seq)
                transmitir(seq, retransmissao=True)

    st["tempo_total"] = time.perf_counter() - inicio
    st["sha256"] = sha256_arquivo(caminho)
    return st


def main():
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
