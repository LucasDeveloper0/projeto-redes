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

# Salva a imagemimport matplotlib.pyplot as plt
import re

def ler_dados_ss(arquivo, offset_tempo=0.0):
    tempos, cwnds = [], []
    tempo_fallback = 0.0

    with open(arquivo, 'r') as f:
        for linha in f:
            match_cwnd = re.search(r'cwnd:(\d+)', linha)
            if not match_cwnd:
                continue

            # Ignora a conexão de controle do iperf3 (menos de 2 KB trafegados)
            match_bytes = re.search(r'bytes_sent:(\d+)', linha) or re.search(r'bytes_acked:(\d+)', linha)
            if match_bytes and int(match_bytes.group(1)) < 2000:
                continue

            cwnd = int(match_cwnd.group(1))

            # Usa o tempo ativo da conexão (busy) em segundos
            match_busy = re.search(r'busy:(\d+)ms', linha)
            if match_busy:
                t = offset_tempo + (int(match_busy.group(1)) / 1000.0)
            else:
                t = offset_tempo + tempo_fallback
                tempo_fallback += 0.05

            tempos.append(t)
            cwnds.append(cwnd)

    return tempos, cwnds

tempos, cwnds = ler_dados_ss('capturas/cwnd_log.txt')

plt.figure(figsize=(10, 5))
plt.plot(tempos, cwnds, color='blue', linewidth=1.5)
plt.title('Comportamento da Janela de Congestionamento TCP CUBIC')
plt.xlabel('Tempo ativo da conexão (segundos)')
plt.ylabel('Tamanho da Janela (cwnd em pacotes)')
plt.grid(True, linestyle='--', alpha=0.7)

plt.savefig('graficos/grafico_cwnd.png', dpi=300, bbox_inches='tight')
print('Gráfico corrigido em graficos/grafico_cwnd.png')

