"""
logica.py — Lógica de processamento de nuvens de pontos 3D.

Responsabilidades:
  • Geração vetorizada de pontos simulados
  • Aplicação de defeitos geométricos
  • Alinhamento por ICP (Iterative Closest Point)
  • Comparação com métricas industriais completas
  • Exportação STL (casco convexo e Delaunay aprimorado)
  • I/O de arquivos XYZ e STL

Autor : Yan de Lima Pereira
Versão: 2.0
"""

import logging
import numpy as np
from scipy.spatial import cKDTree, ConvexHull, Delaunay

try:
    from stl import mesh as stlmesh
    STL_DISPONIVEL = True
except ImportError:
    stlmesh = None
    STL_DISPONIVEL = False

from config import Config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Geração de geometria
# ─────────────────────────────────────────────────────────────────────────────

def _gerar_casca_cilindro(n_pontos: int, raio: float, altura: float) -> np.ndarray:
    """
    Gera N pontos na superfície de um cilindro (vetorizado com NumPy).

    Complexidade: O(N) — sem loop Python, muito mais rápido para 100k+ pontos.
    """
    theta = np.random.uniform(0, 2 * np.pi, n_pontos)
    z     = np.random.uniform(-altura / 2, altura / 2, n_pontos)
    x     = raio * np.cos(theta)
    y     = raio * np.sin(theta)
    return np.column_stack([x, y, z])


def _gerar_casca_esfera(n_pontos: int, raio: float) -> np.ndarray:
    """
    Gera N pontos uniformes na superfície de uma esfera (vetorizado).

    Usa amostragem por rejeição → distribuição uniforme garantida.
    """
    # Método de Marsaglia: pontos uniformes em esfera unitária
    pts = []
    while len(pts) < n_pontos:
        u = np.random.uniform(-1, 1, (n_pontos * 2, 3))
        norma = np.linalg.norm(u, axis=1, keepdims=True)
        mask  = (norma[:, 0] <= 1) & (norma[:, 0] > 0)
        u     = u[mask] / norma[mask]
        pts.extend(u.tolist())
    pts = np.array(pts[:n_pontos]) * raio
    return pts


def gerar_casca_3d(
    forma: str = "cilindro",
    n_pontos: int = 2000,
    raio: float = 10,
    altura: float = 20,
) -> np.ndarray:
    """
    Gera pontos na superfície de uma forma geométrica (todo vetorizado).

    Args:
        forma    : "cilindro" ou "esfera"
        n_pontos : Quantidade de pontos
        raio     : Raio em mm
        altura   : Altura do cilindro em mm (ignorado para esfera)

    Returns:
        np.ndarray (n_pontos, 3)
    """
    if forma == "esfera":
        return _gerar_casca_esfera(n_pontos, raio)
    return _gerar_casca_cilindro(n_pontos, raio, altura)


# ─────────────────────────────────────────────────────────────────────────────
# Aplicação de defeitos
# ─────────────────────────────────────────────────────────────────────────────

def _aplicar_defeito(pontos: np.ndarray, tipo_defeito: str) -> np.ndarray:
    """Aplica defeito geométrico à nuvem de pontos (vetorizado)."""

    if tipo_defeito == "furo lateral":
        angulo = np.arctan2(pontos[:, 1], pontos[:, 0])
        mask = (np.abs(angulo) < 0.3) & (pontos[:, 2] > -3) & (pontos[:, 2] < 3)
        pontos = pontos[~mask]

    elif tipo_defeito == "furo superior":
        mask = (pontos[:, 0] ** 2 + pontos[:, 1] ** 2 < 9) & (pontos[:, 2] > 0)
        pontos = pontos[~mask]

    elif tipo_defeito == "amassado":
        pontos = pontos.copy()
        pontos[:, 2] *= 0.5

    elif tipo_defeito == "esticado":
        pontos = pontos.copy()
        pontos[:, 2] *= 1.5

    elif tipo_defeito == "falta de tampa":
        z_med  = np.median(pontos[:, 2])
        pontos = pontos[pontos[:, 2] < z_med]

    elif tipo_defeito == "quebrado":
        pontos = pontos[pontos[:, 0] > -2]

    return pontos


