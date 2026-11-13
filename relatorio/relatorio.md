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

> **Responsável:** Márcio (requisito B)

### 3.1 Funcionamento

### 3.2 Máquina de estados (FSM)

### 3.3 Implementação

### 3.4 Resultados nos cenários de teste

### 3.5 Comportamento observado

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
