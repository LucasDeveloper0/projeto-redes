# Análise Experimental do Controle de Congestionamento TCP via Mininet

## 1. Objetivo e Metodologia Experimental

Este experimento teve como objetivo emular, analisar e comprovar o comportamento dinâmico da janela de congestionamento ($\text{cwnd}$) do protocolo TCP diante de um enlace gargalo (*bottleneck*). A topologia foi construída no emulador **Mininet** utilizando o controle de enlace `TCLink` do kernel Linux, conectando um host remetente ($h_1$) a um host receptor ($h_2$) através de um switch central ($s_1$).

Os parâmetros da rede foram dimensionados com base no Produto Banda-Atraso (*Bandwidth-Delay Product* — $\text{BDP}$) para forçar o congestionamento de maneira controlada:

- **Enlace de Acesso ($h_1 \leftrightarrow s_1$):** Largura de banda de $100\text{ Mbps}$ e atraso de propagação de $5\text{ ms}$, garantindo que o remetente injete pacotes na rede sem limitações locais.
- **Enlace Gargalo ($s_1 \leftrightarrow h_2$):** Largura de banda restrita a $5\text{ Mbps}$, atraso de $20\text{ ms}$ e fila (*buffer*) com capacidade máxima de $15\text{ pacotes}$ (`max_queue_size=15`).
- **RTT Base e Dimensionamento de Fila:** O tempo de ida e volta mínimo sem fila ($\text{RTT}_{\text{base}}$) é calculado como:

$$
\text{RTT}_{\text{base}} = 2 \times (5\text{ ms} + 20\text{ ms}) = 50\text{ ms} = 0{,}05\text{ s}
$$

Considerando pacotes padrão Ethernet de $1.500\text{ bytes}$, a capacidade de armazenamento em trânsito no enlace gargalo ($\text{BDP}$) é dada por:

$$
\text{BDP} = \text{Banda} \times \text{RTT}_{\text{base}} = 5\text{ Mbps} \times 0{,}05\text{ s} = 250.000\text{ bits} = 31.250\text{ bytes}
$$

$$
\text{BDP}_{\text{pacotes}} = \frac{31.250\text{ bytes}}{1.500\text{ bytes/pacote}} \approx 20{,}8\text{ pacotes}
$$

Ao limitar o buffer do switch a $15\text{ pacotes}$ (valor inferior a $1\text{ BDP}$), a fila satura rapidamente quando a taxa instantânea do TCP excede a taxa de escoamento de $5\text{ Mbps}$, provocando descartes por *tail drop* e acionando os mecanismos de recuperação do protocolo.

A geração de tráfego TCP foi realizada com a ferramenta `iperf3`, enquanto a coleta da variável interna $\text{cwnd}$ do kernel foi extraída em intervalos de $50\text{ ms}$ a $100\text{ ms}$ por meio do utilitário `ss -ti`.

---

## 2. Análise do Experimento 1: Fluxo Único (Slow Start e AIMD)

No primeiro cenário, estabeleceu-se um único fluxo TCP de $h_1$ para $h_2$ durante $15\text{ segundos}$ (`graficos/grafico_cwnd.png`). A evolução da janela de congestionamento evidenciou as duas fases fundamentais do controle de congestionamento:

1. **Partida Lenta (*Slow Start*):** Nos instantes iniciais da conexão ($t \in [0, 1{,}5]\text{ s}$), o TCP desconhece a capacidade disponível do caminho e incrementa a $\text{cwnd}$ exponencialmente a cada $\text{RTT}$ (dobrando o número de segmentos enviados a cada confirmação recebida). Esse crescimento acelerado preenche rapidamente os $15\text{ pacotes}$ de capacidade do buffer do switch $s_1$.
2. **Prevenção de Congestionamento (*Congestion Avoidance* — AIMD):** Assim que o buffer do gargalo transborda e ocorre o primeiro descarte de pacote, o remetente detecta a perda por meio de 3 ACKs duplicados (*Fast Retransmit*) e aplica a política **AIMD** (*Additive Increase, Multiplicative Decrease*):
   - **Decréscimo Multiplicativo:** A $\text{cwnd}$ é reduzida abruptamente pela metade ($\text{cwnd}_{\text{novo}} = \frac{1}{2} \times \text{cwnd}_{\text{atual}}$) para aliviar a fila do roteador.
   - **Incremento Aditivo:** A partir desse novo patamar, a janela volta a crescer de forma linear e cautelosa ($\text{cwnd} \leftarrow \text{cwnd} + 1\text{ pacote}$ a cada RTT) até atingir novamente o limite físico de $5\text{ Mbps} + 15\text{ pacotes}$ de fila, repetindo o ciclo e formando o padrão clássico de **"dente de serra"**.

---

## 3. Análise do Experimento 2: Concorrência e Justiça (*Fairness*)

No segundo cenário (`graficos/grafico_fairness.png`), avaliou-se a equidade do TCP quando dois fluxos independentes compartilham o mesmo gargalo de $5\text{ Mbps}$. O **Fluxo 1** iniciou no instante $t = 0\text{ s}$ (duração de $20\text{ s}$) e o **Fluxo 2** ingressou na rede em $t = 5\text{ s}$ (duração de $15\text{ s}$):

- **Fase de Monopólio ($0\text{ s} \le t < 5\text{ s}$):** O Fluxo 1 opera sozinho, ocupando toda a banda disponível e oscilando sua $\text{cwnd}$ entre aproximadamente $10$ e $40\text{ pacotes}$.
- **Ingresso do Segundo Fluxo ($t = 5\text{ s}$):** Ao iniciar, o Fluxo 2 executa seu *Slow Start*, gerando um pico inicial agudo (ultrapassando $70\text{ pacotes}$) que satura imediatamente a fila do switch $s_1$.
- **Convergência para Equidade ($t \ge 8\text{ s}$):** Os descartes simultâneos na fila forçam ambos os fluxos a reduzirem suas janelas de congestionamento. Como os dois fluxos possuem o mesmo RTT base ($\text{RTT}_{\text{base}} = 50\text{ ms}$) e obedecem às mesmas regras de incremento linear e redução multiplicativa, eles convergem para uma divisão justa da capacidade: a partir de $t = 10\text{ s}$, as curvas dos dois fluxos passam a oscilar na mesma faixa média de pacotes, comprovando a propriedade de **Fairness** (equidade) do TCP.