import matplotlib.pyplot as plt
import re

tempos, cwnds = [], []
tempo_atual = 0.0

# Lê o arquivo gerado pelo Mininet/ss
with open('capturas/cwnd_log.txt', 'r') as f:
    for linha in f:
        match = re.search(r'cwnd:(\d+)', linha)
        if match:
            cwnds.append(int(match.group(1)))
            tempos.append(tempo_atual)
            tempo_atual += 0.05  # O intervalo de coleta foi 0.05s

# Monta o gráfico
plt.figure(figsize=(10, 5))
plt.plot(tempos, cwnds, color='blue', linewidth=1.5)
plt.title('Comportamento da Janela de Congestionamento TCP (AIMD)')
plt.xlabel('Tempo (segundos)')
plt.ylabel('Tamanho da Janela (cwnd em pacotes)')
plt.grid(True, linestyle='--', alpha=0.7)

# Salva a imagem
plt.savefig('graficos/grafico_cwnd.png')
print('Gráfico gerado em graficos/grafico_cwnd.png')
