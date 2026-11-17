import re, sys
from pathlib import Path
import markdown

md_path = Path(sys.argv[1]).resolve()
html_path = Path(sys.argv[2]).resolve()
texto = md_path.read_text(encoding="utf-8")

# o cabeçalho tem 3 linhas seguidas: força quebra de linha entre elas
texto = re.sub(r"^(\*\*(?:Disciplina|Grupo 3|Entrega):\*\*.*)$", r"\1  ", texto, flags=re.M)
# sublistas com 2 espaços (o python-markdown exige 4)
texto = re.sub(r"^  ([-*] )", r"    \1", texto, flags=re.M)
# sumário logo depois do primeiro separador
texto = texto.replace("\n---\n", "\n---\n\n<div class=\"sumario-titulo\">Sumário</div>\n\n[TOC]\n\n---\n", 1)

md = markdown.Markdown(
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
    extension_configs={"toc": {"title": "", "toc_depth": "2-2", "permalink": False}},
)
corpo = md.convert(texto)

css = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
html { font-size: 10.5pt; }
body { font-family: 'DejaVu Serif', Georgia, 'Times New Roman', serif; line-height: 1.45; color: #111; }
h1 { font-size: 22pt; margin: 0 0 6mm; line-height: 1.2; }
h2 { font-size: 15pt; margin: 0 0 4mm; padding-bottom: 1.5mm; border-bottom: 1px solid #999; page-break-after: avoid; }
.sumario-titulo { font-size: 15pt; font-weight: bold; margin: 6mm 0 4mm; padding-bottom: 1.5mm; border-bottom: 1px solid #999; }
h3 { font-size: 12pt; margin: 6mm 0 2mm; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
hr { display: none; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.6pt; background: #f2f2f2; padding: 0 1px; }
pre { background: #f5f5f5; border: 1px solid #ddd; padding: 2.5mm; font-size: 8pt; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8pt; }
table { page-break-inside: avoid; border-collapse: collapse; width: 100%; margin: 3mm 0 4mm; font-size: 8.8pt; }
tr { page-break-inside: avoid; }
thead { display: table-header-group; }
th, td { border: 1px solid #999; padding: 1.2mm 2mm; text-align: left; vertical-align: top; overflow-wrap: break-word; }
th { background: #e9eef5; }
img { max-width: 100%; max-height: 62mm; display: block; margin: 3mm auto; page-break-inside: avoid; }
em { color: #333; }
.toc ul { list-style: none; padding-left: 5mm; margin: 0; }
.toc > ul { padding-left: 0; }
.toc li { margin: 0.6mm 0; }
.toc a { color: #111; text-decoration: none; }
a { color: #0b4f9c; word-break: break-all; }
"""
base = (md_path.parent).as_uri() + "/"
html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<base href="{base}"><title>Laboratório de Transporte Confiável: Relatório Técnico</title>
<style>{css}</style></head><body>{corpo}</body></html>"""
html_path.write_text(html, encoding="utf-8")
print("html:", html_path, len(html), "bytes")
