"""Validação: o arquivo recebido é idêntico ao enviado
"""
import hashlib
from pathlib import Path


def sha256_arquivo(caminho) -> str:
    h = hashlib.sha256()
    with open(Path(caminho), "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()
