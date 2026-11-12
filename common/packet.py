import struct

DADOS = 0
ACK = 1


class Packet:

    HEADER_FORMAT = "!BIIHH"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @staticmethod
    def _checksum(b: bytes) -> int:
        if len(b) % 2:
            b += b"\x00"
        s = 0
        for i in range(0, len(b), 2):
            s += (b[i] << 8) | b[i + 1]
            s = (s & 0xFFFF) + (s >> 16)
        return ~s & 0xFFFF

    @staticmethod
    def make(pkt_type, seq_num, ack_num, data: bytes = b"") -> bytes:
        length = len(data)
        sem_checksum = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, 0, length)
        checksum = Packet._checksum(sem_checksum + data)
        header = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, checksum, length)
        return header + data

    @staticmethod
    def extract(packet_bytes: bytes):
        if len(packet_bytes) < Packet.HEADER_SIZE:
            return None
        header = packet_bytes[:Packet.HEADER_SIZE]
        data = packet_bytes[Packet.HEADER_SIZE:]
        pkt_type, seq_num, ack_num, checksum, length = struct.unpack(Packet.HEADER_FORMAT, header)
        if length != len(data):
            return None
        sem_checksum = struct.pack(Packet.HEADER_FORMAT, pkt_type, seq_num, ack_num, 0, length)
        if Packet._checksum(sem_checksum + data) != checksum:
            return None
        return pkt_type, seq_num, ack_num, checksum, data

    @staticmethod
    def is_valid(packet_bytes: bytes) -> bool:
        return Packet.extract(packet_bytes) is not None