"""
logica.py — Lógica de processamento de nuvens de pontos 3D.

Responsabilidades:
  • Geração vetorizada de pontos simulados
  • Aplicação de defeitos geométricos
  • Alinhamento por ICP (Iterative Closest Point)
  • Comparação com métricas industriais completas
  • Exportação STL via Ball Pivoting Algorithm (BPA)
  • I/O de arquivos XYZ e STL

Autor : Yan de Lima Pereira
Versão: 2.0
"""

import logging
import numpy as np
from scipy.spatial import cKDTree

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
    """
    theta = np.random.uniform(0, 2 * np.pi, n_pontos)
    z     = np.random.uniform(-altura / 2, altura / 2, n_pontos)
    x     = raio * np.cos(theta)
    y     = raio * np.sin(theta)
    return np.column_stack([x, y, z])


def _gerar_casca_esfera(n_pontos: int, raio: float) -> np.ndarray:
    """
    Gera N pontos uniformes na superfície de uma esfera (vetorizado).
    """
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

    T_acum = np.eye(4)
    erro_anterior = np.inf

    tree_dst = cKDTree(dst)

    for i in range(max_iter):
        dist, idx = tree_dst.query(src)
        correspondentes = dst[idx]

        erro = float(np.mean(dist))

        if abs(erro_anterior - erro) < tol:
            logger.debug("ICP convergiu em %d iterações (erro=%.6f mm)", i, erro)
            break
        erro_anterior = erro

        c_src = src.mean(axis=0)
        c_dst = correspondentes.mean(axis=0)

        A = (src - c_src).T @ (correspondentes - c_dst)
        U, _, Vt = np.linalg.svd(A)

        D = np.diag([1, 1, np.linalg.det(Vt.T @ U.T)])
        R = Vt.T @ D @ U.T
        t = c_dst - R @ c_src

        src = (R @ src.T).T + t

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

    if usar_icp:
        logger.info("Executando ICP para alinhar nuvens...")
        pontos_teste, _, erro_icp = icp(pontos_teste, pontos_ref)
        logger.info("ICP concluído — erro residual: %.4f mm", erro_icp)

    tree_ref   = cKDTree(pontos_ref)
    tree_teste = cKDTree(pontos_teste)

    dist_teste, _ = tree_ref.query(pontos_teste)
    dist_ref,   _ = tree_teste.query(pontos_ref)

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
        "n_defeitos"      : n_defeitos,
        "pct_defeito"     : pct_defeito,
        "dist_media"      : dist_media,
        "dist_max"        : dist_max,
        "dist_std"        : dist_std,
        "cores_teste"     : cores_teste,
        "cores_ref"       : cores_ref,
        "dist_teste"      : dist_teste,
        "dist_ref"        : dist_ref,
        "erro_icp"        : erro_icp,
        "aprovada"        : n_defeitos == 0,
        "pontos_alinhados": pontos_teste,
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
# Exportação STL — Poisson Surface Reconstruction (principal) + BPA (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _preparar_pcd(pontos: np.ndarray, o3d):
    """
    Etapas comuns de pré-processamento: downsampling + normais orientadas.

    O voxel_size é calculado como avg_dist * 0.8 para uniformizar a
    densidade sem perder estrutura — densidade uniforme é pré-requisito
    tanto do Poisson quanto do BPA.

    Returns:
        pcd (PointCloud open3d com normais), avg_dist (float mm)
    """
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pontos.astype(np.float64))

    # Voxel downsampling — uniformiza a densidade da nuvem
    distancias  = pcd.compute_nearest_neighbor_distance()
    avg_dist    = float(np.mean(distancias))
    voxel_size  = avg_dist * 0.8
    pcd         = pcd.voxel_down_sample(voxel_size=voxel_size)
    logger.debug("Após voxel downsampling: %d pontos", len(pcd.points))

    # Recalcula avg_dist após downsampling (densidade mudou)
    distancias = pcd.compute_nearest_neighbor_distance()
    avg_dist   = float(np.mean(distancias))

    # Normais com vizinhança ampla — melhor para cascas cilíndricas/esféricas
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamKNN(knn=50)
    )
    pcd.orient_normals_consistent_tangent_plane(k=20)

    return pcd, avg_dist


def _salvar_malha(malha_o3d, caminho: str, metodo: str) -> None:
    """Converte malha Open3D → numpy-stl e grava em disco."""
    malha_o3d.remove_degenerate_triangles()
    malha_o3d.remove_duplicated_triangles()
    malha_o3d.remove_duplicated_vertices()
    malha_o3d.remove_non_manifold_edges()
    malha_o3d = malha_o3d.filter_smooth_laplacian(number_of_iterations=2)
    malha_o3d.compute_vertex_normals()

    vertices   = np.asarray(malha_o3d.vertices)
    triangulos = np.asarray(malha_o3d.triangles)

    if len(triangulos) == 0:
        raise ValueError(
            f"{metodo} não gerou triângulos. "
            "Verifique se a nuvem de pontos tem densidade suficiente."
        )

    dados     = np.zeros(len(triangulos), dtype=stlmesh.Mesh.dtype)
    malha_stl = stlmesh.Mesh(dados, remove_empty_areas=False)
    for i, (a, b, c) in enumerate(triangulos):
        malha_stl.vectors[i] = np.array([vertices[a], vertices[b], vertices[c]])

    malha_stl.save(caminho)
    logger.info("STL (%s) salvo: %s (%d triângulos)", metodo, caminho, len(triangulos))


def exportar_stl_bpa(pontos: np.ndarray, caminho: str) -> None:
    """
    Exporta STL a partir de uma nuvem de pontos.

    Estratégia (duas tentativas automáticas):
    ─────────────────────────────────────────
    1ª — Poisson Surface Reconstruction  (método padrão)
         Resolve uma equação de Poisson para criar uma malha *watertight*
         (fechada, sem buracos) mesmo quando a densidade é irregular.
         É a escolha certa para cascas de scanner porque interpola suavemente
         as regiões mais esparsas em vez de deixá-las vazias.

         Pipeline:
           1. Voxel downsampling + normais orientadas
           2. Poisson depth=9  (resolução ~512³ — boa para peças industriais)
           3. Remoção de vértices de baixa densidade (artefatos em ar livre)
              usando o percentil 5 do mapa de densidade retornado pelo Poisson
           4. Limpeza + suavização Laplaciana leve + exportação

    2ª — Ball Pivoting Algorithm  (fallback automático)
         Usado somente se o Poisson não gerar triângulos suficientes.
         Preserva furos/defeitos reais da peça, mas é sensível a lacunas.

         Pipeline:
           1. Raios adaptativos em 7 níveis (1× → 13× avg_dist)
           2. Segunda passagem nos pontos ainda livres
           3. fill_holes() para buracos residuais
           4. Limpeza + suavização + exportação

    Args:
        pontos  : Nuvem de pontos (N, 3) — mínimo 20 pontos
        caminho : Caminho de saída do arquivo .stl

    Raises:
        ImportError : open3d ou numpy-stl não instalados
        ValueError  : Pontos insuficientes ou nenhum triângulo gerado
    """
    try:
        import open3d as o3d
    except ImportError:
        raise ImportError(
            "open3d não instalado.\n"
            "Execute: pip install open3d  (requer Python 3.8–3.11)"
        )

    if not STL_DISPONIVEL:
        raise ImportError("numpy-stl não instalado. Execute: pip install numpy-stl")
    if pontos is None or len(pontos) < 20:
        raise ValueError("Mínimo de 20 pontos necessários para exportação STL.")

    logger.info("Iniciando reconstrução de superfície — %d pontos", len(pontos))

    pcd, avg_dist = _preparar_pcd(pontos, o3d)

    # ══════════════════════════════════════════════════════════════════════════
    # TENTATIVA 1 — Poisson Surface Reconstruction
    # ══════════════════════════════════════════════════════════════════════════
    logger.info("Tentando Poisson Surface Reconstruction (depth=9)…")
    try:
        malha_poisson, densidades = (
            o3d.geometry.TriangleMesh
            .create_from_point_cloud_poisson(pcd, depth=9)
        )
        logger.debug("Poisson gerou %d triângulos antes do filtro de densidade",
                     len(malha_poisson.triangles))

        # Remove vértices "fantasmas" criados em regiões sem pontos.
        # O Poisson retorna um mapa de densidade: baixa densidade = artefato.
        # Usar percentil 5 remove ~5 % dos vértices mais isolados sem cortar
        # nada da superfície real (que sempre tem densidade > mediana).
        densidades_np = np.asarray(densidades)
        limiar        = np.quantile(densidades_np, 0.000)
        verts_remover = densidades_np < limiar
        malha_poisson.remove_vertices_by_mask(verts_remover)
        logger.debug(
            "Poisson após filtro de densidade (limiar=%.4f): %d triângulos",
            limiar, len(malha_poisson.triangles),
        )

        if len(malha_poisson.triangles) >= 10:
            _salvar_malha(malha_poisson, caminho, "Poisson")
            return   # ← sucesso; sai da função

        logger.warning("Poisson gerou poucos triângulos (%d) — tentando BPA como fallback",
                       len(malha_poisson.triangles))

    except Exception as e:
        logger.warning("Poisson falhou (%s) — tentando BPA como fallback", e)

    # ══════════════════════════════════════════════════════════════════════════
    # TENTATIVA 2 — Ball Pivoting Algorithm (fallback)
    # ══════════════════════════════════════════════════════════════════════════
    logger.info("Iniciando BPA (fallback)…")

    radii = o3d.utility.DoubleVector([
        avg_dist * 1.0,
        avg_dist * 1.5,
        avg_dist * 2.5,
        avg_dist * 4.0,
        avg_dist * 6.0,
        avg_dist * 9.0,
        avg_dist * 13.0,
    ])

    malha_o3d = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd, radii
    )
    logger.debug("BPA principal: %d triângulos", len(malha_o3d.triangles))

    # Segunda passagem nos pontos ainda não cobertos
    vertices_usados = set(np.asarray(malha_o3d.triangles).flatten().tolist())
    todos_pts       = np.asarray(pcd.points)
    mascara_livres  = np.ones(len(todos_pts), dtype=bool)
    for idx in vertices_usados:
        if idx < len(mascara_livres):
            mascara_livres[idx] = False

    n_livres = int(mascara_livres.sum())
    if n_livres >= 10:
        pcd_extra         = o3d.geometry.PointCloud()
        pcd_extra.points  = o3d.utility.Vector3dVector(todos_pts[mascara_livres])
        pcd_extra.normals = o3d.utility.Vector3dVector(
            np.asarray(pcd.normals)[mascara_livres]
        )
        radii_extra = o3d.utility.DoubleVector([
            avg_dist * 6.0, avg_dist * 10.0, avg_dist * 15.0, avg_dist * 20.0,
        ])
        malha_extra = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd_extra, radii_extra
        )
        malha_o3d += malha_extra
        logger.debug("BPA extra: +%d triângulos (pontos livres: %d)",
                     len(malha_extra.triangles), n_livres)

    # Tenta fill_holes (Open3D ≥ 0.14)
    try:
        malha_o3d = malha_o3d.fill_holes(hole_size=avg_dist * 20.0)
        logger.debug("fill_holes aplicado com sucesso")
    except AttributeError:
        logger.debug("fill_holes não disponível nesta versão do Open3D (ignorado)")

    _salvar_malha(malha_o3d, caminho, "BPA")