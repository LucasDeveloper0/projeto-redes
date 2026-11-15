"""Validação de integridade da transferência (SHA-256).

Requisito do roteiro: provar que o arquivo recebido é IDÊNTICO ao enviado.
Calculamos o hash SHA-256 dos dois arquivos; se forem iguais, nenhum byte foi
perdido, duplicado, trocado de ordem ou corrompido, mesmo com o canal falhando.
Este módulo é usado pelos três protocolos (rdt3.0, GBN e SR) e pelos testes.
"""
import hashlib
from pathlib import Path


def sha256_arquivo(caminho) -> str:
    """Devolve o SHA-256 (em hexadecimal) do arquivo em `caminho`."""
    h = hashlib.sha256()
    with open(Path(caminho), "rb") as f:
        # Lê em blocos de 64 KB: funciona com arquivos grandes sem carregá-los
        # inteiros na memória. O hash final é o mesmo de ler tudo de uma vez.
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()
