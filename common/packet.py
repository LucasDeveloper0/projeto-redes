import struct
import hashlib

class Packet:
    # Exemplo de formato: 
    # Tipo (1 byte: 0=dados, 1=ack), Seq (1 byte), Ack (1 byte), Checksum (2 bytes), Tamanho do Payload (2 bytes)
    HEADER_FORMAT = "!BBBHH"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @staticmethod
    def make(pkt_type, seq_num, ack_num, data: bytes) -> bytes:
        checksum = 0 # Pode implementar checksum simples (ex: soma de verificação ou crc16)
        length = len(data)
        header = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, checksum, length)
        return header + data

    @staticmethod
    def extract(packet_bytes: bytes):
        header = packet_bytes[:Packet.HEADER_SIZE]
        data = packet_bytes[Packet.HEADER_SIZE:]
        pkt_type, seq_num, ack_num, checksum, length = struct.unpack(Packet.HEADER_FORMAT, header)
        return pkt_type, seq_num, ack_num, checksum, data