def gerar_pontos_simulados(
    defeito: bool = False,
    tipo_defeito: str = "nenhum",
    seed: int | None = None,
    forma_base: str = "cilindro",
) -> np.ndarray:
    """
    Gera nuvem de pontos simulada, opcionalmente com defeito.

    Args:
        defeito     : Se True aplica o defeito escolhido
        tipo_defeito: Identificador do defeito (ver Config.TIPOS_DEFEITOS)
        seed        : Semente para reprodutibilidade
        forma_base  : "cilindro" ou "esfera"

    Returns:
        np.ndarray (N, 3)
    """
    if seed is not None:
        np.random.seed(seed)

    pontos = gerar_casca_3d(
        forma=forma_base,
        n_pontos=Config.N_PONTOS_SIMULACAO,
        raio=Config.RAIO_PADRAO,
        altura=Config.ALTURA_PADRAO,
    )

    if defeito and tipo_defeito != "nenhum":
        pontos = _aplicar_defeito(pontos, tipo_defeito)

    logger.debug("Gerados %d pontos (forma=%s, defeito=%s)", len(pontos), forma_base, tipo_defeito)
    return pontos


# ─────────────────────────────────────────────────────────────────────────────
# Alinhamento ICP  (Iterative Closest Point)
# ─────────────────────────────────────────────────────────────────────────────

