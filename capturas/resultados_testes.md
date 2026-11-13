| Protocolo | Cenário | Hash | Tempo (s) | Retransmissões | Perdidos | Corrompidos | Detectados (checksum) |
|---|---|---|---|---|---|---|---|
| rdt30 | sem falhas | OK | 0.02 | 0 | 0 | 0 | 0 |
| rdt30 | 10% de perda | OK | 1.67 | 27 | 27 | 0 | 0 |
| rdt30 | 20% de perda | OK | 3.40 | 55 | 55 | 0 | 0 |
| rdt30 | só corrupção (20%) | OK | 3.91 | 63 | 0 | 75 | 75 |
| rdt30 | perda 10% + corrupção 10% | OK | 4.10 | 66 | 38 | 37 | 37 |
| gbn | sem falhas | OK | 0.03 | 0 | 0 | 0 | 0 |
| gbn | 10% de perda | OK | 0.68 | 88 | 35 | 0 | 0 |
| gbn | 20% de perda | OK | 1.49 | 178 | 95 | 0 | 0 |
| gbn | só corrupção (20%) | OK | 1.80 | 226 | 0 | 139 | 139 |
| gbn | perda 10% + corrupção 10% | OK | 1.61 | 206 | 67 | 59 | 59 |
| sr | sem falhas | OK | 0.03 | 0 | 0 | 0 | 0 |
| sr | 10% de perda | OK | 0.86 | 27 | 27 | 0 | 0 |
| sr | 20% de perda | OK | 1.49 | 55 | 55 | 0 | 0 |
| sr | só corrupção (20%) | OK | 1.49 | 66 | 0 | 66 | 66 |
| sr | perda 10% + corrupção 10% | OK | 2.04 | 75 | 38 | 37 | 37 |
