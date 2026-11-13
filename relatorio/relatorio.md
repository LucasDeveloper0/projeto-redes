# Laboratório de Transporte Confiável: Relatório Técnico

**Disciplina:** Redes de Computadores, Universidade de Pernambuco (UPE)
**Grupo 3:** Lucas, Márcio, João Pedro, João Vitor, José Fernando e Elias
**Entrega:** 17/11/2026

> **Como usar este documento.** Cada seção tem um responsável e um prazo. Quem for o
> responsável apaga a caixa de instruções (as linhas que começam com `>`) e escreve o
> texto no lugar. Não mexam nas seções dos outros: se algo estiver errado, avisem no
> grupo. Figuras entram com caminho relativo a esta pasta, por exemplo
> `![legenda](../graficos/grafico_utilizacao.png)`. Texto em Markdown simples
> (títulos, listas, tabelas e imagens), porque o arquivo final será exportado para PDF.
> Prazo para todas as seções: **domingo, 15/11**. O Márcio consolida na segunda, 16/11.

---

## 1. Introdução

> **Responsável:** Márcio (escreve por último, depois das outras seções)
> **O que escrever:** o problema (transporte confiável sobre um canal que perde e corrompe
> pacotes), os objetivos do trabalho, as ferramentas usadas (Python, UDP, Wireshark,
> Mininet) e um resumo de como o relatório está organizado.

## 2. rdt3.0: pare-e-espera sobre UDP

> **Responsável:** Lucas (requisito A)
> **O que escrever:** o formato do pacote (tipo, número de sequência, ACK, checksum,
> tamanho), o funcionamento do rdt3.0 (sequência 0/1, ACK, temporizador, retransmissão),
> a FSM e a validação com SHA-256.
> **Material pronto:** `relatorio/fsm_rdt30.md`, `graficos/fsm_rdt30_remetente.png`,
> `graficos/fsm_rdt30_receptor.png`, `common/packet.py`, `rdt30/`.

## 3. Go-Back-N

### 3.1 Funcionamento

O Go-Back-N (GBN) é um protocolo de **janela deslizante**: em vez de esperar o ACK de cada
pacote, como o rdt3.0, o remetente pode ter até **N pacotes enviados e ainda não
confirmados**. Isso mantém o canal ocupado enquanto os ACKs voltam.

O remetente controla a janela com duas variáveis: `base`, o número de sequência do pacote
mais antigo sem ACK, e `proximo`, o número do próximo pacote a enviar. Ele só envia quando
`proximo < base + N`. As regras são:

- **ACK cumulativo:** um ACK com número `k` confirma todos os pacotes até `k`. Ao recebê-lo,
  o remetente faz `base = k + 1` e a janela desliza.
- **Temporizador único:** há um só temporizador, associado ao pacote `base`. Ele liga ao
  enviar o primeiro pacote da janela, reinicia quando a base avança e para quando não há
  nada em trânsito.
- **Timeout:** se o ACK de `base` não chega a tempo, o remetente **volta N** (*go back N*):
  retransmite todos os pacotes da janela, de `base` até `proximo - 1`.
- **Receptor sem buffer:** o receptor aceita **somente o pacote esperado**. Pacote fora de
  ordem, duplicado ou com checksum inválido é descartado e o receptor reenvia o ACK do
  último pacote entregue em ordem.

Com N = 1 o GBN se reduz ao pare-e-espera. Quanto maior o N, mais pacotes ficam em trânsito,
mas cada perda custa mais caro, porque força a retransmissão da janela inteira (seção 3.5).

### 3.2 Máquina de estados (FSM)

O remetente tem dois estados: **janela vazia** (temporizador parado) e **pacotes em
trânsito** (temporizador ligado). O receptor tem um estado só, que espera o pacote de número
`esperado`.

![FSM do remetente Go-Back-N](../graficos/fsm_gbn_remetente.png)

![FSM do receptor Go-Back-N](../graficos/fsm_gbn_receptor.png)

A tabela que liga cada elemento da FSM ao conceito da aula e ao trecho do código está em
`relatorio/fsm_gbn.md`.

### 3.3 Implementação

A implementação está em `gbn/remetente.py` e `gbn/receptor.py`, escrita em Python sobre
UDP e no mesmo padrão do rdt3.0 e da Repetição Seletiva, para os três protocolos serem
executados e comparados do mesmo jeito.

- **Formato do pacote e canal:** usa a classe `Packet` (`common/packet.py`), com número de
  sequência e de ACK de 4 bytes e checksum de 16 bits, e o canal não confiável
  (`common/channel.py`), que injeta perda, corrupção e atraso. Um pacote com checksum
  inválido é descartado como se nunca tivesse chegado (`Packet.extract()` devolve `None`).
