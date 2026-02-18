"""
interface.py — Interface gráfica do Sistema de Inspeção 3D.

Responsabilidades:
  • Layout e controles Tkinter
  • Visualização 3D com Matplotlib
  • Janela de resultados com mapa de calor, histograma e métricas
  • Delegação de processamento para logica.py e serial_comm.py

Autor : Yan de Lima Pereira
Versão: 2.0
"""

import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D   # noqa: F401

import logica
import serial_comm
from config import Config

logger = logging.getLogger(__name__)


class Interface:
    """Interface gráfica do sistema de inspeção 3D."""

    # ─────────────────────────────────────────────────────────────────────────
    # Inicialização
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self):
        self.arquivo_stl_selecionado = None
        self.pontos_previa           = None
        self.pontos_teste_ultimo     = None
        self.pontos_ref_ultimo       = None
        self._ultimo_resultado       = None   # dict de métricas da última inspeção

        self._criar_janela_principal()
        self.janela.mainloop()

    # ─────────────────────────────────────────────────────────────────────────
    # Janela principal
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_janela_principal(self):
        self.janela = tk.Tk()
        self.janela.title("🔍 Sistema de Inspeção 3D v2.0")
        self.janela.state("zoomed")
        self.janela.configure(bg=Config.cor_fundo)

        self.FONT_PADRAO = ("Segoe UI", 10)
        self.FONT_TITULO = ("Segoe UI", 11, "bold")

        # ── Estilo ttk ───────────────────────────────────────────────────────
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "TCombobox",
            fieldbackground=Config.cor_fundo_secundario,
            background=Config.cor_fundo_secundario,
            foreground=Config.cor_texto,
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Config.cor_fundo_secundario)],
            selectbackground=[("readonly", Config.cor_secundaria)],
        )

        self._criar_variaveis()
        self._criar_layout()
        self._atualizar_botoes_modo()

    def _criar_variaveis(self):
        self.var_modo            = tk.BooleanVar(value=Config.MODO_SIMULADO)
        self.var_referencia      = tk.BooleanVar(value=Config.MODO_REFERENCIA)
        self.var_previa_fonte    = tk.StringVar(value="real")
        self.var_previa_comparacao = tk.StringVar(value="Pré-Visualização")

    # ─────────────────────────────────────────────────────────────────────────
    # Layout em colunas
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_layout(self):
        # ── Coluna esquerda com scroll ────────────────────────────────────────
        cont_scroll = tk.Frame(self.janela, bg=Config.cor_fundo)
        cont_scroll.pack(side="left", fill="y", padx=15, pady=15)

        self.canvas_scroll = tk.Canvas(
            cont_scroll, bg=Config.cor_fundo, width=360, highlightthickness=0
        )
        scrollbar = tk.Scrollbar(
            cont_scroll, orient="vertical", command=self.canvas_scroll.yview
        )
        self.coluna_esq = tk.Frame(self.canvas_scroll, bg=Config.cor_fundo, padx=5)
        self.canvas_scroll.create_window((0, 0), window=self.coluna_esq, anchor="nw")
        self.canvas_scroll.configure(yscrollcommand=scrollbar.set)
        self.coluna_esq.bind(
            "<Configure>",
            lambda e: self.canvas_scroll.configure(
                scrollregion=self.canvas_scroll.bbox("all")
            ),
        )
        self.canvas_scroll.pack(side="left", fill="y", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── Coluna direita: visualização ──────────────────────────────────────
        self.coluna_dir = tk.Frame(self.janela, bg=Config.cor_fundo)
        self.coluna_dir.pack(side="left", fill="both", expand=True, padx=(0, 15), pady=15)

        self._criar_controles_esquerda()
        self._criar_painel_direita()

    # ─────────────────────────────────────────────────────────────────────────
    # Controles (coluna esquerda)
    # ─────────────────────────────────────────────────────────────────────────

    def _lf(self, texto, icone=""):
        """Cria um LabelFrame padronizado."""
        return tk.LabelFrame(
            self.coluna_esq,
            text=f" {icone} {texto} " if icone else f" {texto} ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=8,
        )

    def _btn(self, parent, texto, cmd, cor_bg=None, cor_fg=None):
        """Cria botão padronizado."""
        return tk.Button(
            parent,
            text=texto,
            command=cmd,
            bg=cor_bg or Config.cor_borda,
            fg=cor_fg or Config.cor_texto,
            font=self.FONT_PADRAO,
            borderwidth=0,
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
            activebackground=Config.cor_principal,
            activeforeground=Config.cor_fundo,
        )

    def _criar_controles_esquerda(self):
        # ── Modo (simulado / real) ────────────────────────────────────────────
        self.frm_modo = self._lf("Modo de Operação", "⚙️")
        self.frm_modo.pack(fill="x", pady=(0, 8))

        self.label_modo = tk.Label(
            self.frm_modo,
            text="🖥️  Simulado" if self.var_modo.get() else "⚙️  Real",
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_destaque,
            font=self.FONT_TITULO,
        )
        self.label_modo.pack(pady=(0, 6))

        tk.Button(
            self.frm_modo,
            text="↔️  Alternar Modo",
            command=self._alternar_modo,
            bg=Config.cor_secundaria,
            fg=Config.cor_texto,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            activebackground=Config.cor_principal,
            activeforeground=Config.cor_fundo,
        ).pack(fill="x")

        # ── Forma base (simulado) ─────────────────────────────────────────────
        self.frm_forma = self._lf("Forma Base", "📐")
        self.combo_forma = ttk.Combobox(
            self.frm_forma, values=Config.FORMAS_BASE, state="readonly", font=self.FONT_PADRAO
        )
        self.combo_forma.set("cilindro")
        self.combo_forma.pack(fill="x", padx=5, pady=5)
        self.combo_forma.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())

        # ── Tipo de defeito (simulado) ────────────────────────────────────────
        self.frm_defeito = self._lf("Tipo de Defeito", "⚠️")
        self.combo_defeito = ttk.Combobox(
            self.frm_defeito,
            values=Config.TIPOS_DEFEITOS,
            state="readonly",
            font=self.FONT_PADRAO,
        )
        self.combo_defeito.set("nenhum")
        self.combo_defeito.pack(fill="x", padx=5, pady=5)
        self.combo_defeito.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())

        if self.var_modo.get():
            self.frm_forma.pack(fill="x", pady=(0, 8))
            self.frm_defeito.pack(fill="x", pady=(0, 8))

        # ── Tolerância ────────────────────────────────────────────────────────
        frm_tol = self._lf("Tolerância", "📏")
        frm_tol.pack(fill="x", pady=(0, 8))
        self.slider_tolerancia = tk.Scale(
            frm_tol,
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
            length=260,
            label="mm",
        )
        self.slider_tolerancia.set(Config.TOLERANCIA_PADRAO)
        self.slider_tolerancia.pack(fill="x", padx=5, pady=5)

        # ── Referência / STL ──────────────────────────────────────────────────
        frm_ref = self._lf("Referência / STL", "📁")
        frm_ref.pack(fill="x", pady=(0, 8))

        tk.Checkbutton(
            frm_ref,
            text="💾 Salvar como Referência",
            variable=self.var_referencia,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto,
            selectcolor=Config.cor_borda,
            activebackground=Config.cor_fundo_secundario,
            activeforeground=Config.cor_principal,
            font=self.FONT_PADRAO,
            borderwidth=0,
            highlightthickness=0,
        ).pack(anchor="w", padx=5, pady=(0, 6))

        self.lbl_stl = tk.Label(
            frm_ref,
            text="Nenhum STL selecionado",
            wraplength=290,
            justify="left",
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_texto_secundario,
            font=("Segoe UI", 9),
        )
        self.lbl_stl.pack(fill="x", padx=5, pady=(0, 6))

        self._btn(frm_ref, "📂 Carregar STL", self._selecionar_stl).pack(fill="x", padx=5, pady=(0, 4))
        self._btn(frm_ref, "🗑️ Limpar STL",   self._limpar_stl,     cor_bg=Config.cor_borda).pack(fill="x", padx=5, pady=(0, 4))

        # ── Fonte da pré-visualização ─────────────────────────────────────────
        self.frm_prev_src = self._lf("Pré-visualização", "👁️")
        self.frm_prev_src.pack(fill="x", pady=(0, 8))

        # ── Modo de operação real ─────────────────────────────────────────────
        self.modo_op_real = self._lf("Ação ao Executar (Modo Real)", "🔧")
        self._atualizar_radios_modo_real()

        # ── Exportações ───────────────────────────────────────────────────────
        self._btn(self.coluna_esq, "💾 Exportar STL da Prévia", self._exportar_stl_previa).pack(
            fill="x", pady=(0, 5)
        )
        self._btn(self.coluna_esq, "💾 Exportar STL do Teste",  self._exportar_stl_teste).pack(
            fill="x", pady=(0, 5)
        )
        self._btn(self.coluna_esq, "📊 Ver Métricas da Última Inspeção", self._abrir_janela_metricas).pack(
            fill="x", pady=(0, 10)
        )

        # ── Botão principal ───────────────────────────────────────────────────
        tk.Button(
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
            activeforeground=Config.cor_fundo,
        ).pack(fill="x", pady=(0, 20))

    # ─────────────────────────────────────────────────────────────────────────
    # Painel de visualização 3D (coluna direita)
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_painel_direita(self):
        frm = tk.LabelFrame(
            self.coluna_dir,
            text=" 📊 Visualização 3D ",
            font=self.FONT_TITULO,
            bg=Config.cor_fundo_secundario,
            fg=Config.cor_principal,
            borderwidth=2,
            relief="groove",
            padx=10,
            pady=10,
        )
        frm.pack(fill="both", expand=True)

        self.fig_previa = plt.Figure(figsize=(7, 7), facecolor=Config.cor_fundo_secundario)
        self.ax_previa  = self.fig_previa.add_subplot(111, projection="3d")
        self.ax_previa.set_facecolor(Config.cor_fundo)

        self.canvas_previa = FigureCanvasTkAgg(self.fig_previa, master=frm)
        self.canvas_previa.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers de UI
    # ─────────────────────────────────────────────────────────────────────────

    def _atualizar_botoes_modo(self):
        """Recria radiobuttons de fonte da prévia conforme o modo atual."""
        for w in self.frm_prev_src.winfo_children():
            w.destroy()

        if not self.var_previa_fonte.get():
            self.var_previa_fonte.set("simulado" if self.var_modo.get() else "real")

        opts = (
            [("🖥️  Simulado", "simulado"), ("📁 STL Carregado", "stl")]
            if self.var_modo.get()
            else [("⚙️  Real", "real"), ("📁 STL Carregado", "stl")]
        )
        for label, val in opts:
            tk.Radiobutton(
                self.frm_prev_src,
                text=label,
                variable=self.var_previa_fonte,
                value=val,
                command=self._atualizar_previa,
                bg=Config.cor_fundo_secundario,
                fg=Config.cor_texto,
                selectcolor=Config.cor_borda,
                activebackground=Config.cor_fundo_secundario,
                activeforeground=Config.cor_principal,
                font=self.FONT_PADRAO,
                borderwidth=0,
                highlightthickness=0,
            ).pack(anchor="w", padx=5, pady=3)

    def _atualizar_radios_modo_real(self):
        """Recria radiobuttons de ação no modo real."""
        for w in self.modo_op_real.winfo_children():
            w.destroy()
        if not self.var_previa_comparacao.get():
            self.var_previa_comparacao.set("Pré-Visualização")

        for label, val in [("👁️ Pré-Visualização", "Pré-Visualização"), ("🔍 Comparação", "Comparação")]:
            tk.Radiobutton(
                self.modo_op_real,
                text=label,
                variable=self.var_previa_comparacao,
                value=val,
                command=self._atualizar_modo_real_vis,
                bg=Config.cor_fundo_secundario,
                fg=Config.cor_texto,
                selectcolor=Config.cor_borda,
                activebackground=Config.cor_fundo_secundario,
                activeforeground=Config.cor_principal,
                font=self.FONT_PADRAO,
                borderwidth=0,
                highlightthickness=0,
            ).pack(anchor="w", padx=5, pady=3)

    # ─────────────────────────────────────────────────────────────────────────
    # Alternância de modo
    # ─────────────────────────────────────────────────────────────────────────

    def _alternar_modo(self):
        self.var_modo.set(not self.var_modo.get())
        simulado = self.var_modo.get()
        self.label_modo.config(text="🖥️  Simulado" if simulado else "⚙️  Real")

        if simulado:
            self.frm_forma.pack(after=self.frm_modo, fill="x", pady=(0, 8))
            self.frm_defeito.pack(after=self.frm_forma, fill="x", pady=(0, 8))
            self.modo_op_real.pack_forget()
            self.var_previa_fonte.set("simulado")
        else:
            self.frm_forma.pack_forget()
            self.frm_defeito.pack_forget()
            self.modo_op_real.pack(after=self.frm_prev_src, fill="x", pady=(0, 8))
            self._atualizar_radios_modo_real()
            self.var_previa_fonte.set("real")

        self._atualizar_botoes_modo()
        self._atualizar_previa()
        logger.info("Modo alterado para: %s", "Simulado" if simulado else "Real")

    # ─────────────────────────────────────────────────────────────────────────
    # Pré-visualização 3D
    # ─────────────────────────────────────────────────────────────────────────

    def _plot_nuvem(self, ax, pts, titulo="", cores=None):
        """Plota nuvem de pontos em eixo 3D com estilo escuro."""
        ax.cla()
        ax.set_facecolor(Config.cor_fundo)

        if pts is None or len(pts) == 0:
            ax.set_title("(sem dados)", color=Config.cor_texto)
            for lab in [ax.set_xlabel, ax.set_ylabel, ax.set_zlabel]:
                lab("")
            self.canvas_previa.draw_idle()
            return

        c = cores if cores else "cyan"
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=1, c=c)

        try:
            mx  = (pts.max(axis=0) - pts.min(axis=0)).max()
            mid = pts.mean(axis=0)
            ax.set_xlim(mid[0] - mx / 2, mid[0] + mx / 2)
            ax.set_ylim(mid[1] - mx / 2, mid[1] + mx / 2)
            ax.set_zlim(mid[2] - mx / 2, mid[2] + mx / 2)
            ax.set_box_aspect((1, 1, 1))
        except Exception:
            pass

        ax.set_title(titulo, color=Config.cor_texto, fontsize=11, pad=12)
        for fn, lbl in [(ax.set_xlabel, "X (mm)"), (ax.set_ylabel, "Y (mm)"), (ax.set_zlabel, "Z (mm)")]:
            fn(lbl, color=Config.cor_texto_secundario, fontsize=9)

        ax.tick_params(colors=Config.cor_texto_secundario, labelsize=8)
        ax.grid(True, alpha=0.2, color=Config.cor_borda)
        for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor(Config.cor_borda)

        self.canvas_previa.draw_idle()

    def _atualizar_previa(self):
        src = self.var_previa_fonte.get()

        if src == "stl":
            if not self.arquivo_stl_selecionado:
                self._plot_nuvem(self.ax_previa, None, "Nenhum STL carregado")
                return
            try:
                pts = logica.carregar_stl(self.arquivo_stl_selecionado)
                self.pontos_previa = pts
                self._plot_nuvem(self.ax_previa, pts, f"STL: {os.path.basename(self.arquivo_stl_selecionado)}")
            except Exception as e:
                self._plot_nuvem(self.ax_previa, None, f"Erro STL: {e}")

        elif src in ("simulado", "real"):
            forma    = self.combo_forma.get()   if hasattr(self, "combo_forma")   else "cilindro"
            tipo_def = self.combo_defeito.get() if hasattr(self, "combo_defeito") else "nenhum"
            pts = logica.gerar_pontos_simulados(
                defeito=(tipo_def != "nenhum"), tipo_defeito=tipo_def, forma_base=forma
            )
            self.pontos_previa = pts
            self._plot_nuvem(self.ax_previa, pts, f"Simulado — {forma} / {tipo_def}")

    def _atualizar_modo_real_vis(self):
        modo = self.var_previa_comparacao.get()
        if modo == "Comparação" and os.path.exists(Config.ARQUIVO_REFERENCIA):
            try:
                pts = logica.carregar_xyz(Config.ARQUIVO_REFERENCIA)
                self._plot_nuvem(self.ax_previa, pts, "Referência carregada")
            except Exception as e:
                messagebox.showwarning("Aviso", str(e))
        elif modo == "Pré-Visualização" and self.pontos_teste_ultimo is not None:
            self._plot_nuvem(self.ax_previa, self.pontos_teste_ultimo, "Última peça capturada")

    # ─────────────────────────────────────────────────────────────────────────
    # Gerenciamento STL
    # ─────────────────────────────────────────────────────────────────────────

    def _selecionar_stl(self):
        path = filedialog.askopenfilename(title="Selecionar STL", filetypes=[("STL", "*.stl")])
        if not path:
            return
        self.arquivo_stl_selecionado = path
        self.lbl_stl.config(text=f"STL: {os.path.basename(path)}")
        if self.var_previa_fonte.get() == "stl":
            self._atualizar_previa()

    def _limpar_stl(self):
        self.arquivo_stl_selecionado = None
        self.lbl_stl.config(text="Nenhum STL selecionado")
        if self.var_previa_fonte.get() == "stl":
            self._atualizar_previa()

    # ─────────────────────────────────────────────────────────────────────────
    # Execução principal
    # ─────────────────────────────────────────────────────────────────────────

    def _executar(self):
        modo_ref   = self.var_referencia.get()
        modo_sim   = self.var_modo.get()
        tol_mm     = self.slider_tolerancia.get()
        tipo_def   = self.combo_defeito.get() if modo_sim and hasattr(self, "combo_defeito") else "nenhum"
        forma      = self.combo_forma.get()   if modo_sim and hasattr(self, "combo_forma")   else "cilindro"

        logger.info(
            "EXECUTAR — ref=%s sim=%s tol=%.1f defeito=%s forma=%s",
            modo_ref, modo_sim, tol_mm, tipo_def, forma,
        )

        # ── Salvar referência ─────────────────────────────────────────────────
        if modo_ref:
            pontos = self._obter_pontos_referencia(modo_sim, tipo_def, forma)
            if pontos is not None:
                self._salvar_referencia(pontos, tipo_def)
            return

        # ── Inspecionar (simulado) ────────────────────────────────────────────
        if modo_sim:
            pontos_ref = self._carregar_referencia()
            if pontos_ref is None:
                return
            pontos_teste = logica.gerar_pontos_simulados(
                defeito=(tipo_def != "nenhum"),
                tipo_defeito=tipo_def,
                seed=np.random.randint(0, 999999),
                forma_base=forma,
            )
            self.pontos_teste_ultimo = pontos_teste.copy()
            self._comparar_e_exibir(pontos_ref, pontos_teste, tol_mm)
            return

        # ── Inspecionar (real) ────────────────────────────────────────────────
        modo_op = self.var_previa_comparacao.get()
        messagebox.showinfo("Leitura", "Iniciando leitura do sensor…\nAguarde o sinal FIM do Arduino.")

        if modo_op == "Pré-Visualização":
            serial_comm.ler_dados_async(
                callback_pontos=lambda pts: self.janela.after(0, lambda: self._cb_previa_real(pts)),
                callback_erro=lambda msg: self.janela.after(0, lambda: messagebox.showerror("Erro serial", msg)),
            )
        elif modo_op == "Comparação":
            pontos_ref = self._carregar_referencia()
            if pontos_ref is None:
                return
            serial_comm.ler_dados_async(
                callback_pontos=lambda pts: self.janela.after(
                    0, lambda: self._cb_comparar(pts, pontos_ref, tol_mm)
                ),
                callback_erro=lambda msg: self.janela.after(0, lambda: messagebox.showerror("Erro serial", msg)),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Referência
    # ─────────────────────────────────────────────────────────────────────────

    def _obter_pontos_referencia(self, modo_sim, tipo_def, forma):
        if self.arquivo_stl_selecionado:
            try:
                return logica.carregar_stl(self.arquivo_stl_selecionado)
            except Exception as e:
                messagebox.showerror("Erro", str(e))
                return None

        if modo_sim:
            tem_def = tipo_def != "nenhum"
            return logica.gerar_pontos_simulados(
                defeito=tem_def,
                tipo_defeito=tipo_def if tem_def else "nenhum",
                seed=np.random.randint(0, 999999),
                forma_base=forma,
            )

        messagebox.showinfo("Referência Real", "Inicie a leitura do sensor.\nAguarde o sinal FIM.")
        serial_comm.ler_dados_async(
            callback_pontos=lambda pts: self.janela.after(0, lambda: self._salvar_referencia(pts, "real")),
            callback_erro=lambda msg: self.janela.after(0, lambda: messagebox.showerror("Erro serial", msg)),
        )
        return None

    def _salvar_referencia(self, pontos, tipo_def="nenhum"):
        if pontos is None or len(pontos) == 0:
            messagebox.showerror("Erro", "Nenhum ponto para salvar como referência.")
            return
        try:
            logica.salvar_xyz(Config.ARQUIVO_REFERENCIA, pontos)
            self.pontos_ref_ultimo = pontos.copy()
            self._plot_nuvem(self.ax_previa, pontos, "Referência salva")
            msg = f"Referência salva ({'com defeito: ' + tipo_def if tipo_def not in ('nenhum', 'real') else 'sem defeito'})."
            messagebox.showinfo("Referência", msg)
            logger.info("Referência salva — %d pontos", len(pontos))
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _carregar_referencia(self):
        if not os.path.exists(Config.ARQUIVO_REFERENCIA):
            messagebox.showerror("Erro", "Arquivo de referência não encontrado.\nGere uma referência primeiro.")
            return None
        try:
            pts = logica.carregar_xyz(Config.ARQUIVO_REFERENCIA)
            self.pontos_ref_ultimo = pts
            return pts
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Comparação e resultado
    # ─────────────────────────────────────────────────────────────────────────

    def _comparar_e_exibir(self, pontos_ref, pontos_teste, tol_mm):
        try:
            resultado = logica.verificar_defeito(pontos_ref, pontos_teste, tol_mm, usar_icp=True)
        except Exception as e:
            messagebox.showerror("Erro na verificação", str(e))
            logger.error("Erro na verificação: %s", e)
            return

        self._ultimo_resultado = resultado

        # ── Mensagem de resultado ─────────────────────────────────────────────
        status  = "✅ PEÇA APROVADA" if resultado["aprovada"] else "❌ PEÇA COM DEFEITO"
        resumo  = (
            f"{status}\n\n"
            f"Defeitos detectados : {resultado['n_defeitos']} pontos\n"
            f"% fora da tolerância: {resultado['pct_defeito']:.1f}%\n"
            f"Distância média     : {resultado['dist_media']:.3f} mm\n"
            f"Distância máxima    : {resultado['dist_max']:.3f} mm\n"
            f"Desvio padrão       : {resultado['dist_std']:.3f} mm\n"
            f"Erro ICP residual   : {resultado['erro_icp']:.4f} mm"
        )
        messagebox.showinfo("Resultado da Inspeção", resumo)
        logger.info("Resultado: %s", status)

        self._abrir_janela_comparacao(pontos_teste, pontos_ref, resultado)

    def _cb_previa_real(self, pts):
        self.pontos_teste_ultimo = pts
        self._plot_nuvem(self.ax_previa, pts, "Peça Real Capturada")

    def _cb_comparar(self, pts, pontos_ref, tol_mm):
        self.pontos_teste_ultimo = pts
        self._comparar_e_exibir(pontos_ref, pts, tol_mm)

    # ─────────────────────────────────────────────────────────────────────────
    # Janela de comparação visual
    # ─────────────────────────────────────────────────────────────────────────

    def _abrir_janela_comparacao(self, pontos_teste, pontos_ref, resultado):
        """Janela com nuvens lado a lado + colormap de distâncias."""
        win = tk.Toplevel(self.janela)
        win.title("Comparação Visual — Nuvens de Pontos")
        win.geometry("1100x560")
        win.configure(bg=Config.cor_fundo)

        fig = plt.Figure(figsize=(11, 5.5), facecolor=Config.cor_fundo_secundario)

        # ── Nuvem teste ───────────────────────────────────────────────────────
        ax1 = fig.add_subplot(121, projection="3d")
        ax1.set_facecolor(Config.cor_fundo)
        ax1.scatter(
            pontos_teste[:, 0], pontos_teste[:, 1], pontos_teste[:, 2],
            c=resultado["cores_teste"], s=2,
        )
        ax1.set_title("Peça TESTE (vermelho = defeito)", color=Config.cor_texto, fontsize=11)
        ax1.set_box_aspect((1, 1, 1))

        # ── Nuvem referência ──────────────────────────────────────────────────
        ax2 = fig.add_subplot(122, projection="3d")
        ax2.set_facecolor(Config.cor_fundo)
        ax2.scatter(
            pontos_ref[:, 0], pontos_ref[:, 1], pontos_ref[:, 2],
            c=resultado["cores_ref"], s=2,
        )
        ax2.set_title("REFERÊNCIA (pontos faltantes em vermelho)", color=Config.cor_texto, fontsize=11)
        ax2.set_box_aspect((1, 1, 1))

        for ax in [ax1, ax2]:
            ax.tick_params(colors=Config.cor_texto_secundario, labelsize=7)
            for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
                pane.fill = False
                pane.set_edgecolor(Config.cor_borda)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Janela de métricas industriais completas
    # ─────────────────────────────────────────────────────────────────────────

    def _abrir_janela_metricas(self):
        """
        Abre janela com dashboard técnico completo:
          • Mapa de calor de distâncias (scatter colorido por magnitude)
          • Histograma de distribuição das distâncias
          • Painel de métricas numéricas
        """
        if self._ultimo_resultado is None:
            messagebox.showinfo("Métricas", "Nenhuma inspeção realizada ainda.\nExecute uma inspeção primeiro.")
            return

        r = self._ultimo_resultado

        win = tk.Toplevel(self.janela)
        win.title("📊 Dashboard de Métricas — Última Inspeção")
        win.geometry("1150x620")
        win.configure(bg=Config.cor_fundo)

        fig = plt.Figure(figsize=(11.5, 6), facecolor=Config.cor_fundo_secundario)
        fig.suptitle("Análise Técnica da Inspeção 3D", color=Config.cor_texto, fontsize=14, y=0.98)

        gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35, left=0.06, right=0.97)

        # ── 1. Mapa de calor: distâncias nos pontos teste ─────────────────────
        ax_heat = fig.add_subplot(gs[0], projection="3d")
        ax_heat.set_facecolor(Config.cor_fundo)
        pts  = self.pontos_teste_ultimo
        dist = r["dist_teste"]

        if pts is not None and len(pts) > 0:
            sc = ax_heat.scatter(
                pts[:, 0], pts[:, 1], pts[:, 2],
                c=dist, cmap="RdYlGn_r", s=3, vmin=0, vmax=max(dist.max(), 0.01),
            )
            cbar = fig.colorbar(sc, ax=ax_heat, shrink=0.6, pad=0.12)
            cbar.set_label("Distância (mm)", color=Config.cor_texto, fontsize=8)
            cbar.ax.yaxis.set_tick_params(color=Config.cor_texto_secundario)
            plt.setp(cbar.ax.yaxis.get_ticklabels(), color=Config.cor_texto_secundario)

        ax_heat.set_title("Mapa de Calor\n(distâncias à referência)", color=Config.cor_texto, fontsize=10, pad=8)
        ax_heat.set_box_aspect((1, 1, 1))
        ax_heat.tick_params(colors=Config.cor_texto_secundario, labelsize=7)
        for pane in [ax_heat.xaxis.pane, ax_heat.yaxis.pane, ax_heat.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor(Config.cor_borda)

        # ── 2. Histograma das distâncias ──────────────────────────────────────
        ax_hist = fig.add_subplot(gs[1])
        ax_hist.set_facecolor(Config.cor_fundo)
        ax_hist.patch.set_alpha(0)

        todas_dist = np.concatenate([r["dist_teste"], r["dist_ref"]])
        ax_hist.hist(todas_dist, bins=50, color=Config.cor_principal, alpha=0.85, edgecolor="none")
        ax_hist.axvline(self.slider_tolerancia.get(), color=Config.cor_perigo, lw=2, ls="--", label=f"Tol. {self.slider_tolerancia.get()} mm")
        ax_hist.axvline(r["dist_media"], color=Config.cor_destaque, lw=1.5, ls="-", label=f"Média {r['dist_media']:.2f} mm")
        ax_hist.set_title("Histograma de Distâncias", color=Config.cor_texto, fontsize=10)
        ax_hist.set_xlabel("Distância (mm)", color=Config.cor_texto_secundario)
        ax_hist.set_ylabel("Nº de pontos",   color=Config.cor_texto_secundario)
        ax_hist.tick_params(colors=Config.cor_texto_secundario)
        leg = ax_hist.legend(facecolor=Config.cor_fundo_secundario, edgecolor=Config.cor_borda, labelcolor=Config.cor_texto, fontsize=8)
        ax_hist.spines[:].set_color(Config.cor_borda)

        # ── 3. Painel de métricas numéricas ──────────────────────────────────
        ax_txt = fig.add_subplot(gs[2])
        ax_txt.set_facecolor(Config.cor_fundo_secundario)
        ax_txt.axis("off")

        status_txt  = "✅  APROVADA" if r["aprovada"] else "❌  REPROVADA"
        status_cor  = Config.cor_sucesso if r["aprovada"] else Config.cor_perigo

        linhas = [
            ("STATUS", status_txt, status_cor),
            ("", "", ""),
            ("Defeitos detectados", f"{r['n_defeitos']} pontos", Config.cor_texto),
            ("% fora da tolerância", f"{r['pct_defeito']:.2f}%", Config.cor_destaque),
            ("", "", ""),
            ("Distância média", f"{r['dist_media']:.4f} mm", Config.cor_texto),
            ("Distância máxima", f"{r['dist_max']:.4f} mm", Config.cor_perigo if r['dist_max'] > self.slider_tolerancia.get() else Config.cor_sucesso),
            ("Desvio padrão", f"{r['dist_std']:.4f} mm", Config.cor_texto),
            ("", "", ""),
            ("Erro residual ICP", f"{r['erro_icp']:.6f} mm", Config.cor_texto_secundario),
        ]

        y = 0.95
        for label, valor, cor in linhas:
            if not label:
                y -= 0.04
                continue
            ax_txt.text(0.05, y, label + ":", color=Config.cor_texto_secundario, fontsize=9, transform=ax_txt.transAxes)
            ax_txt.text(0.05, y - 0.055, valor, color=cor, fontsize=11, fontweight="bold", transform=ax_txt.transAxes)
            y -= 0.115

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Exportações STL
    # ─────────────────────────────────────────────────────────────────────────

    def _exportar_stl(self, pontos, titulo_dialogo):
        if pontos is None or len(pontos) == 0:
            messagebox.showwarning("Exportar STL", "Nenhum ponto disponível para exportar.")
            return

        caminho = filedialog.asksaveasfilename(
            title=titulo_dialogo,
            defaultextension=".stl",
            filetypes=[("STL", "*.stl")],
        )
        if not caminho:
            return

        # Pergunta o método de reconstrução
        metodo = messagebox.askquestion(
            "Método STL",
            "Usar triangulação Delaunay (melhor para formas não-convexas)?\n\n"
            "SIM → Delaunay 2.5D (recomendado)\n"
            "NÃO → Casco Convexo (mais rápido)",
        )

        try:
            if metodo == "yes":
                logica.exportar_stl_delaunay(pontos, caminho)
            else:
                logica.exportar_stl_convexo(pontos, caminho)
            messagebox.showinfo("Exportar STL", f"STL salvo em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Exportar STL", str(e))

    def _exportar_stl_previa(self):
        self._exportar_stl(self.pontos_previa, "Salvar STL da Prévia")

    def _exportar_stl_teste(self):
        self._exportar_stl(self.pontos_teste_ultimo, "Salvar STL do Teste")
