import argparse
import random
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.enlace import EnlaceSocket  # noqa: E402
from common.metricas import registrar  # noqa: E402
from common.packet import Packet  # noqa: E402
import gbn.receptor as gbn_rx  # noqa: E402
import gbn.remetente as gbn_tx  # noqa: E402
import rdt30.receptor as rdt_rx  # noqa: E402
import rdt30.remetente as rdt_tx  # noqa: E402
import sr.receptor as sr_rx  # noqa: E402
import sr.remetente as sr_tx  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA_PADRAO = RAIZ / "graficos" / "experimentos.jsonl"
TAMANHO_DADOS = 1024  # bytes de dados por pacote (padrão dos três remetentes)
FOLGA_TIMEOUT = 0.05  # s somados ao timeout


def rodar(protocolo, janela, arquivo, saida, perda, atraso, taxa_bps, seed):
    """Uma transferência completa. Devolve (stats_remetente, timeout_usado)."""
    tam_pacote = (TAMANHO_DADOS + Packet.HEADER_SIZE) * 8
    # RTT + tempo de a janela inteira sair do enlace + folga
    timeout = 2 * atraso + janela * tam_pacote / taxa_bps + FOLGA_TIMEOUT
    linger = max(0.3, 1.5 * timeout)

    rx = EnlaceSocket(loss=perda, atraso=atraso, taxa_bps=taxa_bps, seed=seed + 1)
    rx.bind(("127.0.0.1", 0))
    destino = rx.sock.getsockname()
    tx = EnlaceSocket(loss=perda, atraso=atraso, taxa_bps=taxa_bps, seed=seed)

    resultado = {}

    def lado_receptor():
        try:
            if protocolo == "rdt30":
                rdt_rx.receber_arquivo(rx, saida, inatividade=30.0, linger=linger)
            elif protocolo == "gbn":
                gbn_rx.receber_arquivo(rx, saida, inatividade=30.0, linger=linger)
            else:
                sr_rx.receber_arquivo(rx, saida, inatividade=30.0, linger=linger, janela=janela)
        except Exception as e:  # noqa: BLE001 - repassa para a thread principal
            resultado["erro"] = e

    t = threading.Thread(target=lado_receptor, daemon=True)
    t.start()
    try:
        if protocolo == "rdt30":
            st = rdt_tx.enviar_arquivo(tx, destino, arquivo, timeout=timeout)
        elif protocolo == "gbn":
            st = gbn_tx.enviar_arquivo(tx, destino, arquivo, janela=janela, timeout=timeout)
        else:
            st = sr_tx.enviar_arquivo(tx, destino, arquivo, janela=janela, timeout=timeout)
    finally:
        t.join(timeout=60)
        tx.close()
        rx.close()
    if "erro" in resultado:
        raise resultado["erro"]
    return st, timeout


def main():
    ap = argparse.ArgumentParser(description="Experimentos de utilização do canal")
    ap.add_argument("--kb", type=int, default=100, help="tamanho do arquivo (KB)")
    ap.add_argument("--janelas", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32],
                    help="tamanhos de janela N para GBN e SR")
    ap.add_argument("--perdas", type=float, nargs="+", default=[0.0, 0.05],
                    help="probabilidades de perda do canal")
    ap.add_argument("--atraso", type=float, default=0.02,
                    help="propagação de uma direção, em s (RTT = 2x)")
    ap.add_argument("--taxa-mbps", type=float, default=1.0, help="taxa do enlace (Mbit/s)")
    ap.add_argument("--repeticoes", type=int, default=3,
                    help="repetições por ponto (sementes diferentes)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--saida", default=str(SAIDA_PADRAO), help="arquivo .jsonl de saída")
    ap.add_argument("--acrescentar", action="store_true",
                    help="não apaga o .jsonl existente")
    ap.add_argument("--rapido", action="store_true", help="arquivo de 30 KB, só para conferir")
    a = ap.parse_args()
    if a.rapido:
        a.kb = 30

    taxa_bps = a.taxa_mbps * 1e6
    destino_jsonl = Path(a.saida)
    if destino_jsonl.exists() and not a.acrescentar:
        destino_jsonl.unlink()  # evita misturar execuções diferentes no gráfico

    # (protocolo, janela): rdt3.0 é sempre N=1; GBN e SR variam
    execucoes = [("rdt30", 1)] + [(p, n) for p in ("gbn", "sr") for n in a.janelas]
    total = len(execucoes) * len(a.perdas) * a.repeticoes
    falhas = feitas = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        origem = tmp / "teste.bin"
        origem.write_bytes(random.Random(a.seed).randbytes(a.kb * 1024))
        hash_origem = sha256_arquivo(origem)
        rtt_ms = 2 * a.atraso * 1000
        print(f"arquivo: {a.kb} KB | taxa {a.taxa_mbps} Mbit/s | RTT {rtt_ms:.0f} ms | "
              f"perdas {a.perdas} | janelas {a.janelas} | {a.repeticoes} repetição(ões)\n")
        print(f"{'#':>8}  {'protocolo':<9}{'N':>3}{'perda':>7}{'hash':>7}{'tempo(s)':>10}"
              f"{'retrans.':>10}{'util.':>8}")
        print("-" * 64)

        for perda in a.perdas:
            for protocolo, janela in execucoes:
                for rep in range(a.repeticoes):
                    feitas += 1
                    saida = tmp / "recebido.bin"
                    seed = a.seed + 1000 * rep
                    try:
                        st, timeout = rodar(protocolo, janela, origem, saida,
                                            perda, a.atraso, taxa_bps, seed)
                        ok = sha256_arquivo(saida) == hash_origem
                    except Exception as e:  # noqa: BLE001
                        print(f"{feitas:>3}/{total:<4} {protocolo:<9}{janela:>3}{perda:>7.0%}  ERRO: {e}")
                        falhas += 1
                        continue
                    falhas += not ok
                    util = (st["bytes_uteis"] * 8 / taxa_bps) / st["tempo_total"]
                    print(f"{feitas:>3}/{total:<4} {protocolo:<9}{janela:>3}{perda:>7.0%}"
                          f"{'OK' if ok else 'FALHOU':>7}{st['tempo_total']:>10.2f}"
                          f"{st['retransmissoes']:>10}{util:>8.1%}")
                    registrar(
                        destino_jsonl,
                        protocolo=protocolo, janela=janela, perda=perda, corrupcao=0.0,
                        atraso=a.atraso, tempo_total=st["tempo_total"],
                        retransmissoes=st["retransmissoes"], bytes_uteis=st["bytes_uteis"],
                        pacotes_enviados=st["pacotes_enviados"], ok_hash=ok,
                        arquivo=origem.name, seed=seed,
                        # campos extras para o gráfico
                        taxa_bps=taxa_bps, rtt=2 * a.atraso, timeout=timeout,
                        tamanho_dados=TAMANHO_DADOS,
                        cabecalho=Packet.HEADER_SIZE, utilizacao=util,
                    )

    print(f"\nresultados gravados em {destino_jsonl}")
    if falhas:
        print(f"{falhas} execução(ões) com hash diferente ou erro")
        sys.exit(1)
    print("todas as execuções: SHA-256 do recebido == SHA-256 do enviado")


if __name__ == "__main__":
    main()