- **Remetente de uma thread só:** um laço alterna entre encher a janela e esperar um ACK até
  o prazo do temporizador. Não há travas, porque nenhuma estrutura é compartilhada.
- **Fim do arquivo:** é sinalizado por um pacote de dados **vazio**, que passa pela janela
  como um pacote comum. Depois de confirmá-lo, o receptor espera um tempo (*linger*) para
  responder caso o último ACK tenha se perdido.
- **ACK inicial:** o campo de ACK não tem sinal, então, enquanto nada foi entregue, o
  receptor não envia ACK e o remetente recupera por timeout.
- **Parâmetros:** a janela é escolhida por `--janela` (padrão 8). Timeout padrão de 0,1 s e
  1024 bytes de dados por pacote, os mesmos valores do rdt3.0.
- **Métricas e log:** o remetente devolve tempo total, retransmissões, pacotes enviados,
  ACKs corrompidos e duplicados e bytes úteis, gravados por `common/metricas.py`. O log de
  eventos usa os termos `RETRANSMISSÃO`, `TIMEOUT` e `ACK CORROMPIDO`.

Exemplo de execução, em dois terminais:

```bash
python gbn/receptor.py --porta 5000 --saida recebido.bin
python gbn/remetente.py arquivo.bin --porta 5000 --janela 8 --perda 0.1 --seed 42
```

### 3.4 Resultados nos cenários de teste

A suíte automatizada (`testes/test_suite.py`) transfere um arquivo em cada cenário e compara
o SHA-256 do arquivo recebido com o do enviado. O GBN passou nos cinco cenários, sempre com
hash igual. Os números abaixo vêm de `capturas/resultados_testes.md`:

| Cenário | Hash | Tempo (s) | Retransmissões | Pacotes perdidos | Pacotes corrompidos | Detectados pelo checksum |
| --- | --- | --- | --- | --- | --- | --- |
| sem falhas | OK | 0,03 | 0 | 0 | 0 | 0 |
| 10% de perda | OK | 0,68 | 88 | 35 | 0 | 0 |
| 20% de perda | OK | 1,49 | 178 | 95 | 0 | 0 |
| só corrupção (20%) | OK | 1,80 | 226 | 0 | 139 | 139 |
| perda 10% + corrupção 10% | OK | 1,61 | 206 | 67 | 59 | 59 |

Dois pontos aparecem na tabela:

- **Toda corrupção foi detectada:** o número de pacotes corrompidos é igual ao detectado pelo
  checksum, então nenhum pacote com erro chegou à aplicação.
- **Muitas retransmissões:** com 10% de perda, o GBN fez 88 retransmissões para 35 pacotes
  perdidos, enquanto o rdt3.0 e a Repetição Seletiva fizeram 27, uma por perda. A diferença
  é o custo do *go back N*: cada timeout reenvia também pacotes que já tinham chegado.

Em tempo total os protocolos ficaram próximos nesses testes curtos: com 10% de perda, o GBN
levou 0,68 s, a SR 0,86 s e o rdt3.0 1,67 s. Como o arquivo é pequeno e os tempos dependem do
timeout, a comparação de desempenho é feita na seção 5, com atraso e taxa de enlace.

### 3.5 Comportamento observado

Os experimentos da seção 5 usam um arquivo de 100 KB, enlace de 1 Mbit/s, RTT de 40 ms e
três repetições por ponto. A utilização é a fração da taxa do enlace usada por dados úteis.
Valores médios para o GBN, com a Repetição Seletiva ao lado:

| Janela N | GBN, sem perda | SR, sem perda | GBN, 5% de perda | SR, 5% de perda |
| --- | --- | --- | --- | --- |
| 1 | 16,3% | 16,4% | 14,1% | 14,1% |
| 2 | 32,4% | 32,4% | 25,2% | 24,6% |
| 4 | 63,8% | 63,8% | 40,0% | 38,0% |
| 8 | 94,0% | 94,1% | 50,1% | 49,6% |
| 16 | 94,0% | 94,0% | 49,7% | 58,0% |
| 32 | 94,0% | 94,0% | 28,9% | 62,3% |

**Sem perda.** A utilização cresce quase linearmente com N e satura em cerca de 94%. Um
pacote de 1037 bytes (1024 de dados e 13 de cabeçalho) leva 8,3 ms para sair do enlace e o
RTT é de 40 ms, então são necessários cerca de 1 + 40 / 8,3 ≈ 6 pacotes em trânsito para manter o canal ocupado. Isso
explica por que N = 8 já satura e N = 16 e N = 32 não melhoram. Com N = 1, o GBN usa 16,3%,
o mesmo valor do rdt3.0 (16,3%), como esperado.

