# Laboratório de Transporte Confiável (Grupo 3)

Trabalho de Redes de Computadores (UPE). O grupo implementa e observa, na prática, os
mecanismos que tornam confiável a comunicação sobre um canal que não é:

- três protocolos de transferência confiável escritos do zero em Python sobre UDP:
  **rdt3.0** (pare-e-espera), **Go-Back-N** e **Repetição Seletiva**;
- um canal que injeta **perda**, **corrupção** e **atraso** de forma controlada, para mostrar
  a detecção e a recuperação;
- a comparação da **utilização do canal** entre pare-e-espera, GBN e SR;
- a análise de uma conexão **TCP real** no Wireshark e do **controle de congestionamento**
  (partida lenta, AIMD e fairness) no Mininet.

**Grupo:** Lucas, Márcio, João Pedro, João Vitor, José Fernando e Elias.

## Requisitos

- **Python 3.9 ou mais novo.** Os protocolos e os testes usam só a biblioteca padrão.
- **matplotlib**, só para gerar os gráficos: `pip install matplotlib`
- **Mininet** e **iperf3** (Linux), só para a parte de congestionamento.
- **Wireshark**, só para a análise do TCP real.

Todos os comandos abaixo são executados **da raiz do repositório** e funcionam no
Windows, no Linux e no macOS. No Linux e no macOS, troque `python` por `python3` se
necessário.

## Estrutura

```
common/      pacote, canal não confiável e utilitários usados pelos três protocolos
  packet.py    formato do pacote: tipo, seq, ack, checksum (16 bits) e tamanho
  channel.py   UnreliableSocket: UDP com perda, corrupção (inversão de bit) e atraso
  enlace.py    EnlaceSocket: canal com taxa de transmissão e atraso de propagação (experimentos)
  arquivo.py   SHA-256 de um arquivo (validação da transferência)
  metricas.py  grava as métricas de cada execução em JSON Lines
rdt30/       rdt3.0: pare-e-espera, seq 0/1, ACK, temporizador e retransmissão
gbn/         Go-Back-N: janela N, ACK cumulativo, um temporizador, reenvia a janela
sr/          Repetição Seletiva: ACK individual, temporizador por pacote, buffer no receptor
testes/      validação por SHA-256, suíte automatizada, experimentos e topologia Mininet
graficos/    scripts de gráfico, figuras (PNG), FSMs (.dot/.png) e dados dos experimentos
capturas/    logs dos testes, tabela de resultados e medições da cwnd
relatorio/   relatório técnico e documentos de apoio (FSMs, análise do TCP)
```

## Protocolos implementados

| | rdt3.0 | Go-Back-N | Repetição Seletiva |
|---|---|---|---|
| Pacotes em trânsito | 1 | até N | até N |
| Números de sequência | 0 e 1 | 0, 1, 2, ... | 0, 1, 2, ... |
| ACK | do pacote recebido | cumulativo | individual |
| Temporizador | um | um (do pacote `base`) | um por pacote |
| No timeout reenvia | o pacote | a janela inteira | só o pacote vencido |
| Receptor fora de ordem | descarta | descarta | guarda no buffer |

Detalhes comuns aos três:

- **Corrupção:** o checksum de 16 bits detecta o erro e o pacote é descartado como se
  nunca tivesse chegado.
- **Fim do arquivo:** é um pacote de dados **vazio**. Depois de confirmá-lo, o receptor
  continua respondendo por um tempo (*linger*), caso o último ACK tenha se perdido.
- **ACK:** o número confirmado vai no campo `ack_num`; o `seq_num` do ACK não é usado.
- **Mesmos padrões nos três protocolos:** timeout de 0,1 s, 1024 bytes de dados por pacote
  e janela N = 8 (GBN e SR). Assim a comparação entre eles é justa.

## Como executar

### Transferir um arquivo

Cada protocolo tem um receptor e um remetente. Abra dois terminais e inicie o
**receptor primeiro**. Exemplo com a Repetição Seletiva:

```
python -m sr.receptor --porta 5000 --saida recebido.bin
python -m sr.remetente arquivo.bin --porta 5000 --janela 8 --perda 0.1 --seed 42 -v
```

Para os outros protocolos, troque `sr` por `gbn` ou `rdt30` (o rdt3.0 não tem `--janela`).
Os dois lados mostram o SHA-256 no final: se forem iguais, o arquivo chegou íntegro.

Opções do remetente:

| Opção | Significado | Padrão |
|---|---|---|
| `--host`, `--porta` | endereço do receptor | `127.0.0.1`, `5000` |
| `--janela` | tamanho N da janela (GBN e SR) | `8` |
| `--perda` | probabilidade de perder cada pacote (0 a 1) | `0` |
| `--corrupcao` | probabilidade de corromper cada pacote (0 a 1) | `0` |
| `--atraso` | atraso do canal, em segundos | `0` |
| `--seed` | semente do canal, para repetir o mesmo experimento | aleatória |
| `--timeout` | timeout de retransmissão, em segundos | `0.1` |
| `--tamanho` | bytes de dados por pacote | `1024` |
| `-v` | mostra o log de eventos | desligado |

