"""Suíte automatizada de testes (requisito C): rdt3.0, Go-Back-N e Repetição Seletiva.

Roda os 3 protocolos nos 5 cenários de falha (15 testes). Em cada teste:
  1. o SHA-256 do arquivo recebido tem de ser igual ao do enviado;
  2. o mecanismo de recuperação tem de ter sido realmente acionado
     (perda -> retransmissão por timeout; corrupção -> checksum detecta e descarta).

Efeitos colaterais (evidência para o relatório e o seminário):
  capturas/logs_testes/<protocolo>__<cenario>.log   sequência detecção -> descarte ->
                                                     timeout -> retransmissão
  capturas/resultados_testes.md                      tabela de resultados

Uso (da raiz do projeto):
    python -m unittest testes.test_suite -v
"""
import logging
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from common.arquivo import sha256_arquivo  # noqa: E402
from testes import validar_gbn, validar_rdt30, validar_sr  # noqa: E402

SEED = 42                 # semente fixa: o canal sorteia sempre as mesmas perdas/corrupções
TAMANHO_KB = 100
JANELA = 8                # N do GBN e da SR (o rdt3.0 é pare-e-espera, N = 1)
TIMEOUT = 0.05            # s; folga para não haver timeout espúrio no cenário sem falhas
LINGER = 0.3

PASTA_LOGS = RAIZ / "capturas" / "logs_testes"
ARQUIVO_TABELA = RAIZ / "capturas" / "resultados_testes.md"

# (nome, probabilidade de perda, probabilidade de corrupção) - os 5 cenários do roteiro
CENARIOS = [
    ("sem falhas", 0.0, 0.0),
    ("10% de perda", 0.10, 0.0),
    ("20% de perda", 0.20, 0.0),
    ("só corrupção (20%)", 0.0, 0.20),
    ("perda 10% + corrupção 10%", 0.10, 0.10),
]


def _rodar_rdt30(origem, saida, perda, corr):
    return validar_rdt30.rodar_cenario(origem, saida, perda, corr, TIMEOUT, LINGER, SEED)


def _rodar_gbn(origem, saida, perda, corr):
    return validar_gbn.rodar_cenario(origem, saida, perda, corr, JANELA, TIMEOUT, LINGER, SEED)


def _rodar_sr(origem, saida, perda, corr):
    return validar_sr.rodar_cenario(origem, saida, perda, corr, JANELA, TIMEOUT, LINGER, SEED)


PROTOCOLOS = [("rdt30", _rodar_rdt30), ("gbn", _rodar_gbn), ("sr", _rodar_sr)]

RESULTADOS = []  # uma linha por teste, usada para montar a tabela no final


def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def _corrompidos_detectados(st_tx, st_rx):
    """Pacotes/ACKs que chegaram corrompidos e foram descartados pelo checksum."""
    return st_tx["acks_corrompidos"] + st_rx["pacotes_corrompidos"]


class SuiteTransporteConfiavel(unittest.TestCase):
    """Os testes são gerados dinamicamente: um por (protocolo, cenário)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.origem = tmp / "teste.bin"
        # Arquivo pseudoaleatório reproduzível (mesma semente => mesmo conteúdo)
        cls.origem.write_bytes(random.Random(SEED).randbytes(TAMANHO_KB * 1024))
        cls.hash_origem = sha256_arquivo(cls.origem)
        cls.saida = tmp / "recebido.bin"
        PASTA_LOGS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _executar(self, proto, rodar, nome, perda, corr):
        # Grava o log INFO da execução: mostra detecção, descarte, timeout e retransmissão.
        arq_log = PASTA_LOGS / f"{proto}__{_slug(nome)}.log"
        handler = logging.FileHandler(arq_log, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d [%(name)s] %(message)s",
                                               "%H:%M:%S"))
        raiz = logging.getLogger()
        nivel_antigo = raiz.level
        raiz.addHandler(handler)
        raiz.setLevel(logging.INFO)
        try:
            if self.saida.exists():
                self.saida.unlink()
            st_tx, st_rx, tx, rx = rodar(self.origem, self.saida, perda, corr)
        finally:
            raiz.removeHandler(handler)
            raiz.setLevel(nivel_antigo)
            handler.close()

        perdidos = tx.perdidos + rx.perdidos          # pacotes que o canal descartou
        corrompidos = tx.corrompidos + rx.corrompidos  # pacotes com 1 bit invertido
        detectados = _corrompidos_detectados(st_tx, st_rx)
        retrans = st_tx["retransmissoes"]
        ok_hash = self.saida.exists() and sha256_arquivo(self.saida) == self.hash_origem

        RESULTADOS.append({
            "protocolo": proto, "cenario": nome, "ok": ok_hash,
            "tempo": st_tx["tempo_total"], "retrans": retrans,
            "perdidos": perdidos, "corrompidos": corrompidos, "detectados": detectados,
        })

        # 1) Entrega confiável: o arquivo recebido é idêntico ao enviado.
        self.assertTrue(ok_hash, "SHA-256 do recebido difere do enviado")

        # 2) Os mecanismos foram de fato exercitados no cenário.
        if perda > 0:
            self.assertGreater(perdidos, 0, "o canal deveria ter perdido pacotes")
            self.assertGreater(retrans, 0, "perda exige timeout + retransmissão")
        if corr > 0:
            self.assertGreater(corrompidos, 0, "o canal deveria ter corrompido pacotes")
            self.assertGreater(detectados, 0, "o checksum deveria detectar a corrupção")
            self.assertLessEqual(detectados, corrompidos)
        if perda == 0 and corr == 0:
            self.assertEqual(retrans, 0, "sem falhas não deve haver retransmissão")
            self.assertEqual(detectados, 0)


def _criar_teste(proto, rodar, nome, perda, corr):
    def teste(self):
        self._executar(proto, rodar, nome, perda, corr)
    return teste


for _proto, _rodar in PROTOCOLOS:
    for _nome, _perda, _corr in CENARIOS:
        setattr(SuiteTransporteConfiavel, f"test_{_proto}__{_slug(_nome)}",
                _criar_teste(_proto, _rodar, _nome, _perda, _corr))


def tearDownModule():
    """Escreve a tabela de resultados (Markdown) para colar no relatório."""
    if not RESULTADOS:
        return
    ordem = {p: i for i, (p, _) in enumerate(PROTOCOLOS)}
    nomes = [c[0] for c in CENARIOS]
    linhas = sorted(RESULTADOS, key=lambda r: (ordem[r["protocolo"]], nomes.index(r["cenario"])))
    out = ["| Protocolo | Cenário | Hash | Tempo (s) | Retransmissões | Perdidos | Corrompidos | Detectados (checksum) |",
           "|---|---|---|---|---|---|---|---|"]
    for r in linhas:
        out.append(f"| {r['protocolo']} | {r['cenario']} | {'OK' if r['ok'] else 'FALHOU'} | "
                   f"{r['tempo']:.2f} | {r['retrans']} | {r['perdidos']} | "
                   f"{r['corrompidos']} | {r['detectados']} |")
    ARQUIVO_TABELA.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
