"""
Sistema de Inspeção 3D por Nuvem de Pontos

Este sistema compara peças físicas com modelos de referência usando
nuvens de pontos 3D capturadas por sensores ou geradas por simulação.

Autor: Yan de Lima Pereira
Data: 2025
"""

import numpy as np
import serial
import time
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.spatial import cKDTree, ConvexHull
from stl import mesh as stlmesh
import threading
import serial.tools.list_ports


# ===================== CONFIGURAÇÕES DO SISTEMA =====================
class Config:
    """Configurações globais do sistema de inspeção 3D."""

    # Modos de operação padrão
    MODO_SIMULADO = False
    MODO_REFERENCIA = False

    # Parâmetros de inspeção (em mm)
    TOLERANCIA_PADRAO = 3
    DISTANCIA_SENSOR_MESA = 103.44

    # Arquivos
    ARQUIVO_REFERENCIA = "modelo_ok.xyz"

    # Parâmetros de simulação
    N_PONTOS_SIMULACAO = 2500
    N_PONTOS_STL_AMOSTRA = 8000
    RAIO_PADRAO = 10  # mm
    ALTURA_PADRAO = 20  # mm

    # Comunicação serial
    BAUDRATE_SERIAL = 9600
    TIMEOUT_SERIAL = 2
    
    # Tipos de defeitos disponíveis para simulação
    TIPOS_DEFEITOS = [
        "nenhum",
        "furo lateral",
        "furo superior",
        "amassado",
        "esticado",
        "falta de tampa",
        "quebrado",
    ]

    # Formas geométricas base para simulação
    FORMAS_BASE = [
        "cilindro",
        "esfera"
    ]

    # Cores da interface (tema moderno escuro)
    cor_fundo = "#1a1a2e"
    cor_fundo_secundario = "#16213e"
    cor_texto = "#eee"
    cor_texto_secundario = "#a8b2d1"
    cor_principal = "#00d9ff"
    cor_secundaria = "#7b68ee"
    cor_sucesso = "#00ffa3"
    cor_perigo = "#ff006e"
    cor_destaque = "#ffbe0b"
    cor_borda = "#2d3561"




