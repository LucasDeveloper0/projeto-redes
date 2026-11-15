"""Validação do rdt3.0: transfere um arquivo em vários cenários de falha e compara SHA-256.

Para cada cenário (sem falhas, perda, corrupção, perda + corrupção):
  1. gera um arquivo de teste reprodutível (bytes aleatórios com semente fixa);
  2. sobe receptor e remetente na mesma máquina (receptor em uma thread);
  3. transfere pelo UnreliableSocket com a perda/corrupção do cenário;
  4. compara o SHA-256 do arquivo recebido com o do original.
Se os hashes forem iguais, o rdt3.0 se recuperou de todas as falhas injetadas.

Uso:  python -m testes.validar_rdt30 [-v] [--kb 100] [--registrar]
Sai com código 1 se algum cenário terminar com hash diferente.
"""
import argparse
import logging
import random
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.arquivo import sha256_arquivo  # noqa: E402
from common.channel import UnreliableSocket  # noqa: E402
from common.metricas import registrar  # noqa: E402
from rdt30.receptor import receber_arquivo  # noqa: E402
from rdt30.remetente import enviar_arquivo  # noqa: E402

# (nome, probabilidade de perda, probabilidade de corrupção)
CENARIOS = [
    ("sem falhas", 0.0, 0.0),
    ("10% de perda", 0.10, 0.0),
    ("20% de perda", 0.20, 0.0),
    ("só corrupção (20%)", 0.0, 0.20),
    ("perda 10% + corrupção 10%", 0.10, 0.10),
]

# Semente fixa: o mesmo comando gera sempre as mesmas perdas (resultado reprodutível)
SEED = 42


def rodar_cenario(arquivo, saida, perda, corrupcao, timeout, linger, seed=SEED):
    """Faz uma transferência completa e devolve (stats_tx, stats_rx, canal_tx, canal_rx)."""
    # Receptor: porta 0 = o sistema operacional escolhe uma porta livre.
    # Sementes diferentes (seed+1) para os dois lados não repetirem o mesmo sorteio.
    rx = UnreliableSocket(loss=perda, corrupt=corrupcao, seed=seed + 1)
    rx.bind(("127.0.0.1", 0))
    destino = rx.sock.getsockname()
    tx = UnreliableSocket(loss=perda, corrupt=corrupcao, seed=seed)

    resultado = {}

    def lado_receptor():
        # Roda em outra thread, porque remetente e receptor bloqueiam esperando um ao outro
        try:
            resultado["rx"] = receber_arquivo(rx, saida, inatividade=20.0, linger=linger)
        except Exception as e:  # noqa: BLE001 - repassa o erro para a thread principal
            resultado["erro"] = e

    t = threading.Thread(target=lado_receptor, daemon=True)
    t.start()
    try:
        st_tx = enviar_arquivo(tx, destino, arquivo, timeout=timeout)
    finally:
        # espera o receptor terminar (inclui o linger) e libera os sockets
        t.join(timeout=30)
        tx.close()
        rx.close()
    if "erro" in resultado:
        raise resultado["erro"]
    return st_tx, resultado["rx"], tx, rx


def main():
    """Roda todos os cenários, imprime a tabela e termina com código 1 se algum falhar."""
    ap = argparse.ArgumentParser(description="Valida o rdt3.0 comparando SHA-256")
    ap.add_argument("--kb", type=int, default=100, help="tamanho do arquivo de teste (KB)")
    ap.add_argument("--timeout", type=float, default=0.02, help="timeout do remetente (s)")
    ap.add_argument("--linger", type=float, default=0.3, help="linger do receptor (s)")
    ap.add_argument("--registrar", action="store_true",
                    help="grava as métricas em graficos/resultados.jsonl")
    ap.add_argument("-v", "--verbose", action="store_true", help="mostra o log de eventos")
    a = ap.parse_args()

    # Com -v aparecem os eventos (TIMEOUT, RETRANSMISSÃO, DUPLICADO ...) de cada cenário
    logging.basicConfig(
        level=logging.INFO if a.verbose else logging.WARNING,
        format="%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    falhas = 0
    # Pasta temporária: arquivos de teste não sujam o repositório
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        origem = tmp / "teste.bin"
        # bytes pseudoaleatórios determinísticos (mesma semente -> mesmo arquivo)
        origem.write_bytes(random.Random(SEED).randbytes(a.kb * 1024))
        hash_origem = sha256_arquivo(origem)
        print(f"arquivo de teste: {a.kb} KB  sha256={hash_origem[:16]}...\n")

        cab = (f"{'cenário':<28}{'hash':<6}{'tempo(s)':>9}{'retrans.':>9}{'pacotes':>9}"
               f"{'perdidos':>9}{'corrompidos':>12}")
        print(cab)
        print("-" * len(cab))

        for nome, perda, corr in CENARIOS:
            if a.verbose:
                print(f"\n=== {nome} ===")
            saida = tmp / "recebido.bin"
            st, srx, tx, rx = rodar_cenario(origem, saida, perda, corr, a.timeout, a.linger)
            # A validação central: hash do recebido == hash do original?
            ok = sha256_arquivo(saida) == hash_origem
            falhas += not ok
            # perdas/corrupções somam os dois sentidos (dados e ACKs)
            perdidos = tx.perdidos + rx.perdidos
            corrompidos = tx.corrompidos + rx.corrompidos
            print(f"{nome:<28}{'OK' if ok else 'FALHOU':<6}{st['tempo_total']:>9.2f}"
                  f"{st['retransmissoes']:>9}{st['pacotes_enviados']:>9}"
                  f"{perdidos:>9}{corrompidos:>12}")

            if a.registrar:
                # guarda a linha no .jsonl que alimenta os gráficos
                registrar(
                    protocolo="rdt30", janela=1, perda=perda, corrupcao=corr, atraso=0.0,
                    tempo_total=st["tempo_total"], retransmissoes=st["retransmissoes"],
                    bytes_uteis=st["bytes_uteis"], pacotes_enviados=st["pacotes_enviados"],
                    ok_hash=ok, arquivo=origem.name, seed=SEED,
                )

    print()
    if falhas:
        print(f"{falhas} cenário(s) com hash diferente")
        sys.exit(1)  # código de saída diferente de zero indica falha (útil em scripts/CI)
    print("todos os cenários: SHA-256 do recebido == SHA-256 do enviado")


if __name__ == "__main__":
    main()
