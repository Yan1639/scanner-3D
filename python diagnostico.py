"""
diagnostico.py — Verifica dependências e testa a inicialização do sistema.

Execute com:  python diagnostico.py
"""

import sys
import traceback

print("=" * 55)
print("  DIAGNÓSTICO — Sistema de Inspeção 3D")
print("=" * 55)

erros = []

# ── 1. Python ──────────────────────────────────────────────────────────
print(f"\n[✓] Python {sys.version.split()[0]}")

# ── 2. Dependências ────────────────────────────────────────────────────
deps = [
    ("tkinter",             "tkinter"),
    ("numpy",               "numpy"),
    ("matplotlib",          "matplotlib"),
    ("scipy",               "scipy"),
    ("serial (pyserial)",   "serial"),
    ("numpy-stl",           "stl"),
]

print("\n── Dependências ──────────────────────────────────────")
for nome, modulo in deps:
    try:
        __import__(modulo)
        print(f"  [✓] {nome}")
    except ImportError as e:
        print(f"  [✗] {nome}  →  {e}")
        erros.append(f"pip install {modulo if modulo != 'stl' else 'numpy-stl'}")

# ── 3. Arquivos do projeto ─────────────────────────────────────────────
import os
print("\n── Arquivos do projeto ───────────────────────────────")
for arq in ["main.py", "interface.py", "logica.py", "serial_comm.py", "config.py"]:
    existe = os.path.exists(arq)
    print(f"  {'[✓]' if existe else '[✗]'} {arq}")
    if not existe:
        erros.append(f"Arquivo ausente: {arq}")

# ── 4. Import de cada módulo ───────────────────────────────────────────
print("\n── Imports dos módulos do projeto ────────────────────")
for mod in ["config", "logica", "serial_comm"]:
    try:
        __import__(mod)
        print(f"  [✓] {mod}")
    except Exception as e:
        print(f"  [✗] {mod}  →  {e}")
        erros.append(f"Erro ao importar {mod}: {e}")

# ── 5. Teste do tkinter (janela mínima) ────────────────────────────────
print("\n── Teste de janela tkinter ───────────────────────────")
try:
    import tkinter as tk
    root = tk.Tk()
    root.title("Teste")
    root.geometry("200x80")
    tk.Label(root, text="Tkinter OK — feche esta janela").pack(pady=20)
    print("  [✓] Janela de teste criada — feche para continuar")
    root.mainloop()
    print("  [✓] mainloop() encerrado normalmente")
except Exception as e:
    print(f"  [✗] Falha no tkinter: {e}")
    erros.append(f"Tkinter: {e}")

# ── 6. Import completo da interface ────────────────────────────────────
print("\n── Import de interface.py ────────────────────────────")
try:
    import interface
    print("  [✓] interface.py importado sem erros")
except Exception as e:
    print(f"  [✗] {e}")
    traceback.print_exc()
    erros.append(f"interface.py: {e}")

# ── Resumo ─────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if erros:
    print("  PROBLEMAS ENCONTRADOS:")
    for e in erros:
        print(f"    → {e}")
    print("\n  Corrija os itens acima e rode main.py novamente.")
else:
    print("  Tudo OK — tente rodar main.py normalmente.")
print("=" * 55)