def icp(
    origem: np.ndarray,
    alvo: np.ndarray,
    max_iter: int = None,
    tol: float = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Alinha 'origem' contra 'alvo' usando ICP ponto-a-ponto.

    Sem alinhamento prévio, diferenças de rotação ou translação podem
    gerar falsos positivos na inspeção. O ICP corrige esse problema.

    Algoritmo:
      1. Encontra correspondências (vizinho mais próximo via KDTree)
      2. Calcula a transformação rígida ótima (SVD)
      3. Aplica transformação e verifica convergência
      4. Repete até convergir ou esgotar iterações

    Args:
        origem  : Nuvem a transformar  (N, 3)
        alvo    : Nuvem de referência  (M, 3)
        max_iter: Número máximo de iterações
        tol     : Tolerância de convergência

    Returns:
        (origem_alinhada, matriz_rotacao_4x4, erro_final_mm)
    """
    if max_iter is None:
        max_iter = Config.ICP_MAX_ITERACOES
    if tol is None:
        tol = Config.ICP_TOLERANCIA

    src = origem.copy().astype(np.float64)
    dst = alvo.astype(np.float64)

    T_acum = np.eye(4)   # Transformação acumulada
    erro_anterior = np.inf

    tree_dst = cKDTree(dst)

    for i in range(max_iter):
        # 1 — Correspondências
        dist, idx = tree_dst.query(src)
        correspondentes = dst[idx]

        erro = float(np.mean(dist))

        # 2 — Convergência
        if abs(erro_anterior - erro) < tol:
            logger.debug("ICP convergiu em %d iterações (erro=%.6f mm)", i, erro)
            break
        erro_anterior = erro

        # 3 — Transformação rígida ótima (Umeyama / SVD)
        c_src = src.mean(axis=0)
        c_dst = correspondentes.mean(axis=0)

        A = (src - c_src).T @ (correspondentes - c_dst)
        U, _, Vt = np.linalg.svd(A)

        # Garante rotação própria (det = +1)
        D = np.diag([1, 1, np.linalg.det(Vt.T @ U.T)])
        R = Vt.T @ D @ U.T
        t = c_dst - R @ c_src

        # 4 — Aplica
        src = (R @ src.T).T + t

        # Acumula na transformação 4x4
        T = np.eye(4)
        T[:3, :3] = R
        T[:3,  3] = t
        T_acum = T @ T_acum

    else:
        logger.warning("ICP atingiu o limite de %d iterações sem convergir", max_iter)

    return src, T_acum, erro


# ─────────────────────────────────────────────────────────────────────────────
# Comparação com métricas industriais
# ─────────────────────────────────────────────────────────────────────────────

def verificar_defeito(
    pontos_ref: np.ndarray,
    pontos_teste: np.ndarray,
    tol_mm: float,
    usar_icp: bool = True,
) -> dict:
    """
    Compara duas nuvens de pontos e retorna métricas industriais completas.

    O ICP é aplicado antes da comparação para eliminar falsos positivos
    causados por deslocamento/rotação da peça na mesa de inspeção.

    Métricas retornadas:
      - n_defeitos    : Total de pontos fora da tolerância (bidirecional)
      - pct_defeito   : Percentual da peça fora da tolerância
      - dist_media    : Distância média entre nuvens (mm)
      - dist_max      : Distância máxima detectada (mm)
      - dist_std      : Desvio padrão das distâncias
      - cores_teste   : Lista de cores por ponto ("red" / "blue")
      - cores_ref     : Lista de cores por ponto referência
      - dist_teste    : Array de distâncias para cada ponto teste (heatmap)
      - dist_ref      : Array de distâncias para cada ponto referência
      - erro_icp      : Erro residual após alinhamento ICP (mm)
      - aprovada      : bool — True se nenhum defeito detectado

    Args:
        pontos_ref  : Modelo de referência OK (M, 3)
        pontos_teste: Peça a inspecionar (N, 3)
        tol_mm      : Tolerância máxima em mm
        usar_icp    : Aplica ICP antes de comparar (recomendado)

    Returns:
        dict com todas as métricas listadas acima

    Raises:
        ValueError: Se as nuvens forem inválidas
    """
    if pontos_ref is None or len(pontos_ref) == 0:
        raise ValueError("Nuvem de referência está vazia")
    if pontos_teste is None or len(pontos_teste) == 0:
        raise ValueError("Nuvem de teste está vazia")
    if tol_mm <= 0:
        raise ValueError("Tolerância deve ser positiva")

    erro_icp = 0.0

    # ── Alinhamento ICP ─────────────────────────────────────────────────────
    if usar_icp:
        logger.info("Executando ICP para alinhar nuvens...")
        pontos_teste, _, erro_icp = icp(pontos_teste, pontos_ref)
        logger.info("ICP concluído — erro residual: %.4f mm", erro_icp)

    # ── Comparação bidirecional com KDTree ──────────────────────────────────
    tree_ref   = cKDTree(pontos_ref)
    tree_teste = cKDTree(pontos_teste)

    dist_teste, _ = tree_ref.query(pontos_teste)   # cada ponto teste → ref mais próximo
    dist_ref,   _ = tree_teste.query(pontos_ref)   # cada ponto ref   → teste mais próximo

    # ── Métricas ─────────────────────────────────────────────────────────────
    n_def_teste = int(np.sum(dist_teste > tol_mm))
    n_def_ref   = int(np.sum(dist_ref   > tol_mm))
    n_defeitos  = n_def_teste + n_def_ref

    total_pontos = len(dist_teste) + len(dist_ref)
    pct_defeito  = 100.0 * n_defeitos / total_pontos if total_pontos > 0 else 0.0

    todas_dist  = np.concatenate([dist_teste, dist_ref])
    dist_media  = float(np.mean(todas_dist))
    dist_max    = float(np.max(todas_dist))
    dist_std    = float(np.std(todas_dist))

    cores_teste = ["red" if d > tol_mm else "blue" for d in dist_teste]
    cores_ref   = ["red" if d > tol_mm else "blue" for d in dist_ref]

    resultado = {
        "n_defeitos"  : n_defeitos,
        "pct_defeito" : pct_defeito,
        "dist_media"  : dist_media,
        "dist_max"    : dist_max,
        "dist_std"    : dist_std,
        "cores_teste" : cores_teste,
        "cores_ref"   : cores_ref,
        "dist_teste"  : dist_teste,
        "dist_ref"    : dist_ref,
        "erro_icp"    : erro_icp,
        "aprovada"    : n_defeitos == 0,
    }

    logger.info(
        "Inspeção concluída — defeitos=%d (%.1f%%) | dist_med=%.3f mm | dist_max=%.3f mm",
        n_defeitos, pct_defeito, dist_media, dist_max,
    )
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# I/O de arquivos
# ─────────────────────────────────────────────────────────────────────────────

def carregar_stl(arquivo: str, n_amostras: int | None = None) -> np.ndarray:
    """
    Carrega vértices de um arquivo STL com amostragem aleatória.

    Args:
        arquivo   : Caminho do arquivo .stl
        n_amostras: Nº de pontos a amostrar (None → usa Config)

    Returns:
        np.ndarray (N, 3)

    Raises:
        ValueError: STL sem vértices
        ImportError: numpy-stl não instalado
    """
    if not STL_DISPONIVEL:
        raise ImportError("numpy-stl não instalado. Execute: pip install numpy-stl")

    if n_amostras is None:
        n_amostras = Config.N_PONTOS_STL_AMOSTRA

    modelo = stlmesh.Mesh.from_file(arquivo)
    pontos = np.concatenate([modelo.v0, modelo.v1, modelo.v2])

    if len(pontos) == 0:
        raise ValueError("Arquivo STL não contém vértices válidos.")

    n = min(n_amostras, len(pontos))
    idx = np.random.choice(len(pontos), size=n, replace=False)
    logger.debug("STL carregado: %d pontos amostrados de %s", n, arquivo)
    return pontos[idx]


def salvar_xyz(arquivo: str, pontos: np.ndarray) -> None:
    """Salva nuvem de pontos em formato XYZ (texto simples)."""
    np.savetxt(arquivo, pontos, fmt="%.6f", delimiter=" ")
    logger.info("XYZ salvo: %s (%d pontos)", arquivo, len(pontos))


def carregar_xyz(arquivo: str) -> np.ndarray:
    """Carrega nuvem de pontos de um arquivo XYZ."""
    pontos = np.loadtxt(arquivo)
    if pontos.ndim == 1:
        pontos = pontos.reshape(1, -1)
    logger.debug("XYZ carregado: %d pontos de %s", len(pontos), arquivo)
    return pontos


# ─────────────────────────────────────────────────────────────────────────────
# Exportação STL aprimorada
# ─────────────────────────────────────────────────────────────────────────────

def exportar_stl_convexo(pontos: np.ndarray, caminho: str) -> None:
    """
    Exporta como STL usando envoltória convexa (rápido, forma simples).

    Limitação: ignora cavidades internas. Adequado para peças convexas.
    """
    if not STL_DISPONIVEL:
        raise ImportError("numpy-stl não instalado. Execute: pip install numpy-stl")
    if pontos is None or len(pontos) < 4:
        raise ValueError("Mínimo de 4 pontos necessários para STL.")

    hull  = ConvexHull(pontos)
    tris  = hull.simplices
    dados = np.zeros(len(tris), dtype=stlmesh.Mesh.dtype)
    malha = stlmesh.Mesh(dados, remove_empty_areas=False)

    for i, (a, b, c) in enumerate(tris):
        malha.vectors[i] = np.array([pontos[a], pontos[b], pontos[c]])

    malha.save(caminho)
    logger.info("STL (convexo) salvo: %s", caminho)


def exportar_stl_delaunay(pontos: np.ndarray, caminho: str) -> None:
    """
    Exporta STL usando triangulação de Delaunay em 2.5D (projeção XY).

    Vantagens sobre casco convexo:
      • Mantém forma real da base da peça
      • Melhor para formas não-convexas com variação em Z
      • Não colapsa concavidades laterais

    Nota: Para reconstrução de superfícies complexas com cavidades
    3D completas, considere usar Open3D com Poisson Reconstruction.
    """
    if not STL_DISPONIVEL:
        raise ImportError("numpy-stl não instalado. Execute: pip install numpy-stl")
    if pontos is None or len(pontos) < 4:
        raise ValueError("Mínimo de 4 pontos necessários para STL.")

    # Triangulação Delaunay sobre a projeção XY
    tri  = Delaunay(pontos[:, :2])
    tris = tri.simplices

    # Filtra triângulos degenerados (área muito pequena)
    tris_validos = []
    for t in tris:
        pts_t = pontos[t]
        v1    = pts_t[1] - pts_t[0]
        v2    = pts_t[2] - pts_t[0]
        area  = 0.5 * np.linalg.norm(np.cross(v1, v2))
        if area > 1e-6:
            tris_validos.append(t)

    tris = np.array(tris_validos)
    if len(tris) == 0:
        raise ValueError("Nenhum triângulo válido gerado.")

    dados = np.zeros(len(tris), dtype=stlmesh.Mesh.dtype)
    malha = stlmesh.Mesh(dados, remove_empty_areas=False)

    for i, (a, b, c) in enumerate(tris):
        malha.vectors[i] = np.array([pontos[a], pontos[b], pontos[c]])

    malha.save(caminho)
    logger.info("STL (Delaunay) salvo: %s (%d triângulos)", caminho, len(tris))