# ===================== CLASSE DE LÓGICA DE PROCESSAMENTO =====================
class Logica:
    """
    Classe responsável pelo processamento de nuvens de pontos 3D.

    Funcionalidades principais:
    - Gerar pontos 3D simulados (cilindros, esferas, com/sem defeitos)
    - Carregar e salvar arquivos STL e XYZ
    - Comparar nuvens de pontos e detectar defeitos
    - Exportar resultados para STL
    """

    def __init__(self, nome='Logica'):
        """
        Inicializa o processador de lógica.

        Args:
            nome (str): Identificador da instância para debug
        """
        self.nome = nome

    def _gerar_casca_3d(self, forma="cilindro", n_pontos=2000, raio=10, altura=10):
        """
        Gera pontos 3D na superfície de uma forma geométrica.

        Args:
            forma (str): Tipo de geometria ("cilindro" ou "esfera")
            n_pontos (int): Quantidade de pontos a gerar
            raio (float): Raio da forma em mm
            altura (float): Altura do cilindro em mm (ignorado para esfera)

        Returns:
            np.ndarray: Array (n_pontos, 3) com coordenadas XYZ
        """
        pontos = []

        if forma == "esfera":
            # Gera pontos na superfície de uma esfera usando coordenadas esféricas
            for _ in range(n_pontos):
                theta = np.random.uniform(0, 2 * np.pi)  # Ângulo azimutal
                phi = np.random.uniform(0, np.pi)  # Ângulo polar

                # Conversão de esféricas para cartesianas
                x = raio * np.sin(phi) * np.cos(theta)
                y = raio * np.sin(phi) * np.sin(theta)
                z = raio * np.cos(phi)
                pontos.append([x, y, z])

        else:  # cilindro
            # Gera pontos na superfície de um cilindro
            for _ in range(n_pontos):
                theta = np.random.uniform(0, 2 * np.pi)  # Ângulo ao redor do eixo
                h = np.random.uniform(-altura/2, altura/2)  # Altura ao longo do eixo Z

                # Conversão de cilíndricas para cartesianas
                x = raio * np.cos(theta)
                y = raio * np.sin(theta)
                z = h
                pontos.append([x, y, z])

        return np.array(pontos)

    def _gerar_pontos_simulados(self, defeito=False, tipo_defeito="nenhum",
                                seed=None, forma_base="cilindro"):
        """
        Gera uma nuvem de pontos simulada, opcionalmente com defeitos.

        Args:
            defeito (bool): Se True, aplica um defeito à geometria
            tipo_defeito (str): Tipo de defeito a aplicar (ver TIPOS_DEFEITOS)
            seed (int, optional): Semente para reprodutibilidade
            forma_base (str): Forma geométrica base ("cilindro" ou "esfera")

        Returns:
            np.ndarray: Nuvem de pontos 3D
        """
        if seed is not None:
            np.random.seed(seed)

        # Gera geometria base perfeita
        pontos = self._gerar_casca_3d(
            forma=forma_base,
            n_pontos=Config.N_PONTOS_SIMULACAO,
            raio=Config.RAIO_PADRAO,
            altura=Config.ALTURA_PADRAO
        )

        # Aplica defeito se solicitado
        if defeito and tipo_defeito != "nenhum":
            pontos = self._aplicar_defeito(pontos, tipo_defeito)

        return pontos

    def _aplicar_defeito(self, pontos, tipo_defeito):
        """
        Aplica um defeito específico à nuvem de pontos.

        Args:
            pontos (np.ndarray): Nuvem de pontos original
            tipo_defeito (str): Tipo de defeito a aplicar

        Returns:
            np.ndarray: Nuvem de pontos com defeito aplicado
        """
        if tipo_defeito == "furo lateral":
            # Remove pontos em uma região lateral (furo na parede)
            pontos = pontos[~((pontos[:,1]**2 + pontos[:,2]**2 < 9) & (pontos[:,0] > 0))]

        elif tipo_defeito == "furo superior":
            # Remove pontos na parte superior (furo no topo)
            pontos = pontos[~((pontos[:,0]**2 + pontos[:,1]**2 < 9) & (pontos[:,2] > 0))]

        elif tipo_defeito == "amassado":
            # Comprime a peça no eixo Z (amassamento)
            pontos[:,2] *= 0.5

        elif tipo_defeito == "esticado":
            # Estica a peça no eixo Z (alongamento)
            pontos[:,2] *= 1.5

        elif tipo_defeito == "falta de tampa":
            # Remove metade superior da peça
            z_med = np.median(pontos[:,2])
            pontos = pontos[pontos[:,2] < z_med]

        elif tipo_defeito == "quebrado":
            # Remove uma "fatia" lateral da peça
            pontos = pontos[pontos[:,0] > -2]

        return pontos

    def _carregar_stl(self, arquivo, n_amostras=None):
        """
        Carrega vértices de um arquivo STL e faz amostragem aleatória.

        Args:
            arquivo (str): Caminho do arquivo STL
            n_amostras (int, optional): Número de pontos a amostrar

        Returns:
            np.ndarray: Nuvem de pontos amostrada

        Raises:
            ValueError: Se o STL não contém vértices
        """
        if n_amostras is None:
            n_amostras = Config.N_PONTOS_STL_AMOSTRA

        # Carrega malha STL
        modelo = stlmesh.Mesh.from_file(arquivo)

        # Concatena todos os vértices dos triângulos (v0, v1, v2)
        pontos = np.concatenate([modelo.v0, modelo.v1, modelo.v2])

        if len(pontos) == 0:
            raise ValueError("Arquivo STL não contém vértices válidos.")

        # Amostragem aleatória para reduzir quantidade de pontos
        n_amostrar = min(n_amostras, len(pontos))
        idx = np.random.choice(len(pontos), size=n_amostrar, replace=False)

        return pontos[idx]
    
    def _salvar_nuvem_xyz(self, arquivo, pontos):
        """
        Salva nuvem de pontos em formato XYZ (texto simples).

        Args:
            arquivo (str): Caminho do arquivo de saída
            pontos (np.ndarray): Nuvem de pontos a salvar
        """
        with open(arquivo, 'w') as f:
            for p in pontos:
                f.write(f"{p[0]} {p[1]} {p[2]}\n")
    def _carregar_nuvem_xyz(self, arquivo):
        """
        Carrega nuvem de pontos de um arquivo XYZ.

        Args:
            arquivo (str): Caminho do arquivo XYZ

        Returns:
            np.ndarray: Nuvem de pontos carregada
        """
        pontos = []
        with open(arquivo, 'r') as f:
            for linha in f:
                parts = linha.strip().split()
                if len(parts) < 3:
                    continue
                x, y, z = parts[:3]
                pontos.append([float(x), float(y), float(z)])
        return np.array(pontos)
    
    def _exportar_stl_por_casco_convexo(self, pontos, caminho_saida):
        """
        Exporta nuvem de pontos como STL usando envoltória convexa.

        Args:
            pontos (np.ndarray): Nuvem de pontos
            caminho_saida (str): Caminho do arquivo STL de saída

        Raises:
            ValueError: Se não há pontos suficientes (mínimo 4)
        """
        if pontos is None or len(pontos) < 4:
            raise ValueError("São necessários pelo menos 4 pontos para gerar STL.")

        # Calcula envoltória convexa (triangulação)
        hull = ConvexHull(pontos)
        triangulos = hull.simplices  # Índices dos triângulos

        # Cria malha STL
        dados = np.zeros(len(triangulos), dtype=stlmesh.Mesh.dtype)
        malha = stlmesh.Mesh(dados, remove_empty_areas=False)

        # Preenche vértices de cada triângulo
        for i, (a, b, c) in enumerate(triangulos):
            malha.vectors[i] = np.array([pontos[a], pontos[b], pontos[c]])

        malha.save(caminho_saida)

    def _verificar_defeito(self, pontos_ref, pontos_teste, tol_mm):
        """
        Compara duas nuvens de pontos e identifica discrepâncias.

        Usa KD-Tree para encontrar vizinhos mais próximos e marcar pontos
        que excedem a tolerância especificada como defeituosos.

        Args:
            pontos_ref (np.ndarray): Nuvem de referência (modelo OK)
            pontos_teste (np.ndarray): Nuvem a inspecionar
            tol_mm (float): Tolerância máxima em mm

        Returns:
            tuple: (num_defeitos, cores_teste, cores_ref)
                - num_defeitos: contagem de pontos fora da tolerância
                - cores_teste: lista de cores ("red" ou "blue") para cada ponto teste
                - cores_ref: lista de cores para cada ponto referência

        Raises:
            ValueError: Se as nuvens estiverem vazias
        """
        # Validações de entrada
        if pontos_ref is None or len(pontos_ref) == 0:
            raise ValueError("Nuvem de referência está vazia")
        if pontos_teste is None or len(pontos_teste) == 0:
            raise ValueError("Nuvem de teste está vazia")
        if tol_mm <= 0:
            raise ValueError("Tolerância deve ser positiva")

        # Constrói árvores KD para busca eficiente de vizinhos
        tree_ref = cKDTree(pontos_ref)
        tree_teste = cKDTree(pontos_teste)

        # Distância de cada ponto teste ao ponto mais próximo da referência
        dist_teste, _ = tree_ref.query(pontos_teste)
        cores_teste = ["red" if d > tol_mm else "blue" for d in dist_teste]

        # Distância de cada ponto referência ao ponto mais próximo do teste
        dist_ref, _ = tree_teste.query(pontos_ref)
        cores_ref = ["red" if d > tol_mm else "blue" for d in dist_ref]

        # Conta total de pontos defeituosos (em ambas as direções)
        defeitos = int(np.sum(dist_teste > tol_mm) + np.sum(dist_ref > tol_mm))

        return defeitos, cores_teste, cores_ref


