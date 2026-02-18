"""
main.py — Ponto de entrada do Sistema de Inspeção 3D.

Responsabilidades:
  • Configurar logging para console e arquivo rotativo
  • Garantir criação de diretórios necessários
  • Instanciar e iniciar a interface gráfica

Uso:
    python main.py

Autor : Yan de Lima Pereira
Versão: 2.0
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime

# ── Garante que o diretório do script está no path ────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import Config


# ─────────────────────────────────────────────────────────────────────────────
# Configuração de logging
# ─────────────────────────────────────────────────────────────────────────────

def configurar_logging() -> None:
    """
    Configura logging para:
      • Console (INFO) — feedback imediato ao desenvolvedor
      • Arquivo rotativo diário em logs/ — rastreabilidade industrial

    Formato: ``[2026-02-18 14:03:22] [INFO    ] logica — ICP convergiu em 12 it.``
    """
    Config.garantir_dirs()

    nivel = getattr(logging, Config.LOG_LEVEL, logging.INFO)
    fmt   = "[%(asctime)s] [%(levelname)-8s] %(name)s — %(message)s"
    date  = "%Y-%m-%d %H:%M:%S"

    # ── Handler de console ────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=date))

    # ── Handler de arquivo rotativo (1 arquivo por dia, mantém 30 dias) ───────
    data_str  = datetime.now().strftime("%Y_%m_%d")
    log_path  = os.path.join(Config.LOG_DIR, f"inspecao_{data_str}.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(nivel)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=date))

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(nivel)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "Logging inicializado — arquivo: %s (nível: %s)", log_path, Config.LOG_LEVEL
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entrada
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    configurar_logging()

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Sistema de Inspeção 3D v2.0 — iniciando")
    logger.info("=" * 60)

    try:
        from interface import Interface
        Interface()
    except Exception as e:
        logger.critical("Falha crítica ao iniciar a aplicação: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
