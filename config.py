"""
config.py — Configurações globais do sistema de inspeção 3D.

Centraliza todos os parâmetros ajustáveis em um único local,
facilitando manutenção e parametrização sem alterar a lógica.
"""

import os


class Config:
    """Configurações globais do sistema de inspeção 3D."""

    # ── Modos de operação padrão ─────────────────────────────────────────────
    MODO_SIMULADO   = False
    MODO_REFERENCIA = False

    # ── Parâmetros de inspeção ───────────────────────────────────────────────
    TOLERANCIA_PADRAO        = 3      # mm
    DISTANCIA_SENSOR_MESA    = 103.44 # mm  (distância do sensor à mesa sem peça)

    # ── Arquivos de dados ────────────────────────────────────────────────────
    ARQUIVO_REFERENCIA = "modelo_ok.xyz"

    # ── Simulação ────────────────────────────────────────────────────────────
    N_PONTOS_SIMULACAO = 2500
    N_PONTOS_STL_AMOSTRA = 8000
    RAIO_PADRAO   = 10   # mm
    ALTURA_PADRAO = 20   # mm

    # ── Comunicação serial ───────────────────────────────────────────────────
    BAUDRATE_SERIAL = 9600
    TIMEOUT_SERIAL  = 2   # segundos

    # ── ICP (Iterative Closest Point) ────────────────────────────────────────
    ICP_MAX_ITERACOES = 50
    ICP_TOLERANCIA    = 1e-6   # convergência mínima

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_DIR    = "logs"
    LOG_LEVEL  = "INFO"   # DEBUG | INFO | WARNING | ERROR

    # ── Defeitos e formas disponíveis ────────────────────────────────────────
    TIPOS_DEFEITOS = [
        "nenhum",
        "furo lateral",
        "furo superior",
        "amassado",
        "esticado",
        "falta de tampa",
        "quebrado",
    ]

    FORMAS_BASE = [
        "cilindro",
        "esfera",
    ]

    # ── Paleta de cores (tema escuro moderno) ────────────────────────────────
    cor_fundo             = "#1a1a2e"
    cor_fundo_secundario  = "#16213e"
    cor_texto             = "#eee"
    cor_texto_secundario  = "#a8b2d1"
    cor_principal         = "#00d9ff"
    cor_secundaria        = "#7b68ee"
    cor_sucesso           = "#00ffa3"
    cor_perigo            = "#ff006e"
    cor_destaque          = "#ffbe0b"
    cor_borda             = "#2d3561"

    # ── Cria pasta de logs ao importar ───────────────────────────────────────
    @classmethod
    def garantir_dirs(cls):
        os.makedirs(cls.LOG_DIR, exist_ok=True)
