import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "graficos" / "experimentos.jsonl"
PNG = RAIZ / "graficos" / "grafico_utilizacao.png"
CSV = RAIZ / "graficos" / "utilizacao_resumo.csv"

# paleta categórica validada (slots 1-3, modo claro) + tintas de texto
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e3e2de"
# nome: (cor, marcador, preenchimento, rótulo)
ESTILO = {
    "gbn": ("#2a78d6", "o", True, "Go-Back-N"),
    "sr": ("#eb6834", "s", False, "Repetição Seletiva"),
    "rdt30": ("#1baf7a", "D", True, "rdt3.0 (pare-e-espera, N = 1)"),
}


def carregar():
    if not ENTRADA.exists():
        sys.exit(f"{ENTRADA} não existe. Rode antes: python -m testes.experimentos")
    linhas = [json.loads(l) for l in ENTRADA.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not linhas:
        sys.exit("arquivo de resultados vazio")
    ruins = [l for l in linhas if not l["ok_hash"]]
    if ruins:
        print(f"AVISO: {len(ruins)} execução(ões) com hash diferente foram ignoradas")
    return [l for l in linhas if l["ok_hash"]]


def agregar(linhas):
    """(perda, protocolo, janela) -> (média, mínimo, máximo, n) da utilização."""
    grupos = defaultdict(list)
    for l in linhas:
        grupos[(l["perda"], l["protocolo"], l["janela"])].append(l["utilizacao"])
    return {k: (sum(v) / len(v), min(v), max(v), len(v)) for k, v in grupos.items()}


def teorica(n, l):
    """Limite teórico da aula, descontando o cabeçalho (só dados úteis contam)."""
    tx_pacote = (l["tamanho_dados"] + l["cabecalho"]) * 8 / l["taxa_bps"]
    u = n * tx_pacote / (l["rtt"] + tx_pacote)
    return min(1.0, u) * l["tamanho_dados"] / (l["tamanho_dados"] + l["cabecalho"])


def main():
    linhas = carregar()
    agg = agregar(linhas)
    ref = linhas[0]
    perdas = sorted({l["perda"] for l in linhas})
    janelas = sorted({l["janela"] for l in linhas if l["protocolo"] != "rdt30"})

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "text.color": TEXTO, "axes.labelcolor": TEXTO_2,
        "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    })
    fig, eixos = plt.subplots(1, len(perdas), figsize=(5.6 * len(perdas), 4.8),
                              sharey=True, squeeze=False, facecolor=SUPERFICIE)

    teo_x = [2 ** (i / 8) for i in range(int(8 * __import__("math").log2(max(janelas))) + 1)]
    teo_x = [x for x in teo_x if x >= min(janelas)]

    for ax, perda in zip(eixos[0], perdas):
        ax.set_facecolor(SUPERFICIE)
        ax.grid(axis="y", color=GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color(GRADE)

        # limite teórico (referência recessiva)
        ax.plot(teo_x, [teorica(x, ref) * 100 for x in teo_x], color=TEXTO_2, linestyle=":",
                linewidth=1.4, label="Limite teórico", zorder=1)

        # rdt3.0: sempre N = 1, desenhado como linha horizontal de referência
        if (perda, "rdt30", 1) in agg:
            m, lo, hi, _ = agg[(perda, "rdt30", 1)]
            cor, mk, cheio, rot = ESTILO["rdt30"]
            ax.axhline(m * 100, color=cor, linestyle="--", linewidth=1.8, zorder=2)
            ax.errorbar([1], [m * 100], yerr=[[(m - lo) * 100], [(hi - m) * 100]], color=cor,
                        marker=mk, markersize=7, capsize=3, linewidth=1.5, linestyle="none",
                        label=rot, zorder=5)

        for proto in ("gbn", "sr"):
            xs = [n for n in janelas if (perda, proto, n) in agg]
            ms = [agg[(perda, proto, n)][0] * 100 for n in xs]
            lo = [(agg[(perda, proto, n)][0] - agg[(perda, proto, n)][1]) * 100 for n in xs]
            hi = [(agg[(perda, proto, n)][2] - agg[(perda, proto, n)][0]) * 100 for n in xs]
            cor, mk, cheio, rot = ESTILO[proto]
            ax.errorbar(xs, ms, yerr=[lo, hi], color=cor, marker=mk, markersize=7 if cheio else 10,
                        markerfacecolor=cor if cheio else "none", markeredgewidth=1.8,
                        linewidth=2.0, capsize=3, label=rot, zorder=4 if cheio else 3)

        ax.set_xscale("log", base=2)
        ax.set_xticks(janelas)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}"))
        ax.minorticks_off()
        ax.set_ylim(0, 105)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}%"))
        ax.set_xlabel("Tamanho da janela N (pacotes)")
        ax.set_title("Sem perda" if perda == 0 else f"Perda de {perda:.0%}", loc="left",
                     fontsize=11, color=TEXTO, fontweight="bold")
    eixos[0][0].set_ylabel("Utilização do canal")

    h, r = eixos[0][0].get_legend_handles_labels()
    fig.legend(h, r, loc="lower center", ncol=4, frameon=False, fontsize=9.5,
               labelcolor=TEXTO_2)
    mbps = ref["taxa_bps"] / 1e6
    fig.suptitle("Utilização do canal: pare-e-espera vs Go-Back-N vs Repetição Seletiva",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=TEXTO)
    fig.text(0.01, 0.905, f"Enlace de {mbps:g} Mbit/s, RTT de {ref['rtt'] * 1000:.0f} ms, "
             f"pacotes de {ref['tamanho_dados']} bytes de dados; mesma perda e mesmo arquivo "
             f"nos três protocolos", ha="left", fontsize=9, color=TEXTO_2)
    fig.tight_layout(rect=(0, 0.07, 1, 0.9))
    fig.savefig(PNG, dpi=200, facecolor=SUPERFICIE)
    print(f"gráfico salvo em {PNG}")

    # tabela com os números do gráfico (visão alternativa, boa para o relatório)
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["perda", "protocolo", "janela", "utilizacao_media", "minimo", "maximo",
                    "repeticoes"])
        for (perda, proto, n), (m, lo, hi, k) in sorted(agg.items()):
            w.writerow([perda, proto, n, f"{m:.4f}", f"{lo:.4f}", f"{hi:.4f}", k])
    print(f"tabela salva em {CSV}")


if __name__ == "__main__":
    main()
