import socket
from common.channel import UnreliableSocket
from common.packet import Packet, DADOS

rx = UnreliableSocket()
rx.bind(("127.0.0.1", 0))
rx.settimeout(0.05)
addr = rx.sock.getsockname()
tx = UnreliableSocket(loss=0.2, corrupt=0.3, seed=42)

N = 2000
ok = invalidos = 0
for i in range(N):
    tx.sendto(Packet.make(DADOS, i, 0, b"dados" * 20), addr)
    try:
        d, _ = rx.recvfrom(2048)
    except socket.timeout:
        continue 
    if Packet.extract(d) is None:
        invalidos += 1
    else:
        ok += 1

print(f"enviados={tx.enviados} perdidos={tx.perdidos} corrompidos={tx.corrompidos}")
print(f"recebidos válidos={ok} descartados por checksum={invalidos}")
assert ok + invalidos == N - tx.perdidos
assert invalidos == tx.corrompidos
print("ok: toda corrupção foi detectada e toda perda foi contada")