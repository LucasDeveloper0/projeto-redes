"""Registro de métricas dos experimentos (rdt3.0, GBN e SR).

Cada execução termina chamando registrar(), que grava UMA linha JSON em
graficos/resultados.jsonl. Todos os protocolos usam esta mesma função, então o
formato é idêntico e o script de experimentos (gráfico de utilização do canal)
lê tudo do mesmo jeito.

Tempo: segundos, medido com time.perf_counter().

Exemplo:
    inicio = time.perf_counter()
    ...  # transferência
    registrar(
        protocolo="gbn", janela=8, perda=0.1, corrupcao=0.0, atraso=0.02,
        tempo_total=time.perf_counter() - inicio,
        retransmissoes=37, bytes_uteis=1048576, pacotes_enviados=1100,
        ok_hash=True, arquivo="teste.bin",
    )
"""
import json
from pathlib import Path

# <raiz do projeto>/graficos/resultados.jsonl
ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "graficos" / "resultados.jsonl"

PROTOCOLOS = ("rdt30", "gbn", "sr")

# Campos obrigatórios em toda linha. Para o rdt3.0 use janela=1.
CAMPOS_OBRIGATORIOS = (
    "protocolo",         # "rdt30", "gbn" ou "sr"
    "janela",            # tamanho N da janela
    "perda",             # probabilidade de perda do canal (0.0 a 1.0)
    "corrupcao",         # probabilidade de corrupção do canal (0.0 a 1.0)
    "atraso",            # atraso do canal, em segundos
    "tempo_total",       # segundos, do primeiro envio ao último ACK
    "retransmissoes",    # pacotes reenviados
    "bytes_uteis",       # bytes do arquivo entregues (sem cabeçalho nem repetição)
    "pacotes_enviados",  # total de pacotes enviados, incluindo retransmissões
    "ok_hash",           # True se o SHA-256 do recebido é igual ao do enviado
)


def registrar(destino=None, **campos):
    """Grava uma linha JSON com as métricas de uma execução.

    O primeiro argumento (destino) só serve para trocar o arquivo de saída, por
    exemplo nos testes; normalmente fica vazio e grava em graficos/resultados.jsonl.
    Campos extras (por exemplo arquivo="teste.bin", seed=42) são aceitos e
    gravados junto. Levanta ValueError se faltar um campo obrigatório ou se o
    protocolo for desconhecido, para o erro aparecer na hora e não só no gráfico.
    """
    faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in campos]
    if faltando:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(faltando)}")
    if campos["protocolo"] not in PROTOCOLOS:
        raise ValueError(
            f"protocolo inválido: {campos['protocolo']!r} (use um de {PROTOCOLOS})"
        )

    caminho = Path(destino) if destino else ARQUIVO_PADRAO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(campos, ensure_ascii=False) + "\n")
    return caminho