O receptor aceita `--host`, `--porta`, `--saida`, `--perda`, `--corrupcao`, `--atraso`,
`--seed`, `--inatividade` (s sem receber nada antes de desistir, padrão 30),
`--linger` (padrão 1) e `-v`. No receptor, `--perda` e `--corrupcao` valem para os ACKs.
O receptor da SR também aceita `--janela`, que deve ser igual à do remetente.

Com `-v`, o log mostra cada evento da transferência, como `TIMEOUT`, `RETRANSMISSÃO`,
`FORA DE ORDEM`, `DUPLICADO`, `FIM` e os pacotes e ACKs descartados por corrupção.

### Validar cada protocolo nos 5 cenários

Transfere um arquivo de 100 KB em cada cenário (sem falhas, 10% de perda, 20% de perda,
20% de corrupção e 10% de perda + 10% de corrupção) e compara o SHA-256 do recebido com o
do enviado:

```
python -m testes.validar_rdt30
python -m testes.validar_gbn
python -m testes.validar_sr
```

Opções: `--janela N`, `--kb`, `--timeout`, `--registrar` (grava as métricas em
`graficos/resultados.jsonl`) e `-v` (log de eventos).

### Suíte automatizada de testes (requisito C)

Roda os 3 protocolos nos 5 cenários (15 testes). Além do hash, confere que o mecanismo de
recuperação foi realmente acionado: perda gera retransmissão, e toda corrupção é detectada
pelo checksum.

```
python -m unittest testes.test_suite -v
python -m testes.teste_canal
```

A suíte atualiza `capturas/resultados_testes.md` (tabela de resultados) e
`capturas/logs_testes/` (um log por protocolo e cenário, com a sequência detecção,
descarte, timeout e retransmissão). O `teste_canal` confere só o canal: toda perda é
contada e toda corrupção é detectada.

### Gráfico de utilização do canal (requisito B)

Transfere o mesmo arquivo com cada protocolo, variando a janela (1, 2, 4, 8, 16 e 32) e a
perda (0% e 5%), num enlace de 1 Mbit/s com 20 ms de atraso:

```
python -m testes.experimentos
python graficos/plot_utilizacao.py
```

O primeiro comando leva alguns minutos (use `--rapido` para uma conferência rápida) e
grava `graficos/experimentos.jsonl`. O segundo gera `graficos/grafico_utilizacao.png` e
`graficos/utilizacao_resumo.csv`. Veja `python -m testes.experimentos -h` para mudar
janelas, perdas, atraso e taxa.

### Controle de congestionamento no Mininet (requisito E, bônus)

Precisa de Linux com Mininet e iperf3, e de permissão de administrador:

```
sudo python3 testes/topologia_gargalo.py
```

A topologia liga h1 a h2 por um switch: acesso de 100 Mbit/s e 5 ms, e gargalo de
5 Mbit/s, 20 ms e fila de 15 pacotes. No CLI do Mininet, o tráfego é gerado com `iperf3`
e a cwnd é coletada com `ss -ti`. As medições já coletadas estão em `capturas/` e os
gráficos são gerados com:

```
python graficos/plot_cwnd.py
python graficos/plot_fairness.py
```

## Resultados principais

Nos 5 cenários, os três protocolos entregam o arquivo com SHA-256 idêntico ao original, e
toda corrupção injetada é detectada pelo checksum. Com 100 KB, janela N = 8 e semente 42
(`capturas/resultados_testes.md`):

| Cenário | Retransmissões no GBN | Retransmissões na SR |
|---|---|---|
| 10% de perda | 88 | 27 |
| 20% de perda | 178 | 55 |
| 20% de corrupção | 226 | 66 |
| 10% de perda + 10% de corrupção | 206 | 75 |

A SR retransmite só o pacote perdido, enquanto o GBN reenvia a janela inteira. No gráfico
de utilização, sem perda, GBN e SR chegam a cerca de 94% de utilização com N ≥ 8, contra
16% do pare-e-espera. Com 5% de perda, a utilização do GBN cai com janelas grandes
(29% com N = 32), enquanto a da SR continua subindo (62% com N = 32).

## Entregáveis

| Artefato | Onde está |
|---|---|
| Código-fonte e testes de perda e corrupção | `common/`, `rdt30/`, `gbn/`, `sr/`, `testes/` |
| Gráfico de utilização do canal | `graficos/grafico_utilizacao.png` |
| Gráficos da janela de congestionamento | `graficos/grafico_cwnd.png`, `graficos/grafico_fairness.png` |
| Captura TCP comentada | `capturas/` (arquivo `.pcapng` e prints anotados) |
| Relatório (inclui fairness do TCP) | `relatorio/relatorio.md` |
