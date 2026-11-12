import matplotlib.pyplot as plt
import re

def ler_cwnd(arquivo):
    cwnds = []
    with open(arquivo, 'r') as f:
        for linha in f:
            match = re.search(r'cwnd:(\d+)', linha)
            if match:
                cwnds.append(int(match.group(1)))
    return cwnds

cwnd1 = ler_cwnd('capturas/cwnd_fluxo1.txt')
cwnd2 = ler_cwnd('capturas/cwnd_fluxo2.txt')

tempos1 = [x * 0.1 for x in range(len(cwnd1))]
tempos2 = [5.0 + (x * 0.1) for x in range(len(cwnd2))]

plt.figure(figsize=(10, 5))
plt.plot(tempos1, cwnd1, label='Fluxo 1 (Inicia em 0s)', color='blue', linewidth=1.5)
plt.plot(tempos2, cwnd2, label='Fluxo 2 (Inicia em 5s)', color='orange', linewidth=1.5)
plt.title('Teste de Fairness: Dois Fluxos TCP Competindo')
plt.xlabel('Tempo (segundos)')
plt.ylabel('cwnd (pacotes)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)
plt.savefig('graficos/grafico_fairness.png')
print('Gráfico de Fairness gerado!')
