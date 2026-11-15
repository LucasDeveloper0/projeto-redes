import matplotlib.pyplot as plt
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
                tempo_fallback += 0.1

            tempos.append(t)
            cwnds.append(cwnd)

    return tempos, cwnds

tempos1, cwnd1 = ler_dados_ss('capturas/cwnd_fluxo1.txt', offset_tempo=0.0)
tempos2, cwnd2 = ler_dados_ss('capturas/cwnd_fluxo2.txt', offset_tempo=5.0)

plt.figure(figsize=(10, 5))
plt.plot(tempos1, cwnd1, label='Fluxo 1 (Inicia em 0s)', color='blue', linewidth=1.5)
plt.plot(tempos2, cwnd2, label='Fluxo 2 (Inicia em 5s)', color='orange', linewidth=1.5)
plt.title('Teste de Fairness: Dois Fluxos TCP Competindo no Gargalo (5 Mbps)')
plt.xlabel('Tempo ativo da conexão (segundos)')
plt.ylabel('cwnd (pacotes)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

plt.savefig('graficos/grafico_fairness.png', dpi=300, bbox_inches='tight')
print('Gráfico de Fairness corrigido em graficos/grafico_fairness.png')