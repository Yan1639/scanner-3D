"""
serial_comm.py — Comunicação serial com o Arduino.

Responsabilidades:
  • Detecção automática da porta serial
  • Leitura de dados do sensor em thread separada
  • Conversão de coordenadas polares → cartesianas
  • Sinalização de fim de leitura via callback

Autor : Yan de Lima Pereira
Versão: 2.0
"""

import logging
import threading
import time
import numpy as np

try:
    import serial
    import serial.tools.list_ports
    SERIAL_DISPONIVEL = True
except ImportError:
    SERIAL_DISPONIVEL = False

from config import Config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Detecção e conexão
# ─────────────────────────────────────────────────────────────────────────────

def detectar_porta_arduino() -> str | None:
    """
    Detecta automaticamente a porta serial do Arduino.

    Estratégia:
      1. Busca por descrição conhecida (arduino / ch340 / usb serial)
      2. Se única porta disponível, assume que é o Arduino
      3. Caso contrário retorna None e loga lista encontrada

    Returns:
        str com nome da porta, ou None se não encontrada
    """
    if not SERIAL_DISPONIVEL:
        logger.error("pyserial não instalado — modo serial indisponível")
        return None

    portas = list(serial.tools.list_ports.comports())
    if not portas:
        logger.warning("Nenhuma porta serial detectada")
        return None

    for p in portas:
        descricao = p.description.lower()
        if any(t in descricao for t in ("arduino", "ch340", "usb serial")):
            logger.info("Arduino detectado em %s (%s)", p.device, p.description)
            return p.device

    if len(portas) == 1:
        logger.info("Única porta disponível: %s — assumindo Arduino", portas[0].device)
        return portas[0].device

    logger.warning(
        "Múltiplas portas encontradas, nenhuma identificada como Arduino: %s",
        [p.device for p in portas],
    )
    return None


def _processar_linha(linha: str) -> list[float] | None:
    """
    Converte linha serial do Arduino em ponto 3D cartesiano.

    Protocolo: ``"camada|distancia|angulo_mesa|altura_fuso"``

    Returns:
        [x, y, z] em mm, ou None se a linha for inválida
    """
    if "|" not in linha:
        return None

    partes = linha.split("|")
    if len(partes) != 4:
        return None

    try:
        distancia    = float(partes[1])
        angulo_mesa  = float(partes[2])
        altura_fuso  = float(partes[3])

        raio  = Config.DISTANCIA_SENSOR_MESA - distancia
        theta = np.radians(angulo_mesa)
        x     = raio * np.cos(theta)
        y     = raio * np.sin(theta)
        z     = altura_fuso

        return [x, y, z]
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Leitura em background
# ─────────────────────────────────────────────────────────────────────────────

def ler_dados_async(
    callback_pontos,
    callback_erro=None,
    porta: str | None = None,
    baudrate: int | None = None,
    timeout: float | None = None,
) -> threading.Thread:
    """
    Inicia leitura serial em thread daemon para não bloquear a UI.

    Args:
        callback_pontos : ``f(np.ndarray)`` — chamado na thread principal via janela.after
        callback_erro   : ``f(str)``        — chamado em caso de falha serial
        porta           : Porta serial (auto-detecta se None)
        baudrate        : Taxa de comunicação (padrão: Config.BAUDRATE_SERIAL)
        timeout         : Timeout de leitura em segundos

    Returns:
        Thread iniciada (daemon=True)
    """
    if baudrate is None:
        baudrate = Config.BAUDRATE_SERIAL
    if timeout is None:
        timeout = Config.TIMEOUT_SERIAL

    def _tarefa():
        pontos = []
        porta_alvo = porta or detectar_porta_arduino()

        if not porta_alvo:
            msg = "Porta do Arduino não encontrada. Verifique a conexão."
            logger.error(msg)
            if callback_erro:
                callback_erro(msg)
            return

        try:
            logger.info("Conectando em %s @ %d baud…", porta_alvo, baudrate)
            with serial.Serial(porta_alvo, baudrate, timeout=timeout) as ser:
                time.sleep(2)   # Aguarda reset do Arduino
                logger.info("Conexão estabelecida — aguardando dados…")

                while True:
                    linha = ser.readline().decode(errors="ignore").strip()
                    if not linha:
                        continue
                    if linha.upper() == "FIM":
                        logger.info("Sinal FIM recebido — leitura concluída")
                        break

                    ponto = _processar_linha(linha)
                    if ponto:
                        pontos.append(ponto)

        except serial.SerialException as e:
            msg = f"Erro na porta {porta_alvo}: {e}"
            logger.error(msg)
            if callback_erro:
                callback_erro(msg)
            return

        pts_arr = np.array(pontos) if pontos else np.empty((0, 3))
        logger.info("Leitura serial finalizada — %d pontos capturados", len(pts_arr))
        callback_pontos(pts_arr)

    t = threading.Thread(target=_tarefa, daemon=True)
    t.start()
    return t