# ===================== CLASSE DE INTERFACE GRÁFICA =====================
class Interface:
    """
    Interface gráfica do sistema de inspeção 3D.

    Gerencia toda a interação com o usuário, incluindo:
    - Controles de modo (simulado/real, referência/teste)
    - Visualização 3D de nuvens de pontos
    - Comunicação com hardware (Arduino via serial)
    - Exportação de resultados
    """

    def __init__(self):
        """Inicializa a interface gráfica e seus componentes."""
        # Instância da lógica de processamento
        self.logica = Logica()

        # Estado interno da aplicação
        self.arquivo_stl_selecionado = None
        self.pontos_previa = None
        self.pontos_teste_ultimo = None
        self.pontos_ref_ultimo = None

        # Cria e exibe janela principal
        self._criar_janela_principal()

        # Inicia loop de eventos do Tkinter
        self.janela.mainloop()

    # ---------- Criação da janela principal ----------
    def _criar_janela_principal(self):
        """Configura a janela principal"""
        self.janela = tk.Tk()
        self.janela.title("🔍 Sistema de Inspeção 3D")
        self.janela.state('zoomed')
        self.janela.configure(bg=Config.cor_fundo)
        self.FONT_PADRAO = ("Segoe UI", 10)
        self.FONT_TITULO = ("Segoe UI", 11, "bold")
        
        # Configura estilo ttk para widgets modernos
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Customiza Combobox
        style.configure('TCombobox',
                       fieldbackground=Config.cor_fundo_secundario,
                       background=Config.cor_fundo_secundario,
                       foreground=Config.cor_texto,
                       borderwidth=0,
                       relief='flat')
        style.map('TCombobox',
                 fieldbackground=[('readonly', Config.cor_fundo_secundario)],
                 selectbackground=[('readonly', Config.cor_secundaria)])

        # Cria layout em colunas
        self._criar_colunas()
        self._criar_controle_esquerda()
        self._criar_coluna_direita()

        # Estado inicial dos controles
        self._atualizar_botoes_real_simulado()

    # ---------- Layout em colunas ----------
    def _criar_colunas(self):
        """Cria as colunas principais (controles à esquerda, visualização à direita)."""
        # Variáveis de controle vinculadas a widgets
        self.var_modo = tk.BooleanVar(value=Config.MODO_SIMULADO)
        self.var_referencia = tk.BooleanVar(value=Config.MODO_REFERENCIA)
        self.var_previa_fonte = tk.StringVar(value="real")
        self.var_previa_comparacao = tk.StringVar(value="Pré-Visualização")

        # Frame esquerdo: área com scroll
        frame_scroll_container = tk.Frame(self.janela, bg=Config.cor_fundo)
        frame_scroll_container.pack(side="left", fill="y", padx=15, pady=15)

        # Canvas para permitir scroll
        self.canvas_scroll = tk.Canvas(frame_scroll_container, bg=Config.cor_fundo, width=350, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame_scroll_container, orient="vertical", command=self.canvas_scroll.yview)

        # Frame que vai conter todos os controles
        self.coluna_esq = tk.Frame(self.canvas_scroll, bg=Config.cor_fundo, padx=5)

        # Cria uma "janela" no canvas que contém o frame
        self.canvas_scroll.create_window((0, 0), window=self.coluna_esq, anchor="nw")
        self.canvas_scroll.configure(yscrollcommand=scrollbar.set)

        # Empacota canvas e scrollbar
        self.canvas_scroll.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Atualiza região de scroll quando o tamanho mudar
        self.coluna_esq.bind("<Configure>", lambda e: self.canvas_scroll.configure(scrollregion=self.canvas_scroll.bbox("all")))

        # Adiciona scroll com roda do mouse
        def _on_mousewheel(event):
            self.canvas_scroll.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)

        # Frame direito: visualização 3D
        self.coluna_dir = tk.Frame(self.janela, bg=Config.cor_fundo)
        self.coluna_dir.pack(side="right", fill="both", expand=True, padx=15, pady=15)

    # ---------- Painel de controles (esquerda) ----------
    def _criar_controle_esquerda(self):
        """Cria todos os controles do painel esquerdo."""

        # ===== Seção: Modo de Operação =====
        self.frm_modo = tk.LabelFrame(
            self.coluna_esq,
            text=" 🔧 Modo de Operação ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=10
        )
        self.frm_modo.pack(fill="x", pady=(0, 8))

        self.label_modo = tk.Label(
            self.frm_modo,
            text=f"{'🖥️  Simulado' if self.var_modo.get() else '⚙️  Real'}",
            font=("Segoe UI", 11, "bold"),
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_destaque
        )
        self.label_modo.pack(pady=(0, 8))

        self.btn_alt = tk.Button(
            self.frm_modo,
            text="↔️  Alternar Modo",
            command=self._botao_alternar_modo,
            bg=Config.cor_secundaria,
            fg=Config.cor_texto,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            activebackground=Config.cor_principal,
            activeforeground=Config.cor_fundo
        )
        self.btn_alt.pack(pady=(0, 5), fill="x")

        # ===== Seção: Forma Base (modo simulado) =====
        self.frm_forma = tk.LabelFrame(
            self.coluna_esq,
            text=" 📐 Forma Base ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=10
        )
        self.combo_forma = ttk.Combobox(
            self.frm_forma,
            values=Config.FORMAS_BASE,
            state="readonly",
            font=self.FONT_PADRAO
        )
        self.combo_forma.pack(padx=5, pady=5, fill="x")
        self.combo_forma.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())
        self.combo_forma.set("cilindro")

        # ===== Seção: Seleção de Defeito (modo simulado) =====
        self.frm_defeito = tk.LabelFrame(
            self.coluna_esq,
            text=" ⚠️ Tipo de Defeito ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=10
        )
        self.combo_defeito = ttk.Combobox(
            self.frm_defeito,
            values=Config.TIPOS_DEFEITOS,
            state="readonly",
            font=self.FONT_PADRAO
        )
        self.combo_defeito.pack(padx=5, pady=5, fill="x")
        self.combo_defeito.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())
        self.combo_defeito.set("nenhum")

        # Mostra/oculta baseado no modo inicial
        if self.var_modo.get():  # Se simulado
            self.frm_forma.pack(fill="x", pady=(0, 8))
            self.frm_defeito.pack(fill="x", pady=(0, 8))

        # ===== Seção: Tolerância de Inspeção =====
        self.frm_tol = tk.LabelFrame(
            self.coluna_esq,
            text=" 📏 Tolerância (mm) ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=8
        )
        self.frm_tol.pack(fill="x", pady=(0, 8))

        self.slider_tolerancia = tk.Scale(
            self.frm_tol,
            from_=1,
            to=30,
            orient=tk.HORIZONTAL,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            troughcolor=Config.cor_borda,
            activebackground=Config.cor_principal,
            highlightthickness=0,
            borderwidth=0,
            font=self.FONT_PADRAO,
            length=250
        )
        self.slider_tolerancia.set(Config.TOLERANCIA_PADRAO)
        self.slider_tolerancia.pack(padx=5, pady=5, fill="x")

        # ===== Seção: Referência e STL =====
        self.frm_ref = tk.LabelFrame(
            self.coluna_esq,
            text=" 📁 Referência / STL ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=8
        )
        self.frm_ref.pack(fill="x", pady=(0, 8))

        self.chk_referencia = tk.Checkbutton(
            self.frm_ref,
            text="💾 Salvar como Referência",
            variable=self.var_referencia,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0
        )
        self.chk_referencia.pack(anchor="w", padx=5, pady=(0, 8))

        self.lbl_stl = tk.Label(
            self.frm_ref,
            text="Nenhum STL selecionado",
            wraplength=280,
            justify="left",
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto_secundario,
            font=("Segoe UI", 9)
        )
        self.lbl_stl.pack(fill="x", padx=5, pady=(0, 8))

        self.btn_sel_stl = tk.Button(
            self.frm_ref,
            text="📂 Carregar STL",
            command=self._selecionar_stl,
            bg=Config.cor_borda,
            fg=Config.cor_texto,
            font=self.FONT_PADRAO,
            borderwidth=0,
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
            activebackground=Config.cor_secundaria
        )
        self.btn_sel_stl.pack(padx=5, pady=(0, 5), fill="x")

        self.btn_limpa_stl = tk.Button(
            self.frm_ref,
            text="🗑️ Limpar STL",
            command=self._limpar_stl,
            bg=Config.cor_borda,
            fg=Config.cor_texto,
            font=self.FONT_PADRAO,
            borderwidth=0,
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
            activebackground=Config.cor_perigo
        )
        self.btn_limpa_stl.pack(padx=5, pady=(0, 5), fill="x")

        # ===== Seção: Fonte da Pré-visualização =====
        self.frm_prev_src = tk.LabelFrame(
            self.coluna_esq,
            text=" 👁️ Pré-visualização ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=8
        )
        self.frm_prev_src.pack(fill="x", pady=(0, 8))
        
        
        # ===== Seção: Modo de operação real =====
        self.modo_op_real = tk.LabelFrame(
            self.coluna_esq,
            text=" Modo de operação real ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=8
        )
        self.modo_op_real.pack(fill="x", pady=(0, 8))
        self._atualiza_alterar_modo_real()

        # ===== Botões de Exportação =====
        self.btn_exporta_previa_stl = tk.Button(
            self.coluna_esq,
            text="💾 Exportar STL da Prévia",
            command=self._acao_exportar_stl_previa,
            bg=Config.cor_borda,
            fg=Config.cor_texto,
            font=self.FONT_PADRAO,
            borderwidth=0,
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
            activebackground=Config.cor_secundaria
        )
        self.btn_exporta_previa_stl.pack(fill="x", pady=(0, 6))

        self.btn_exporta_teste_stl = tk.Button(
            self.coluna_esq,
            text="💾 Exportar STL do Teste",
            command=self._acao_exportar_stl_referencia,
            bg=Config.cor_borda,
            fg=Config.cor_texto,
            font=self.FONT_PADRAO,
            borderwidth=0,
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
            activebackground=Config.cor_secundaria
        )
        self.btn_exporta_teste_stl.pack(fill="x", pady=(0, 10))

        # ===== Botão Principal: Executar Inspeção =====
        self.btn_exec = tk.Button(
            self.coluna_esq,
            text="▶️  EXECUTAR INSPEÇÃO",
            font=("Segoe UI", 11, "bold"),
            command=self._executar,
            bg=Config.cor_principal,
            fg=Config.cor_fundo,
            borderwidth=0,
            relief="flat",
            padx=20,
            pady=12,
            cursor="hand2",
            activebackground=Config.cor_sucesso,
            activeforeground=Config.cor_fundo
        )
        self.btn_exec.pack(fill="x", pady=(0, 20))

    # ---------- Painel de visualização (direita) ----------
    def _criar_coluna_direita(self):
        """Cria o painel de visualização 3D."""
        self.frm_previa = tk.LabelFrame(
            self.coluna_dir,
            text=" 📊 Visualização 3D ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=10
        )
        self.frm_previa.pack(fill="both", expand=True)

        # Cria figura Matplotlib 3D com fundo escuro
        self.fig_previa = plt.Figure(figsize=(7, 7), facecolor=Config.cor_fundo_secundario)
        self.ax_previa = self.fig_previa.add_subplot(111, projection='3d')
        self.ax_previa.set_facecolor(Config.cor_fundo)

        # Integra com Tkinter
        self.canvas_previa = FigureCanvasTkAgg(self.fig_previa, master=self.frm_previa)
        self.canvas_previa.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # ---------- Atualização de controles ----------
    def _atualizar_botoes_real_simulado(self):
        """
        Atualiza os botões de rádio para seleção de fonte da pré-visualização.
        Chamado quando o modo é alternado ou a interface é inicializada.
        """
        # Remove widgets antigos
        for widget in self.frm_prev_src.winfo_children():
            widget.destroy()

        # Garante valor padrão
        if self.var_previa_fonte.get() == "":
            self.var_previa_fonte.set("simulado")

        # Cria botões de rádio
        self.selecao_simulado = tk.Radiobutton(
            self.frm_prev_src,
            text="🖥️  Simulado",
            variable=self.var_previa_fonte,
            value="simulado",
            command=self._atualizar_previa,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0,
            state="disabled"
        )
        self.selecao_simulado.pack(anchor="w", padx=5, pady=3)

        self.selecao_real = tk.Radiobutton(
            self.frm_prev_src,
            text="⚙️  Real",
            variable=self.var_previa_fonte,
            value="real",
            command=self._mostrar_peça_real,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0
        )
        self.selecao_real.pack(anchor="w", padx=5, pady=3)
            
        tk.Radiobutton(
            self.frm_prev_src,
            text="📁 STL Carregado",
            variable=self.var_previa_fonte,
            value="stl",
            command=self._atualizar_previa,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0
        ).pack(anchor="w", padx=5, pady=3)

    def _atualiza_alterar_modo_real(self):
        """Atualiza controles do modo de operação real."""
        # Remove widgets antigos
        for widget in self.modo_op_real.winfo_children():
            widget.destroy()

        # Garante valor padrão
        if self.var_previa_comparacao.get() == "":
            self.var_previa_comparacao.set("Pré-Visualização")

        # Cria botões de rádio

        self.selecao_pre_visu = tk.Radiobutton(
            self.modo_op_real,
            text="👁️ Pré-Visualização",
            variable=self.var_previa_comparacao,
            value="Pré-Visualização",
            command=self._atualizar_visualizacao_modo_real,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0
        )
        self.selecao_pre_visu.pack(anchor="w", padx=5, pady=3)

        self.selecao_comparacao = tk.Radiobutton(
            self.modo_op_real,
            text="🔍 Comparação",
            variable=self.var_previa_comparacao,
            value="Comparação",
            command=self._atualizar_visualizacao_modo_real,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0
        )
        self.selecao_comparacao.pack(anchor="w", padx=5, pady=3)

    def _atualizar_visualizacao_modo_real(self):
        """Atualiza a visualização com base no modo selecionado (Comparação ou Pré-visualização)."""
        modo = self.var_previa_comparacao.get()

        if modo == "Comparação":
            # Modo Comparação: mostra o modelo de referência
            if os.path.exists(Config.ARQUIVO_REFERENCIA):
                try:
                    pontos_ref = self.logica._carregar_nuvem_xyz(Config.ARQUIVO_REFERENCIA)
                    self._plot_nuvem(
                        self.ax_previa,
                        pontos_ref,
                        "Modelo de Referência (Comparação)"
                    )
                except Exception as e:
                    messagebox.showwarning(
                        "Aviso",
                        f"Não foi possível carregar a referência: {e}"
                    )
            else:
                messagebox.showinfo(
                    "Info",
                    "Nenhum modelo de referência encontrado.\nGere uma referência primeiro."
                )
                self.var_previa_comparacao.set("Pré-Visualização")
                self._atualizar_visualizacao_modo_real()
                self._plot_nuvem(
                    self.ax_previa,
                    None,
                    "Comparação - Sem referência"
                )

        elif modo == "Pré-Visualização":
            # Modo Pré-visualização: mostra a última peça real capturada
            if self.pontos_teste_ultimo is not None and len(self.pontos_teste_ultimo) > 0:
                self._plot_nuvem(
                    self.ax_previa,
                    self.pontos_teste_ultimo,
                    "Pré-visualização - Peça Real Capturada"
                )
            else:
                self._plot_nuvem(
                    self.ax_previa,
                    None,
                    "Pré-visualização - Nenhuma peça capturada ainda"
                )

    # ---------- Alternância de modo ----------
    def _botao_alternar_modo(self):
        
        """Alterna entre modo simulado e modo real."""
        # Inverte estado
        self.var_modo.set(not self.var_modo.get())
        self.label_modo.config(
            text=f"{'🖥️  Simulado' if self.var_modo.get() else '⚙️  Real'}"
        )
    
        # Mostra/oculta controles específicos do modo simulado
        if self.var_modo.get():
            # Modo simulado: mostra seleção de forma e defeito
            self.frm_forma.pack(after=self.frm_modo, fill="x", pady=(0, 8))
            self.frm_defeito.pack(after=self.frm_forma, fill="x", pady=(0, 8))
            
            # modo simulado: oculta controle de modo de operação real
            self.modo_op_real.pack_forget()
            
            self.var_previa_fonte.set("simulado")
            
        else:
            # Modo real: oculta controles de simulação
            self.frm_forma.pack_forget()
            self.frm_defeito.pack_forget()
            
            # modo real: mostra modo de operação real
            self.modo_op_real.pack(after=self.frm_prev_src, fill="x", pady=(0, 8))
            
            self.var_previa_fonte.set("real")
            self._atualiza_alterar_modo_real()
    
        # Atualiza interface (recria os radiobuttons)
        self._atualizar_botoes_real_simulado()
        
        if self.var_modo.get():
            # Modo simulado
            self.selecao_simulado.config(state="normal")
            self.selecao_real.config(state="disabled")
        else:
            # Modo real
            self.selecao_simulado.config(state="disabled")
            self.selecao_real.config(state="normal")
        
        # Atualiza visualização
        if self.var_previa_fonte.get() == "simulado":
            self._atualizar_previa()
        else:
            self._mostrar_peça_real()

    # ---------- Gerenciamento de arquivos STL ----------
    def _selecionar_stl(self):
        """Abre diálogo para selecionar arquivo STL."""
        caminho = filedialog.askopenfilename(
            title="Selecionar STL",
            filetypes=[("STL", "*.stl")]
        )
        if not caminho:
            return

        self.arquivo_stl_selecionado = caminho
        self.lbl_stl.config(text=f"STL: {os.path.basename(caminho)}")

        # Atualiza prévia se STL estiver selecionado como fonte
        if self.var_previa_fonte.get() == "stl":
           self._atualizar_previa()

    def _limpar_stl(self):
        """Remove seleção de arquivo STL."""
        self.arquivo_stl_selecionado = None
        self.lbl_stl.config(text="Nenhum STL selecionado")

        if self.var_previa_fonte.get() == "stl":
            self._atualizar_previa()

    # ---------- Visualização 3D ----------
    def _plot_nuvem(self, ax, pts, titulo=""):
        """
        Plota nuvem de pontos em um eixo 3D.

        Args:
            ax: Eixo Matplotlib 3D
            pts (np.ndarray): Nuvem de pontos (N, 3)
            titulo (str): Título do gráfico
        """
        ax.cla()  # Limpa gráfico anterior

        if pts is None or len(pts) == 0:
            # Mostra eixos vazios
            ax.set_title("(sem dados)")
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")
            self.canvas_previa.draw_idle()
            return

        # Plota pontos
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=1, c='cyan')

        # Ajusta limites dos eixos para manter proporções
        try:
            max_range = np.ptp(pts, axis=0).max()  # Maior variação entre eixos
            mid = pts.mean(axis=0)  # Centro da nuvem

            # Define limites simétricos ao redor do centro
            ax.set_xlim(mid[0] - max_range / 2, mid[0] + max_range / 2)
            ax.set_ylim(mid[1] - max_range / 2, mid[1] + max_range / 2)
            ax.set_zlim(mid[2] - max_range / 2, mid[2] + max_range / 2)
            ax.set_box_aspect((1, 1, 1))  # Proporção cúbica
        except Exception:
            pass

        # Configurações visuais
        ax.set_title(titulo if titulo else "", color=Config.cor_texto, fontsize=12, pad=15)
        ax.set_xlabel("X (mm)", color=Config.cor_texto_secundario, fontsize=10)
        ax.set_ylabel("Y (mm)", color=Config.cor_texto_secundario, fontsize=10)
        ax.set_zlabel("Z (mm)", color=Config.cor_texto_secundario, fontsize=10)
        ax.grid(True, alpha=0.2, color=Config.cor_borda)

        # Estilo dos eixos
        ax.tick_params(colors=Config.cor_texto_secundario, labelsize=8)
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor(Config.cor_borda)
        ax.yaxis.pane.set_edgecolor(Config.cor_borda)
        ax.zaxis.pane.set_edgecolor(Config.cor_borda)

        self.canvas_previa.draw_idle()

    # ---------- Atualização de pré-visualização ----------
    def _atualizar_previa(self):
        """
        Atualiza a pré-visualização 3D baseada na fonte selecionada.
        Pode mostrar: dados simulados, STL carregado, ou dados reais.
        """
        src = self.var_previa_fonte.get()
        forma_base = self.combo_forma.get() if hasattr(self, "combo_forma") else "cilindro"

        if src == "stl":
            # Fonte: arquivo STL
            if not self.arquivo_stl_selecionado:
                self.pontos_previa = None
                self._plot_nuvem(self.ax_previa, self.pontos_previa, "Nenhum STL carregado")
                return

            try:
                pts = self.logica._carregar_stl(self.arquivo_stl_selecionado)
                self.pontos_previa = pts
                self._plot_nuvem(
                    self.ax_previa,
                    self.pontos_previa,
                    f"Prévia do STL: {os.path.basename(self.arquivo_stl_selecionado)}"
                )
            except Exception as e:
                self.pontos_previa = None
                self._plot_nuvem(
                    self.ax_previa,
                    self.pontos_previa,
                    f"Erro ao carregar STL: {e}"
                )
        else:
            # Fonte: simulação
            tipo_def = self.combo_defeito.get() if hasattr(self, "combo_defeito") else "nenhum"
            pts = self.logica._gerar_pontos_simulados(
                defeito=(tipo_def != "nenhum"),
                tipo_defeito=tipo_def,
                seed=None,
                forma_base=forma_base
            )
            self.pontos_previa = pts
            self._plot_nuvem(
                self.ax_previa,
                self.pontos_previa,
                f"Prévia simulada — forma: {forma_base}, defeito: {tipo_def}"
            )

    def _mostrar_peça_real(self):
        """Mostra visualização baseada no modo selecionado."""
        if not self.var_modo.get():  # Se está no modo Real
            self._atualizar_visualizacao_modo_real()
        else:
            # Modo simulado - comportamento original
            pts = self.pontos_teste_ultimo
            if pts is None:
                self._plot_nuvem(self.ax_previa, None, "Prévia — Modo Real (sem dados)")
            else:
                self._plot_nuvem(self.ax_previa, pts, "Prévia — Peça Real")

        # ---------- Comunicação Serial ----------

    def _detectar_porta_arduino(self):
        """
        Detecta automaticamente a porta serial do Arduino.

        Returns:
            str: Nome da porta detectada, ou None se não encontrar
        """
        portas = list(serial.tools.list_ports.comports())

        if not portas:
            messagebox.showerror(
                "Erro",
                "Nenhuma porta serial detectada.\nConecte o Arduino e tente novamente."
            )
            return None

        # Procura por identificadores conhecidos do Arduino
        for p in portas:
            descricao = p.description.lower()
            if any(termo in descricao for termo in ["arduino", "ch340", "usb serial"]):
                return p.device

        # Se houver apenas uma porta, assume que é o Arduino
        if len(portas) == 1:
            return portas[0].device

        # Se múltiplas portas, mostra lista ao usuário
        lista = "\n".join([f"{p.device}: {p.description}" for p in portas])
        messagebox.showinfo("Portas encontradas", f"Portas encontradas:\n{lista}")
        return None

    def _conectar_serial(self, porta, baudrate, timeout):
        """
        Estabelece conexão serial com o Arduino.

        Args:
            porta (str): Nome da porta serial
            baudrate (int): Taxa de comunicação
            timeout (float): Timeout de leitura em segundos

        Returns:
            serial.Serial: Objeto de conexão serial

        Raises:
            serial.SerialException: Se falhar ao conectar
        """
        ser = serial.Serial(porta, baudrate, timeout=timeout)
        time.sleep(2)  # Aguarda inicialização do Arduino
        return ser

    def _processar_linha_serial(self, linha):
        """
        Processa uma linha de dados recebida do Arduino.

        Formato esperado: "camada|distancia|angulo_mesa|altura_fuso"

        Args:
            linha (str): Linha de texto do Arduino

        Returns:
            list: [x, y, z] em coordenadas cartesianas, ou None se inválido
        """
        if "|" not in linha:
            return None

        partes = linha.split("|")
        if len(partes) != 4:
            return None

        try:
            camada = int(partes[0])
            distancia = float(partes[1])
            angulo_mesa = float(partes[2])
            altura_fuso = float(partes[3])

            # Raio real do objeto (centro até superfície)
            raio = Config.DISTANCIA_SENSOR_MESA - distancia

            # Conversão polar → cartesiana
            theta = np.radians(angulo_mesa)
            x = raio * np.cos(theta)
            y = raio * np.sin(theta)
            z = altura_fuso

            return [x, y, z]

        except ValueError:
            return None

    def _ler_dados_thread(self, porta=None, baudrate=None, timeout=None, callback=None):
        """
        Lê dados do Arduino em uma thread separada para não travar a UI.

        Args:
            porta (str, optional): Porta serial (auto-detecta se None)
            baudrate (int, optional): Taxa de comunicação
            timeout (float, optional): Timeout de leitura
            callback (callable, optional): Função a chamar quando terminar a leitura
        """
        if baudrate is None:
            baudrate = Config.BAUDRATE_SERIAL
        if timeout is None:
            timeout = Config.TIMEOUT_SERIAL

        def tarefa():
            """Função executada na thread de leitura."""
            pontos = []

            # Detecta porta se não especificada
            porta_detectada = porta or self._detectar_porta_arduino()
            if not porta_detectada:
                return

            try:
                # Conecta ao Arduino
                with serial.Serial(porta_detectada, baudrate, timeout=timeout) as ser:
                    time.sleep(2)  # Aguarda estabilização

                    # Loop de leitura
                    while True:
                        linha = ser.readline().decode(errors="ignore").strip()
                        if not linha:
                            continue

                        # Verifica fim da transmissão
                        if linha.upper() == "FIM":
                            break

                        # Processa linha de dados
                        ponto = self._processar_linha_serial(linha)
                        if ponto:
                            pontos.append(ponto)

            except serial.SerialException as e:
                self.janela.after(0,lambda err=e: messagebox.showerror(
                    "Erro",
                    f"Erro na porta {porta_detectada}: {err}"
                    )
                )
                return

            # Converte para numpy array
            pts_arr = np.array(pontos)

            # Guarda no estado da aplicação
            self.pontos_teste_ultimo = pts_arr

            # Atualiza GUI na thread principal
            self.janela.after(0, lambda: self._atualizar_previa_com_pontos(pts_arr))

            # Chama callback se fornecido (para continuar a execução)
            if callback and len(pts_arr) > 0:
                self.janela.after(0, callback)

        # Inicia thread daemon (termina com a aplicação)
        thread = threading.Thread(target=tarefa, daemon=True)
        thread.start()

    def _atualizar_previa_com_pontos(self, pontos):
        """
        Atualiza visualização com novos pontos capturados.

        Args:
            pontos (np.ndarray): Nuvem de pontos a exibir
        """
        self._plot_nuvem(self.ax_previa, pontos, titulo="Coleta em tempo real")

    # ---------- Execução Principal ----------
    def _executar(self):
        """
        Executa inspeção ou salva modelo de referência.

        Fluxo:
        1. Se modo referência: salva modelo atual como referência
        2. Se modo teste: compara com referência e mostra resultado
        """
        # Lê configurações atuais da UI
        self.modo_referencia = self.var_referencia.get()
        self.modo_simulado = self.var_modo.get()
        self.tolerancia_mm = self.slider_tolerancia.get()
        self.tipo_def = self.combo_defeito.get()
        self.forma = self.combo_forma.get()

        # ===== MODO REFERÊNCIA: Salvar modelo OK =====
        if self.modo_referencia:
            pontos = self._obter_pontos_para_referencia()
            if pontos is None:
                return

            self._salvar_referencia(pontos)
            return

        # ===== MODO TESTE: Comparar com referência =====
        if self.modo_simulado:
            pontos_ref = self._carregar_referencia()
            if pontos_ref is None:
                return
    
            pontos_teste = self._obter_pontos_para_teste()
            if pontos_teste is None:
                return
    
            self._comparar_e_exibir_resultado(pontos_ref, pontos_teste)
            print(self.var_previa_comparacao)

    def _obter_pontos_para_referencia(self):
        """
        Obtém pontos para salvar como referência.

        Returns:
            np.ndarray: Nuvem de pontos, ou None em caso de erro
        """
        # Se há STL selecionado, usa ele
        if self.arquivo_stl_selecionado:
            try:
                return self.logica._carregar_stl(self.arquivo_stl_selecionado)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao carregar STL: {e}")
                return None

        # Senão, usa simulação ou leitura real
        if self.modo_simulado:
            tem_defeito = (self.tipo_def != "nenhum")
            return self.logica._gerar_pontos_simulados(
                defeito=tem_defeito,
                tipo_defeito=self.tipo_def if tem_defeito else "nenhum",
                seed=np.random.randint(0, 999999),
                forma_base=self.forma
            )
        else:
            # Modo real: inicia leitura do sensor com callback para salvar após leitura
            messagebox.showinfo("Leitura", "Iniciando leitura do sensor...\nAguarde até receber 'FIM' do Arduino.")
            self._ler_dados_thread(callback=self._callback_salvar_referencia)
            return None

    def _callback_salvar_referencia(self):
        """Callback chamado após leitura real completar (modo referência)."""
        if self.pontos_teste_ultimo is not None and len(self.pontos_teste_ultimo) > 0:
            self._salvar_referencia(self.pontos_teste_ultimo)

    def _salvar_referencia(self, pontos):
        """
        Salva pontos como modelo de referência.

        Args:
            pontos (np.ndarray): Nuvem de pontos a salvar
        """
        if pontos is None or len(pontos) == 0:
            messagebox.showerror("Erro", "Nenhum ponto foi gerado para salvar como referência.")
            return

        try:
            self.logica._salvar_nuvem_xyz(Config.ARQUIVO_REFERENCIA, pontos)
            self.pontos_ref_ultimo = np.copy(pontos)
            self._atualizar_previa_com_pontos(self.pontos_ref_ultimo)

            msg = "com defeito" if (self.tipo_def != "nenhum") else "sem defeito"
            messagebox.showinfo("Referência", f"Modelo de referência salvo ({msg}).")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar referência: {e}")

    def _carregar_referencia(self):
        """
        Carrega modelo de referência do arquivo.

        Returns:
            np.ndarray: Nuvem de pontos de referência, ou None se falhar
        """
        if not os.path.exists(Config.ARQUIVO_REFERENCIA):
            messagebox.showerror(
                "Erro",
                "Arquivo de referência não encontrado. Gere uma referência primeiro."
            )
            return None

        try:
            pontos_ref = self.logica._carregar_nuvem_xyz(Config.ARQUIVO_REFERENCIA)
            self.pontos_ref_ultimo = pontos_ref
            return pontos_ref
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao ler referência: {e}")
            return None

    def _obter_pontos_para_teste(self):
        """
        Obtém pontos da peça a inspecionar.

        Returns:
            np.ndarray: Nuvem de pontos, ou None se leitura em andamento
        """
        if self.modo_simulado:
            tem_defeito = (self.tipo_def != "nenhum")
            pontos_teste = self.logica._gerar_pontos_simulados(
                defeito=tem_defeito,
                tipo_defeito=self.tipo_def if tem_defeito else "nenhum",
                seed=np.random.randint(0, 999999),
                forma_base=self.forma
            )
            self.pontos_teste_ultimo = np.copy(pontos_teste)
            self._atualizar_previa_com_pontos(self.pontos_teste_ultimo)
            return pontos_teste
        else:
            # Modo real: inicia leitura com callback para comparar após leitura
            messagebox.showinfo("Leitura", "Iniciando leitura do sensor...\nAguarde até receber 'FIM' do Arduino.")
            self._ler_dados_thread(callback=self._callback_comparar_teste)
            return None

    def _callback_comparar_teste(self):
        """Callback chamado após leitura real completar (modo teste)."""
        if self.pontos_teste_ultimo is not None and len(self.pontos_teste_ultimo) > 0:
            # Carrega referência novamente
            pontos_ref = self._carregar_referencia()
            if pontos_ref is not None:
                self._comparar_e_exibir_resultado(pontos_ref, self.pontos_teste_ultimo)

    def _comparar_e_exibir_resultado(self, pontos_ref, pontos_teste):
        """
        Compara nuvens de pontos e exibe resultado da inspeção.

        Args:
            pontos_ref (np.ndarray): Modelo de referência
            pontos_teste (np.ndarray): Peça inspecionada
        """
        try:
            defeitos, cores_teste, cores_ref = self.logica._verificar_defeito(
                np.copy(pontos_ref),
                np.copy(pontos_teste),
                self.tolerancia_mm
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Falha na verificação: {e}")
            return

        # Determina resultado
        resultado = "❌ PEÇA COM DEFEITO" if defeitos > 0 else "✅ PEÇA APROVADA"
        messagebox.showinfo("Resultado", f"Defeitos detectados: {defeitos}\n{resultado}")

        # Abre janela de visualização comparativa
        self._abrir_janela_visualizacao(
            pontos_teste, cores_teste,
            pontos_ref, cores_ref
        )

    # ---------- Janela de Visualização Comparativa ----------
    def _abrir_janela_visualizacao(self, pontos_teste, cores_teste, pontos_ref, cores_ref):
        """
        Abre janela secundária mostrando comparação lado a lado.

        Args:
            pontos_teste (np.ndarray): Pontos da peça testada
            cores_teste (list): Cores de cada ponto (vermelho=defeito, azul=ok)
            pontos_ref (np.ndarray): Pontos da referência
            cores_ref (list): Cores de cada ponto da referência
        """
        janela_vis = tk.Toplevel(self.janela)
        janela_vis.title("Comparação Visual")
        janela_vis.geometry("1000x520")

        # Cria figura com 2 subplots 3D
        fig = plt.Figure(figsize=(10, 5))

        # Subplot 1: Peça Teste
        ax1 = fig.add_subplot(121, projection='3d')
        ax1.scatter(
            pontos_teste[:, 0],
            pontos_teste[:, 1],
            pontos_teste[:, 2],
            c=cores_teste,
            s=2
        )
        ax1.set_title("Peça TESTE")
        ax1.set_box_aspect((1, 1, 1))

        # Subplot 2: Peça Referência
        ax2 = fig.add_subplot(122, projection='3d')
        ax2.scatter(
            pontos_ref[:, 0],
            pontos_ref[:, 1],
            pontos_ref[:, 2],
            c=cores_ref,
            s=2
        )
        ax2.set_title("Peça REFERÊNCIA")
        ax2.set_box_aspect((1, 1, 1))

        # Integra com Tkinter
        canvas = FigureCanvasTkAgg(fig, master=janela_vis)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------- Exportações ----------
    def _acao_exportar_stl_previa(self):
        """Exporta pontos da pré-visualização como arquivo STL."""
        if self.pontos_previa is None or len(self.pontos_previa) == 0:
            messagebox.showwarning("Exportar STL", "Não há pontos na prévia para exportar.")
            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar STL da prévia",
            defaultextension=".stl",
            filetypes=[("STL", "*.stl")]
        )
        if not caminho:
            return

        try:
            self.logica._exportar_stl_por_casco_convexo(self.pontos_previa, caminho)
            messagebox.showinfo("Exportar STL", f"STL salvo em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Exportar STL", f"Falha ao exportar STL: {e}")

    def _acao_exportar_stl_referencia(self):
        """Exporta pontos do último teste como arquivo STL."""
        if self.pontos_teste_ultimo is None or len(self.pontos_teste_ultimo) == 0:
            messagebox.showwarning("Exportar STL", "Execute um teste antes para gerar pontos.")
            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar STL do teste",
            defaultextension=".stl",
            filetypes=[("STL", "*.stl")]
        )
        if not caminho:
            return

        try:
            self.logica._exportar_stl_por_casco_convexo(self.pontos_teste_ultimo, caminho)
            messagebox.showinfo("Exportar STL", f"STL salvo em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Exportar STL", f"Falha ao exportar STL: {e}")


# ===================== PONTO DE ENTRADA =====================
if __name__ == "__main__":
    """Inicializa a aplicação."""
    app = Interface()