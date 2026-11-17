# Roteiro: Go-Back-N (Márcio Lima), cerca de 4 minutos

Ordem dos slides do GBN: 9 divisor, 10 Go-Back-N, 11 GBN em ação, 12 No código, 13 Utilização × janela, 14 Métricas de desempenho.
Ritmo de fala: uns 130 palavras por minuto. O texto abaixo tem cerca de 540 palavras.

---

## Slide 9: divisor (0:00 a 0:15)

"Eu sou o Márcio e vou falar do Go-Back-N. O Lucas mostrou o rdt3.0, que manda um pacote e espera a confirmação. Eu mostro como a janela deslizante resolve esse desperdício."

## Slide 10: Go-Back-N (0:15 a 1:30)

**Problema (0:15 a 0:40)**
"O pare-e-espera é como mandar uma carta e só escrever a próxima quando a resposta chegar. Enquanto a carta viaja, o canal fica parado. No nosso teste, com 1 Mbit/s e RTT de 40 ms, o rdt3.0 usa só 16% do canal."

**A janela (0:40 a 1:05)**
(apontar para o diagrama)
"No Go-Back-N o remetente pode ter até N pacotes em voo sem esperar confirmação. Aqui N é 4. Ele guarda duas variáveis: **base**, o pacote mais antigo sem confirmação, e **next**, o próximo a enviar. Enquanto next for menor que base mais N, ele continua enviando."

**ACK cumulativo (1:05 a 1:30)**
"A confirmação é cumulativa: um ACK com número k diz que o receptor recebeu tudo até o k. Um único ACK pode liberar vários pacotes, e a janela desliza para frente. Por isso o nome janela deslizante."

## Slide 11: GBN em ação (1:30 a 2:15)

(ler os quatro cartões da esquerda para a direita)
"Vamos ver uma perda. Janela de 4: o remetente envia 0, 1, 2 e 3. O pacote 0 se perde. Os pacotes 1, 2 e 3 chegam fora de ordem, e o receptor só aceita o pacote que está esperando, então descarta os três e repete o último ACK. O remetente tem **um único temporizador**, ligado à base. Quando ele estoura, o remetente volta N: reenvia a janela inteira a partir da base. Daí vem o nome Go-Back-N. É simples, mas um pacote perdido faz reenviar vários."

## Slide 12: No código (2:15 a 2:45)

"No código, em `gbn/remetente.py`, isso é um laço com três passos. Primeiro, enche a janela: envia enquanto `proximo` for menor que `base` mais N, e liga o timer se a janela estava vazia. Segundo, espera o ACK: se chega um ACK k válido, apaga do buffer tudo até k, faz `base` igual a k mais 1 e reinicia o timer. Terceiro, se o timer estoura, reenvia de `base` até `proximo` menos 1. Uma thread só, sem lock."

## Slide 13: Utilização × janela (2:45 a 3:20)

"Medimos a utilização do canal com arquivo de 100 KB, em média de 3 execuções. Sem perda, a utilização sobe de 16% com N igual a 1 para 32%, 64% e 94% com N igual a 8, e para de subir aí, porque o canal já está cheio. A Repetição Seletiva, do João Pedro, tem o mesmo resultado. Mas com 5% de perda a história muda: o GBN cai para 29% com janela 32, porque cada timeout reenvia muito mais pacotes. A Repetição Seletiva continua subindo, até 62%. Janela maior nem sempre ajuda no GBN."

## Slide 14: Métricas de desempenho (3:20 a 3:50)

"Resumindo em três números. **94%** de utilização com N igual a 8, contra 16% do pare-e-espera. **88 retransmissões** com 10% de perda, contra 27 da Repetição Seletiva, o preço do go-back. E **5 em 5** cenários com SHA-256 igual ao original: sem falhas, perda de 10% e 20%, corrupção de 20%, e perda mais corrupção. Mesmo com falhas, o arquivo chegou certo e em ordem."

## Fechamento (3:50 a 4:00)

"O GBN enche o canal com a janela deslizante, confirma com ACK cumulativo e se recupera com um timer só, ao custo de reenviar a janela. Passo agora para o João Pedro."

---

## Dicas para o dia

- Se passar de 4 minutos, corte primeiro a frase da carta no slide 10 e depois o slide 12 (no código). Não corte o slide 11.
- Pergunta provável, "por que o receptor descarta o pacote fora de ordem?": o receptor do GBN não tem buffer, só espera o próximo número. Isso simplifica o receptor, e a Repetição Seletiva muda justamente isso.
- Pergunta provável, "por que a utilização para em N = 8?": com 1 Mbit/s e RTT de 40 ms, poucos pacotes em voo já enchem o enlace, então mais janela não dá ganho. Não afirme o motivo exato de ficar em 94% e não em 100%, só que o cabeçalho de 13 bytes por pacote já tira cerca de 1%.
- Números de apoio (em `graficos/utilizacao_resumo.csv` e no README): 16,3% / 32,4% / 63,8% / 94,0% para N = 1, 2, 4, 8; com 5% de perda, GBN N = 8 dá 50% e N = 32 dá 29%, e SR N = 32 dá 62%.
- No slide 11, o exemplo é didático (pacote 0 perdido, N = 4), não um log real. Se perguntarem, diga isso.

---

## Outras Situações Importantes no GBN (Guia Rápido / Perguntas da Banca)

1. **Perda de ACK intermediário (Tolerância a falhas):**
   - *Cenário:* Envia 0 e 1. Receptor recebe ambos e manda `ACK 0` e `ACK 1`. O `ACK 0` se perde, mas o `ACK 1` chega.
   - *O que acontece:* Como o ACK é **cumulativo**, receber o `ACK 1` confirma automaticamente o pacote 0 também. Nada é retransmitido e a base pula direto para 2.

2. **Chegada fora de ordem e ACKs Duplicados:**
   - *Cenário:* Pacote 4 se perde, mas 5 e 6 chegam.
   - *O que acontece:* O receptor descarta 5 e 6 (não tem buffer) e responde com `ACK 3` repetido para cada pacote descartado. Quando o timer estoura no remetente, ele volta à base e **reenvia 4, 5 e 6**.

3. **Pacote Corrompido (Checksum inválido):**
   - *Cenário:* Bits são alterados durante a transmissão.
   - *O que acontece:* O receptor detecta o erro no checksum e simplesmente descarta o pacote em silêncio. Para o remetente, pacote corrompido é tratado exatamente igual a pacote perdido (espera timeout e reenvia a janela).

4. **Timeout Prematuro (ACK atrasado por jitter/rede lenta):**
   - *Cenário:* O RTT temporariamente excede o valor do timeout configurado.
   - *O que acontece:* O timer estoura antes do ACK voltar. O remetente retransmite a janela toda desnecessariamente; o receptor descarta os pacotes duplicados e reconfirma com ACKs.