**Com 5% de perda.** O GBN melhora até N = 8 (50,1%), fica estável em N = 16 (49,7%) e
**cai para 28,9% com N = 32**. A Repetição Seletiva, ao contrário, continua melhorando e
chega a 62,3%. A causa é o *go back N*: com janela grande, cada perda obriga o remetente a
reenviar até N pacotes, e o receptor descarta os que chegaram fora de ordem. Em uma janela de
32 pacotes, uma só perda pode desperdiçar dezenas de transmissões. O experimento também
aumenta o timeout junto com a janela (RTT mais o tempo de a janela sair do enlace), o que
contribui para a queda em N = 32, porque o remetente demora mais para perceber a perda.

**Limitações da implementação.** O timeout é fixo, sem adaptação ao RTT medido, e o receptor
não guarda pacotes fora de ordem, por isso a Repetição Seletiva é mais eficiente em canais
com perda. O número de sequência de 4 bytes evita a volta ao zero nos arquivos usados.

## 4. Repetição Seletiva

> **Responsável:** João Pedro (requisito B)
> **O que escrever:** o funcionamento da SR (janela no remetente e no receptor, buffer de
> pacotes fora de ordem, ACK individual, temporizador por pacote), a implementação,
> os resultados e a diferença em relação ao Go-Back-N.
> **Material pronto:** `sr/`, `testes/validar_sr.py`, `capturas/resultados_testes.md`.

## 5. Comparação da utilização do canal

> **Responsável:** Lucas (requisito A e comparação do B)
> **O que escrever:** como foram feitos os experimentos (mesmo arquivo, mesma perda e
> mesmo atraso, variando a janela), o gráfico de utilização do canal (pare-e-espera,
> GBN e SR) e a discussão dos resultados.
> **Material pronto:** `graficos/grafico_utilizacao.png`, `graficos/utilizacao_resumo.csv`,
> `testes/experimentos.py`, `graficos/plot_utilizacao.py`.

## 6. Injeção de falhas e testes

> **Responsável:** João Vitor (requisito C)
> **O que escrever:** o canal que simula a rede não confiável (perda, corrupção por
> inversão de bits, atraso, semente fixa), os 5 cenários de teste, a tabela de resultados
> e a sequência detecção, descarte, timeout e retransmissão mostrada nos logs.
> **Material pronto:** `common/channel.py`, `common/enlace.py`, `testes/test_suite.py`,
> `capturas/resultados_testes.md`, `capturas/logs_testes/`.

## 7. Análise de uma conexão TCP real

> **Responsável:** José Fernando (requisito D)
> **O que escrever:** o handshake de três vias (flags, números de sequência e de ACK
> iniciais), a troca de dados (como sequência e ACK avançam, janela de recepção anunciada),
> o encerramento (FIN/ACK), prints anotados ligando cada campo ao conceito da aula e a
> comparação do ACK cumulativo do TCP com o GBN e a SR.
> **Material:** a captura `.pcapng` e os prints anotados em `capturas/`.

## 8. Por que o TCP é justo (fairness)

> **Responsável:** José Fernando (texto obrigatório)
> **O que escrever:** o que é fairness, por que o TCP (AIMD) tende a dividir o gargalo de
> forma igual e o que as medições de dois fluxos mostraram.
> **Material pronto:** `graficos/grafico_fairness.png` e `capturas/cwnd_fluxo1.txt`,
> `capturas/cwnd_fluxo2.txt` (medições do Elias).

## 9. Controle de congestionamento (bônus)

> **Responsável:** Elias (requisito E)
> **O que escrever:** a topologia com enlace gargalo, a partida lenta e o padrão
> dente-de-serra do AIMD, e a análise do gráfico da cwnd.
> **Material pronto:** `relatorio/analise_tcp.md` (pode ser incorporado aqui),
> `graficos/grafico_cwnd.png`, `testes/topologia_gargalo.py`.

## 10. Conclusão

> **Responsável:** Márcio (escreve por último)
> **O que escrever:** o que o grupo aprendeu, os resultados principais (GBN versus SR,
> pare-e-espera versus janela deslizante, TCP real) e as limitações do trabalho.

## Referências

> Livros e materiais da disciplina usados no trabalho.

## Apêndice: como executar

> **Responsável:** João Pedro (a partir do `README.md` do repositório)
> Comandos para rodar cada protocolo e os testes.
