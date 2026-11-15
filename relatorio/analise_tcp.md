# Análise Experimental do Controle de Congestionamento TCP via Mininet

## 1. Objetivo e Metodologia Experimental

Este experimento teve como objetivo emular, analisar e comprovar o comportamento dinâmico da janela de congestionamento (cwnd) do protocolo TCP diante de um enlace gargalo (bottleneck). A topologia foi construída no emulador Mininet utilizando o controle de enlace TCLink do kernel Linux, conectando um host remetente (h1) a um host receptor (h2) através de um switch central (s1).

Os parâmetros da rede foram dimensionados com base no Produto Banda-Atraso (Bandwidth-Delay Product — BDP) para forçar o congestionamento de maneira controlada:

* **Enlace de Acesso (h1 ↔ s1):** Largura de banda de 100 Mbps e atraso de propagação de 5 ms, garantindo que o remetente injete pacotes na rede sem limitações locais.
* **Enlace Gargalo (s1 ↔ h2):** Largura de banda restrita a 5 Mbps, atraso de 20 ms e fila (buffer) com capacidade máxima de 15 pacotes (max_queue_size=15).
* **RTT Base e Dimensionamento de Fila:** O tempo de ida e volta mínimo sem fila (RTT base) é dado por:

RTT base = 2 × (5 ms + 20 ms) = 50 ms = 0,05 s

Considerando pacotes padrão Ethernet de 1.500 bytes, a capacidade de armazenamento em trânsito no enlace gargalo (BDP) é calculada como:

BDP = 5 Mbps × 0,05 s = 250.000 bits = 31.250 bytes
BDP pacotes = 31.250 bytes / 1.500 bytes ≈ 20,8 pacotes

Ao limitar o buffer do switch a 15 pacotes (valor inferior a 1 BDP), a fila satura rapidamente quando a taxa instantânea do TCP excede a taxa de escoamento de 5 Mbps, provocando descartes por tail drop e acionando os mecanismos de recuperação do protocolo.

A geração de tráfego TCP foi realizada com a ferramenta iperf3 (filtrando apenas a conexão de dados para descartar o canal de controle), enquanto a coleta da variável interna cwnd do kernel Linux (algoritmo TCP CUBIC) foi extraída por meio do utilitário ss -ti.

---

## 2. Análise do Experimento 1: Fluxo Único (Slow Start e TCP CUBIC)

No primeiro cenário, estabeleceu-se um único fluxo TCP de h1 para h2 durante 15 segundos (graficos/grafico_cwnd.png). A evolução da janela de congestionamento evidenciou a dinâmica do algoritmo padrão do kernel Linux (**TCP CUBIC**):

1. **Partida Lenta (Slow Start):** Nos instantes iniciais da conexão, o TCP incrementa a cwnd exponencialmente a cada RTT até preencher os 15 pacotes de capacidade do buffer do switch s1.
2. **Prevenção de Congestionamento (Congestion Avoidance — CUBIC):** Assim que o buffer do gargalo transborda e ocorre descarte por tail drop, o remetente detecta a perda por meio de ACKs duplicados e aplica a redução multiplicativa característica do CUBIC:
   * **Decréscimo Multiplicativo (fator 0,7):** Diferente do TCP Reno clássico (que reduz a janela para metade), o TCP CUBIC reduz a cwnd para aproximadamente **0,7×** do valor anterior (caindo dos picos de ~40 pacotes para cerca de 28 pacotes) para aliviar a fila sem subutilizar o enlace.
   * **Crescimento Côncavo/Convexo:** A partir desse patamar, a janela volta a crescer em função cúbica do tempo decorrido desde a última perda, estabilizando na faixa de **27 a 41 pacotes** até atingir novamente o limite físico do enlace e da fila.

---

## 3. Análise do Experimento 2: Concorrência e Justiça (Fairness)

No segundo cenário (graficos/grafico_fairness.png), avaliou-se a equidade do TCP quando dois fluxos independentes compartilham o mesmo gargalo de 5 Mbps. O Fluxo 1 iniciou no instante t = 0 s e o Fluxo 2 ingressou na rede em t = 5 s:

* **Fase de Monopólio (0 s a 5 s):** O Fluxo 1 opera sozinho, realiza seu pico inicial de Slow Start (~46 pacotes) e estabiliza o crescimento ocupando toda a banda disponível.
* **Ingresso do Segundo Fluxo (t = 5 s):** Ao iniciar, o Fluxo 2 executa seu Slow Start com um pico agudo (~75 pacotes), saturando imediatamente a fila do switch s1 e provocando descartes em ambos os fluxos.
* **Convergência para Equidade (a partir de 7 s):** Como os dois fluxos possuem o mesmo RTT base (50 ms) e operam sob o mesmo controle de congestionamento CUBIC, eles convergem para uma divisão equilibrada do gargalo: suas janelas passam a oscilar na mesma faixa média (entre 27 e 41 pacotes) e a proporção relativa de bytes transmitidos estabiliza em aproximadamente **53% para o Fluxo 1 e 47% para o Fluxo 2**, comprovando a propriedade de Fairness do TCP.

---

## 4. Limitações Experimentais

* **Estimativa Temporal:** Como a captura bruta do utilitário `ss -ti` não registrava timestamps absolutos de relógio, o eixo horizontal dos gráficos foi reconstruído a partir do tempo ativo acumulado da conexão (`busy` em milissegundos).
* **Amostragem:** Os resultados refletem uma execução experimental representativa para cada cenário configurado na topologia emulada.