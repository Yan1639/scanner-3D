"""
interface.py — Interface gráfica do Sistema de Inspeção 3D.

Responsabilidades:
  • Layout e controles Tkinter
  • Visualização 3D com Matplotlib
  • Janela de resultados com mapa de calor, histograma e métricas
  • Delegação de processamento para logica.py e serial_comm.py

Autor : Yan de Lima Pereira
Versão: 2.0 (UI Redesign)
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

# ── Paleta refinada (sobrescreve / complementa Config) ───────────────────────
C = Config
BG         = "#0d1117"          # fundo principal — quase preto azulado
BG2        = "#161b22"          # cards / painéis
BG3        = "#1c2333"          # elementos internos
BORDER     = "#21262d"          # bordas sutis
BORDER_ACC = "#30363d"          # bordas em hover / destaque
TEXT       = "#e6edf3"          # texto principal
TEXT_DIM   = "#8b949e"          # texto secundário
ACCENT     = "#58a6ff"          # azul primário
ACCENT2    = "#79c0ff"          # azul claro (hover)
GREEN      = "#3fb950"          # sucesso
RED        = "#f85149"          # erro / defeito
YELLOW     = "#d29922"          # destaque / aviso
PURPLE     = "#bc8cff"          # modo simulado

FONT_MONO   = ("Consolas",   10)
FONT_UI     = ("Segoe UI",   10)
FONT_UI_SM  = ("Segoe UI",    9)
FONT_BOLD   = ("Segoe UI",   10, "bold")
FONT_HEADER = ("Segoe UI",   13, "bold")
FONT_TITLE  = ("Segoe UI",   11, "bold")
FONT_LABEL  = ("Segoe UI",    9)


# ─────────────────────────────────────────────────────────────────────────────
# Widgets customizados
# ─────────────────────────────────────────────────────────────────────────────

class FlatButton(tk.Frame):
    """Botão flat com hover suave e cursor de mão."""

    def __init__(self, parent, text, command,
                 bg=BG3, fg=TEXT,
                 hover_bg=BORDER_ACC, hover_fg=TEXT,
                 accent=False, danger=False, primary=False,
                 padx=12, pady=6, font=FONT_UI, **kw):
        super().__init__(parent, bg=BG, **kw)

        if primary:
            bg, fg, hover_bg = ACCENT, BG, ACCENT2
        elif accent:
            bg, fg, hover_bg = BG3, ACCENT, "#1c2333"
        elif danger:
            bg, fg, hover_bg = "#2d1a1a", RED, "#3d2020"

        self._bg       = bg
        self._hover_bg = hover_bg
        self._fg       = fg
        self._hover_fg = hover_fg

        self.lbl = tk.Label(
            self, text=text, bg=bg, fg=fg, font=font,
            padx=padx, pady=pady, cursor="hand2",
        )
        self.lbl.pack(fill="both", expand=True)

        for w in (self, self.lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", lambda e: command())

    def _on_enter(self, _):
        self.lbl.config(bg=self._hover_bg, fg=self._hover_fg)

    def _on_leave(self, _):
        self.lbl.config(bg=self._bg, fg=self._fg)

    def config_text(self, text):
        self.lbl.config(text=text)


class SectionCard(tk.Frame):
    """Card com título e linha separadora no topo."""

    def __init__(self, parent, title="", icon="", **kw):
        super().__init__(parent, bg=BG2, **kw)
        self.configure(highlightbackground=BORDER, highlightthickness=1)

        if title or icon:
            header = tk.Frame(self, bg=BG2)
            header.pack(fill="x", padx=12, pady=(10, 0))

            if icon:
                tk.Label(header, text=icon, bg=BG2, fg=TEXT_DIM, font=FONT_UI_SM).pack(side="left")
            tk.Label(
                header,
                text=f"  {title}" if icon else title,
                bg=BG2, fg=TEXT_DIM,
                font=("Segoe UI", 8, "bold"),
            ).pack(side="left")

            # linha separadora
            sep = tk.Frame(self, bg=BORDER, height=1)
            sep.pack(fill="x", padx=12, pady=(6, 0))

        self.body = tk.Frame(self, bg=BG2)
        self.body.pack(fill="both", expand=True, padx=12, pady=10)


class TogglePill(tk.Frame):
    """Toggle estilo pílula ON/OFF."""

    def __init__(self, parent, variable, on_change=None, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self._var = variable
        self._cb  = on_change
        self._draw()

    def _draw(self):
        for w in self.winfo_children():
            w.destroy()
        active = self._var.get()
        bg_pill = ACCENT if active else BG3
        fg_pill = BG if active else TEXT_DIM
        text    = "●  ATIVO" if active else "○  INATIVO"
        lbl = tk.Label(
            self, text=text, bg=bg_pill, fg=fg_pill,
            font=("Segoe UI", 9, "bold"), padx=10, pady=4, cursor="hand2",
        )
        lbl.pack()
        for w in (self, lbl):
            w.bind("<Button-1>", self._toggle)

    def _toggle(self, _=None):
        self._var.set(not self._var.get())
        self._draw()
        if self._cb:
            self._cb()


def styled_radio(parent, text, variable, value, command):
    """Radiobutton estilizado."""
    f = tk.Frame(parent, bg=BG2, cursor="hand2")
    f.pack(fill="x", pady=2)

    dot = tk.Label(f, text="◉" if variable.get() == value else "○",
                   bg=BG2, fg=ACCENT if variable.get() == value else TEXT_DIM,
                   font=FONT_UI_SM)
    dot.pack(side="left", padx=(0, 6))

    lbl = tk.Label(f, text=text, bg=BG2, fg=TEXT if variable.get() == value else TEXT_DIM,
                   font=FONT_UI_SM)
    lbl.pack(side="left")

    def _select(_=None):
        variable.set(value)
        command()
        # Atualiza todos os radios do mesmo grupo (pai)
        for child in parent.winfo_children():
            child.event_generate("<<RadioRefresh>>")

    for w in (f, dot, lbl):
        w.bind("<Button-1>", _select)
    return f


def metric_row(parent, label, value, color=TEXT):
    """Linha de métrica label + valor."""
    row = tk.Frame(parent, bg=BG2)
    row.pack(fill="x", pady=1)
    tk.Label(row, text=label, bg=BG2, fg=TEXT_DIM, font=FONT_LABEL,
             anchor="w").pack(side="left")
    tk.Label(row, text=value, bg=BG2, fg=color, font=FONT_MONO,
             anchor="e").pack(side="right")


# ─────────────────────────────────────────────────────────────────────────────
# Interface principal
# ─────────────────────────────────────────────────────────────────────────────

class Interface:
    """Interface gráfica do sistema de inspeção 3D."""

    def __init__(self):
        self.arquivo_stl_selecionado = None
        self.pontos_previa           = None
        self.pontos_teste_ultimo     = None
        self.pontos_ref_ultimo       = None
        self._ultimo_resultado       = None

        self._criar_janela_principal()
        self.janela.mainloop()

    # ─────────────────────────────────────────────────────────────────────────
    # Janela principal
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_janela_principal(self):
        self.janela = tk.Tk()
        self.janela.title("Sistema de Inspeção 3D v2.0")
        self.janela.state("zoomed")
        self.janela.configure(bg=BG)

        # Estilo ttk
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Dark.TCombobox",
            fieldbackground=BG3, background=BG3,
            foreground=TEXT, borderwidth=0, relief="flat",
            arrowcolor=TEXT_DIM, selectbackground=BORDER_ACC,
        )
        style.map("Dark.TCombobox",
            fieldbackground=[("readonly", BG3)],
            selectbackground=[("readonly", BORDER_ACC)],
            foreground=[("readonly", TEXT)],
        )
        style.configure("Vertical.TScrollbar",
                        background=BG3, troughcolor=BG2,
                        borderwidth=0, arrowcolor=TEXT_DIM)

        self._criar_variaveis()
        self._criar_layout()
        self._atualizar_botoes_modo()

    def _criar_variaveis(self):
        self.var_modo              = tk.BooleanVar(value=Config.MODO_SIMULADO)
        self.var_referencia        = tk.BooleanVar(value=Config.MODO_REFERENCIA)
        self.var_previa_fonte      = tk.StringVar(value="real")
        self.var_previa_comparacao = tk.StringVar(value="Pré-Visualização")

    # ─────────────────────────────────────────────────────────────────────────
    # Layout raiz: header + corpo
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_layout(self):
        # ── Topo: barra de header ─────────────────────────────────────────────
        self._criar_header()

        # ── Corpo: sidebar + viewer ───────────────────────────────────────────
        corpo = tk.Frame(self.janela, bg=BG)
        corpo.pack(fill="both", expand=True)

        self._criar_sidebar(corpo)
        self._criar_painel_direita(corpo)

    def _criar_header(self):
        hbar = tk.Frame(self.janela, bg=BG2,
                        highlightbackground=BORDER, highlightthickness=1)
        hbar.pack(fill="x")

        inner = tk.Frame(hbar, bg=BG2)
        inner.pack(fill="x", padx=20, pady=10)

        # Logo / título
        left = tk.Frame(inner, bg=BG2)
        left.pack(side="left")

        tk.Label(left, text="◈", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 8))
        tk.Label(left, text="INSPEÇÃO 3D", bg=BG2, fg=TEXT,
                 font=FONT_HEADER).pack(side="left")
        tk.Label(left, text=" v2.0", bg=BG2, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left", pady=(4, 0))

        # Indicador de modo (direita)
        right = tk.Frame(inner, bg=BG2)
        right.pack(side="right")

        tk.Label(right, text="MODO", bg=BG2, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))

        self.pill_modo = tk.Label(
            right, text="⬛  REAL", bg=BG3, fg=ACCENT,
            font=("Segoe UI", 9, "bold"), padx=10, pady=4,
        )
        self.pill_modo.pack(side="left")

    # ─────────────────────────────────────────────────────────────────────────
    # Sidebar com scroll (coluna esquerda)
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_sidebar(self, parent):
        sidebar_wrap = tk.Frame(parent, bg=BG, width=320)
        sidebar_wrap.pack(side="left", fill="y")
        sidebar_wrap.pack_propagate(False)

        # Linha separadora vertical
        tk.Frame(parent, bg=BORDER, width=1).pack(side="left", fill="y")

        # Canvas + scrollbar
        self._canvas_scroll = tk.Canvas(sidebar_wrap, bg=BG,
                                        width=318, highlightthickness=0)
        sb = ttk.Scrollbar(sidebar_wrap, orient="vertical",
                           command=self._canvas_scroll.yview)
        self.coluna_esq = tk.Frame(self._canvas_scroll, bg=BG)
        self._canvas_scroll.create_window((0, 0), window=self.coluna_esq, anchor="nw")
        self._canvas_scroll.configure(yscrollcommand=sb.set)

        self.coluna_esq.bind(
            "<Configure>",
            lambda e: self._canvas_scroll.configure(
                scrollregion=self._canvas_scroll.bbox("all")
            ),
        )
        self._canvas_scroll.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Bind scroll com mouse
        self._canvas_scroll.bind_all("<MouseWheel>", self._on_mousewheel)

        self._criar_controles_sidebar()

    def _on_mousewheel(self, event):
        self._canvas_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _criar_controles_sidebar(self):
        p = self.coluna_esq   # alias
        pad = {"fill": "x", "padx": 12, "pady": (0, 8)}

        # ── Modo ──────────────────────────────────────────────────────────────
        card_modo = SectionCard(p, title="MODO DE OPERAÇÃO", icon="⚙")
        card_modo.pack(**pad)

        self.label_modo = tk.Label(
            card_modo.body,
            text="SIMULADO" if self.var_modo.get() else "REAL",
            bg=BG2, fg=PURPLE if self.var_modo.get() else ACCENT,
            font=("Segoe UI", 14, "bold"),
        )
        self.label_modo.pack(pady=(0, 8))

        self.btn_alternar = FlatButton(
            card_modo.body, text="↔  Alternar Modo",
            command=self._alternar_modo, accent=True,
        )
        self.btn_alternar.pack(fill="x")

        # ── Forma base (simulado) ─────────────────────────────────────────────
        self.frm_forma = SectionCard(p, title="FORMA BASE", icon="◻")
        self.combo_forma = ttk.Combobox(
            self.frm_forma.body, values=Config.FORMAS_BASE,
            state="readonly", font=FONT_UI, style="Dark.TCombobox",
        )
        self.combo_forma.set("cilindro")
        self.combo_forma.pack(fill="x")
        self.combo_forma.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())

        # ── Tipo de defeito (simulado) ────────────────────────────────────────
        self.frm_defeito = SectionCard(p, title="TIPO DE DEFEITO", icon="⚠")
        self.combo_defeito = ttk.Combobox(
            self.frm_defeito.body, values=Config.TIPOS_DEFEITOS,
            state="readonly", font=FONT_UI, style="Dark.TCombobox",
        )
        self.combo_defeito.set("nenhum")
        self.combo_defeito.pack(fill="x")
        self.combo_defeito.bind("<<ComboboxSelected>>", lambda e: self._atualizar_previa())

        if self.var_modo.get():
            self.frm_forma.pack(**pad)
            self.frm_defeito.pack(**pad)

        # ── Tolerância ────────────────────────────────────────────────────────
        card_tol = SectionCard(p, title="TOLERÂNCIA", icon="↔")
        card_tol.pack(**pad)

        tol_row = tk.Frame(card_tol.body, bg=BG2)
        tol_row.pack(fill="x", pady=(0, 6))
        tk.Label(tol_row, text="Limite máximo de desvio",
                 bg=BG2, fg=TEXT_DIM, font=FONT_LABEL).pack(side="left")
        self.lbl_tol_val = tk.Label(tol_row, text=f"{Config.TOLERANCIA_PADRAO} mm",
                                    bg=BG2, fg=ACCENT, font=FONT_MONO)
        self.lbl_tol_val.pack(side="right")

        self.slider_tolerancia = tk.Scale(
            card_tol.body, from_=1, to=30, orient=tk.HORIZONTAL,
            bg=BG2, fg=TEXT_DIM, troughcolor=BG3,
            activebackground=ACCENT, highlightthickness=0, borderwidth=0,
            showvalue=False, font=FONT_LABEL, length=240,
            command=self._on_slider_tol,
        )
        self.slider_tolerancia.set(Config.TOLERANCIA_PADRAO)
        self.slider_tolerancia.pack(fill="x")

        # ── Referência / STL ──────────────────────────────────────────────────
        card_ref = SectionCard(p, title="REFERÊNCIA / STL", icon="◈")
        card_ref.pack(**pad)

        # Checkbox salvar como referência
        self._chk_ref_state = self.var_referencia
        self._chk_ref_var   = tk.IntVar(value=int(self.var_referencia.get()))
        chk_row = tk.Frame(card_ref.body, bg=BG2, cursor="hand2")
        chk_row.pack(fill="x", pady=(0, 8))

        self._chk_box = tk.Label(chk_row, text="☐", bg=BG2, fg=TEXT_DIM, font=FONT_UI)
        self._chk_box.pack(side="left", padx=(0, 6))
        tk.Label(chk_row, text="Salvar como Referência",
                 bg=BG2, fg=TEXT_DIM, font=FONT_UI_SM).pack(side="left")
        for w in (chk_row, self._chk_box):
            w.bind("<Button-1>", self._toggle_referencia)

        # Label STL
        self.lbl_stl = tk.Label(
            card_ref.body, text="Nenhum arquivo selecionado",
            wraplength=260, justify="left",
            bg=BG3, fg=TEXT_DIM, font=FONT_LABEL,
            padx=8, pady=6, anchor="w",
        )
        self.lbl_stl.pack(fill="x", pady=(0, 8))

        FlatButton(card_ref.body, text="  Carregar STL",
                   command=self._selecionar_stl, accent=True).pack(fill="x", pady=(0, 4))
        FlatButton(card_ref.body, text="  Limpar STL",
                   command=self._limpar_stl).pack(fill="x")

        # ── Pré-visualização ──────────────────────────────────────────────────
        self.frm_prev_src = SectionCard(p, title="PRÉ-VISUALIZAÇÃO", icon="◎")
        self.frm_prev_src.pack(**pad)

        # ── Modo real: ação ───────────────────────────────────────────────────
        self.modo_op_real = SectionCard(p, title="AÇÃO (MODO REAL)", icon="▶")
        self._atualizar_radios_modo_real()

        # ── Exportações ───────────────────────────────────────────────────────
        card_exp = SectionCard(p, title="EXPORTAR", icon="↗")
        card_exp.pack(**pad)

        FlatButton(card_exp.body, text="STL da Prévia",
                   command=self._exportar_stl_previa).pack(fill="x", pady=(0, 4))
        FlatButton(card_exp.body, text="STL do Teste",
                   command=self._exportar_stl_teste).pack(fill="x", pady=(0, 4))
        FlatButton(card_exp.body, text="Métricas da Última Inspeção",
                   command=self._abrir_janela_metricas, accent=True).pack(fill="x")

        # ── Botão principal ───────────────────────────────────────────────────
        tk.Frame(p, bg=BG, height=4).pack()  # espaço
        self.btn_executar = FlatButton(
            p, text="▶  EXECUTAR INSPEÇÃO",
            command=self._executar, primary=True,
            font=("Segoe UI", 11, "bold"), pady=12,
        )
        self.btn_executar.pack(fill="x", padx=12, pady=(0, 16))

    def _on_slider_tol(self, val):
        self.lbl_tol_val.config(text=f"{int(float(val))} mm")

    def _toggle_referencia(self, _=None):
        new = not self.var_referencia.get()
        self.var_referencia.set(new)
        self._chk_box.config(
            text="☑" if new else "☐",
            fg=ACCENT if new else TEXT_DIM,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Painel direita: visualização 3D
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_painel_direita(self, parent):
        right = tk.Frame(parent, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Barra superior do viewer
        viewer_bar = tk.Frame(right, bg=BG2,
                              highlightbackground=BORDER, highlightthickness=1)
        viewer_bar.pack(fill="x")

        inner = tk.Frame(viewer_bar, bg=BG2)
        inner.pack(fill="x", padx=16, pady=8)

        tk.Label(inner, text="VISUALIZAÇÃO 3D", bg=BG2, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")

        self.lbl_viewer_status = tk.Label(
            inner, text="Aguardando dados…", bg=BG2, fg=TEXT_DIM,
            font=FONT_LABEL,
        )
        self.lbl_viewer_status.pack(side="right")

        # Área do matplotlib
        viewer_body = tk.Frame(right, bg=BG)
        viewer_body.pack(fill="both", expand=True, padx=16, pady=12)

        self.fig_previa = plt.Figure(figsize=(7, 7), facecolor=BG2)
        self.fig_previa.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.08)
        self.ax_previa = self.fig_previa.add_subplot(111, projection="3d")
        self.ax_previa.set_facecolor(BG)

        self.canvas_previa = FigureCanvasTkAgg(self.fig_previa, master=viewer_body)
        self.canvas_previa.get_tk_widget().configure(bg=BG, highlightthickness=0)
        self.canvas_previa.get_tk_widget().pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers de UI
    # ─────────────────────────────────────────────────────────────────────────

    def _atualizar_botoes_modo(self):
        """Recria radiobuttons de fonte da prévia conforme o modo atual."""
        for w in self.frm_prev_src.body.winfo_children():
            w.destroy()

        if not self.var_previa_fonte.get():
            self.var_previa_fonte.set("simulado" if self.var_modo.get() else "real")

        opts = (
            [("Simulado",      "simulado"), ("STL Carregado", "stl")]
            if self.var_modo.get()
            else [("Real",     "real"),     ("STL Carregado", "stl")]
        )
        self._radio_frames_prev = []
        for label, val in opts:
            self._make_radio(
                self.frm_prev_src.body, label, self.var_previa_fonte, val, self._atualizar_previa
            )

    def _atualizar_radios_modo_real(self):
        """Recria radiobuttons de ação no modo real."""
        for w in self.modo_op_real.body.winfo_children():
            w.destroy()
        if not self.var_previa_comparacao.get():
            self.var_previa_comparacao.set("Pré-Visualização")

        for label, val in [("Pré-Visualização", "Pré-Visualização"), ("Comparação", "Comparação")]:
            self._make_radio(
                self.modo_op_real.body, label,
                self.var_previa_comparacao, val, self._atualizar_modo_real_vis,
            )

    def _make_radio(self, parent, text, variable, value, command):
        """Radio button customizado."""
        is_sel = variable.get() == value

        row = tk.Frame(parent, bg=BG2, cursor="hand2")
        row.pack(fill="x", pady=2)

        dot = tk.Label(row,
                       text="◉" if is_sel else "◎",
                       bg=BG2, fg=ACCENT if is_sel else TEXT_DIM,
                       font=FONT_UI_SM)
        dot.pack(side="left", padx=(0, 8))

        lbl = tk.Label(row, text=text,
                       bg=BG2, fg=TEXT if is_sel else TEXT_DIM,
                       font=FONT_UI_SM)
        lbl.pack(side="left")

        def _select(_=None):
            variable.set(value)
            command()
            # Refaz todos os radios no container pai
            for child in parent.winfo_children():
                child.destroy()
            # chama novamente a função correta
            if parent is self.frm_prev_src.body:
                self._atualizar_botoes_modo()
            else:
                self._atualizar_radios_modo_real()

        for w in (row, dot, lbl):
            w.bind("<Button-1>", _select)

    # ─────────────────────────────────────────────────────────────────────────
    # Alternância de modo
    # ─────────────────────────────────────────────────────────────────────────

    def _alternar_modo(self):
        self.var_modo.set(not self.var_modo.get())
        simulado = self.var_modo.get()

        # Header pill
        self.pill_modo.config(
            text="⬛  SIMULADO" if simulado else "⬛  REAL",
            fg=PURPLE if simulado else ACCENT,
        )
        self.label_modo.config(
            text="SIMULADO" if simulado else "REAL",
            fg=PURPLE if simulado else ACCENT,
        )

        pad = {"fill": "x", "padx": 12, "pady": (0, 8)}
        if simulado:
            self.frm_forma.pack(after=self.frm_prev_src, **pad)
            self.frm_defeito.pack(after=self.frm_forma, **pad)
            self.modo_op_real.pack_forget()
            self.var_previa_fonte.set("simulado")
        else:
            self.frm_forma.pack_forget()
            self.frm_defeito.pack_forget()
            self.modo_op_real.pack(after=self.frm_prev_src, **pad)
            self._atualizar_radios_modo_real()
            self.var_previa_fonte.set("real")

        self._atualizar_botoes_modo()
        self._atualizar_previa()
        logger.info("Modo alterado para: %s", "Simulado" if simulado else "Real")

    # ─────────────────────────────────────────────────────────────────────────
    # Pré-visualização 3D
    # ─────────────────────────────────────────────────────────────────────────

    def _plot_nuvem(self, ax, pts, titulo="", cores=None):
        """Plota nuvem de pontos em eixo 3D com estilo escuro refinado."""
        ax.cla()
        ax.set_facecolor(BG)

        if pts is None or len(pts) == 0:
            ax.set_title("sem dados", color=TEXT_DIM, fontsize=10, pad=10)
            for fn in [ax.set_xlabel, ax.set_ylabel, ax.set_zlabel]:
                fn("", color=TEXT_DIM)
            self.canvas_previa.draw_idle()
            self.lbl_viewer_status.config(text="Sem dados")
            return

        c = cores if cores is not None else ACCENT
        ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=1, c=c, alpha=0.85)

        try:
            mx  = (pts.max(axis=0) - pts.min(axis=0)).max()
            mid = pts.mean(axis=0)
            ax.set_xlim(mid[0] - mx / 2, mid[0] + mx / 2)
            ax.set_ylim(mid[1] - mx / 2, mid[1] + mx / 2)
            ax.set_zlim(mid[2] - mx / 2, mid[2] + mx / 2)
            ax.set_box_aspect((1, 1, 1))
        except Exception:
            pass

        ax.set_title(titulo, color=TEXT, fontsize=10, pad=10, fontweight="bold")
        for fn, lbl in [(ax.set_xlabel, "X (mm)"), (ax.set_ylabel, "Y (mm)"), (ax.set_zlabel, "Z (mm)")]:
            fn(lbl, color=TEXT_DIM, fontsize=8)

        ax.tick_params(colors=TEXT_DIM, labelsize=7)
        ax.grid(True, alpha=0.12, color=BORDER_ACC, linewidth=0.5)
        for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor(BORDER)

        self.canvas_previa.draw_idle()
        self.lbl_viewer_status.config(text=f"{len(pts):,} pontos  ·  {titulo}")

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

        elif src == "simulado":
            forma    = self.combo_forma.get()   if hasattr(self, "combo_forma")   else "cilindro"
            tipo_def = self.combo_defeito.get() if hasattr(self, "combo_defeito") else "nenhum"
            pts = logica.gerar_pontos_simulados(
                defeito=(tipo_def != "nenhum"), tipo_defeito=tipo_def, forma_base=forma
            )
            self.pontos_previa = pts
            self._plot_nuvem(self.ax_previa, pts, f"{forma}  ·  {tipo_def}")

        elif src == "real":
            if self.pontos_teste_ultimo is not None:
                self._plot_nuvem(self.ax_previa, self.pontos_teste_ultimo, "Última peça capturada")
            else:
                self._plot_nuvem(self.ax_previa, None, "Sem dados — execute uma leitura real")

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
        name = os.path.basename(path)
        self.lbl_stl.config(text=f"  {name}", fg=ACCENT)
        if self.var_previa_fonte.get() == "stl":
            self._atualizar_previa()

    def _limpar_stl(self):
        self.arquivo_stl_selecionado = None
        self.lbl_stl.config(text="Nenhum arquivo selecionado", fg=TEXT_DIM)
        if self.var_previa_fonte.get() == "stl":
            self._atualizar_previa()

    # ─────────────────────────────────────────────────────────────────────────
    # Execução principal
    # ─────────────────────────────────────────────────────────────────────────

    def _executar(self):
        modo_ref = self.var_referencia.get()
        modo_sim = self.var_modo.get()
        tol_mm   = self.slider_tolerancia.get()
        tipo_def = self.combo_defeito.get() if modo_sim and hasattr(self, "combo_defeito") else "nenhum"
        forma    = self.combo_forma.get()   if modo_sim and hasattr(self, "combo_forma")   else "cilindro"

        logger.info(
            "EXECUTAR — ref=%s sim=%s tol=%.1f defeito=%s forma=%s",
            modo_ref, modo_sim, tol_mm, tipo_def, forma,
        )

        if modo_ref:
            pontos = self._obter_pontos_referencia(modo_sim, tipo_def, forma)
            if pontos is not None:
                self._salvar_referencia(pontos, tipo_def)
            return

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

        status = "✅ PEÇA APROVADA" if resultado["aprovada"] else "❌ PEÇA COM DEFEITO"
        resumo = (
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
        win = tk.Toplevel(self.janela)
        win.title("Comparação Visual — Nuvens de Pontos")
        win.geometry("1100x580")
        win.configure(bg=BG)

        # Barra título
        bar = tk.Frame(win, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")
        tk.Label(bar, text="COMPARAÇÃO VISUAL  —  NUVENS DE PONTOS",
                 bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 8, "bold"),
                 padx=16, pady=8).pack(side="left")

        # Status badge
        aprovada = resultado["aprovada"]
        badge_bg = "#0d2b1a" if aprovada else "#2b0d10"
        badge_fg = GREEN if aprovada else RED
        badge_txt = "APROVADA" if aprovada else "REPROVADA"
        tk.Label(bar, text=f"  {badge_txt}  ", bg=badge_bg, fg=badge_fg,
                 font=("Segoe UI", 9, "bold"), padx=6, pady=4).pack(side="right", padx=12, pady=6)

        # Figura
        fig = plt.Figure(figsize=(11, 5.2), facecolor=BG2)
        fig.subplots_adjust(left=0.04, right=0.96, top=0.88, bottom=0.06, wspace=0.3)

        ax1 = fig.add_subplot(121, projection="3d")
        ax1.set_facecolor(BG)
        ax1.scatter(pontos_teste[:, 0], pontos_teste[:, 1], pontos_teste[:, 2],
                    c=resultado["cores_teste"], s=2)
        ax1.set_title("PEÇA TESTE  (vermelho = defeito)", color=TEXT, fontsize=10, pad=8)
        ax1.set_box_aspect((1, 1, 1))

        ax2 = fig.add_subplot(122, projection="3d")
        ax2.set_facecolor(BG)
        ax2.scatter(pontos_ref[:, 0], pontos_ref[:, 1], pontos_ref[:, 2],
                    c=resultado["cores_ref"], s=2)
        ax2.set_title("REFERÊNCIA  (pontos faltantes em vermelho)", color=TEXT, fontsize=10, pad=8)
        ax2.set_box_aspect((1, 1, 1))

        for ax in [ax1, ax2]:
            ax.tick_params(colors=TEXT_DIM, labelsize=7)
            for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
                pane.fill = False
                pane.set_edgecolor(BORDER)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=BG, highlightthickness=0)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)

    # ─────────────────────────────────────────────────────────────────────────
    # Janela de métricas industriais
    # ─────────────────────────────────────────────────────────────────────────

    def _abrir_janela_metricas(self):
        if self._ultimo_resultado is None:
            messagebox.showinfo("Métricas", "Nenhuma inspeção realizada ainda.\nExecute uma inspeção primeiro.")
            return

        r = self._ultimo_resultado

        win = tk.Toplevel(self.janela)
        win.title("Dashboard de Métricas — Última Inspeção")
        win.geometry("1180x640")
        win.configure(bg=BG)

        # Barra topo
        bar = tk.Frame(win, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")
        tk.Label(bar, text="ANÁLISE TÉCNICA  —  INSPEÇÃO 3D",
                 bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 8, "bold"),
                 padx=16, pady=8).pack(side="left")

        # Figura matplotlib
        fig = plt.Figure(figsize=(11.8, 5.8), facecolor=BG2)
        fig.subplots_adjust(left=0.05, right=0.97, top=0.88, bottom=0.1, wspace=0.38)

        gs = gridspec.GridSpec(1, 3, figure=fig)

        # ── 1. Mapa de calor ──────────────────────────────────────────────────
        ax_heat = fig.add_subplot(gs[0], projection="3d")
        ax_heat.set_facecolor(BG)
        pts  = r.get("pontos_alinhados", self.pontos_teste_ultimo)
        dist = r["dist_teste"]

        if pts is not None and len(pts) > 0:
            sc = ax_heat.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                                 c=dist, cmap="RdYlGn_r", s=3,
                                 vmin=0, vmax=max(dist.max(), 0.01))
            cbar = fig.colorbar(sc, ax=ax_heat, shrink=0.55, pad=0.12)
            cbar.set_label("mm", color=TEXT_DIM, fontsize=8)
            cbar.ax.yaxis.set_tick_params(color=TEXT_DIM, labelsize=7)
            plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT_DIM)

            try:
                mx  = (pts.max(axis=0) - pts.min(axis=0)).max()
                mid = pts.mean(axis=0)
                ax_heat.set_xlim(mid[0] - mx / 2, mid[0] + mx / 2)
                ax_heat.set_ylim(mid[1] - mx / 2, mid[1] + mx / 2)
                ax_heat.set_zlim(mid[2] - mx / 2, mid[2] + mx / 2)
            except Exception:
                pass

        ax_heat.set_box_aspect((1, 1, 1))
        ax_heat.view_init(elev=20, azim=45)
        ax_heat.set_title("MAPA DE CALOR\ndistâncias à referência", color=TEXT, fontsize=9, pad=8)
        ax_heat.tick_params(colors=TEXT_DIM, labelsize=7)
        for fn, lbl in [(ax_heat.set_xlabel, "X"), (ax_heat.set_ylabel, "Y"), (ax_heat.set_zlabel, "Z")]:
            fn(lbl, color=TEXT_DIM, fontsize=7)
        for pane in [ax_heat.xaxis.pane, ax_heat.yaxis.pane, ax_heat.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor(BORDER)

        # ── 2. Histograma ─────────────────────────────────────────────────────
        ax_hist = fig.add_subplot(gs[1])
        ax_hist.set_facecolor(BG)
        ax_hist.patch.set_alpha(0)

        todas_dist = np.concatenate([r["dist_teste"], r["dist_ref"]])
        ax_hist.hist(todas_dist, bins=50, color=ACCENT, alpha=0.75, edgecolor="none")
        ax_hist.axvline(self.slider_tolerancia.get(),
                        color=RED, lw=1.5, ls="--",
                        label=f"Tolerância  {self.slider_tolerancia.get()} mm")
        ax_hist.axvline(r["dist_media"],
                        color=YELLOW, lw=1.2,
                        label=f"Média  {r['dist_media']:.2f} mm")
        ax_hist.set_title("HISTOGRAMA DE DISTÂNCIAS", color=TEXT, fontsize=9)
        ax_hist.set_xlabel("Distância (mm)", color=TEXT_DIM, fontsize=8)
        ax_hist.set_ylabel("Nº de pontos",   color=TEXT_DIM, fontsize=8)
        ax_hist.tick_params(colors=TEXT_DIM, labelsize=7)
        leg = ax_hist.legend(facecolor=BG2, edgecolor=BORDER, fontsize=8)
        for text in leg.get_texts():
            text.set_color(TEXT_DIM)
        for spine in ax_hist.spines.values():
            spine.set_color(BORDER)

        # ── 3. Métricas numéricas ─────────────────────────────────────────────
        ax_txt = fig.add_subplot(gs[2])
        ax_txt.set_facecolor(BG2)
        ax_txt.axis("off")

        aprovada   = r["aprovada"]
        status_txt = "APROVADA" if aprovada else "REPROVADA"
        status_cor = GREEN if aprovada else RED
        tol        = self.slider_tolerancia.get()

        # Bloco de status
        ax_txt.text(0.5, 0.97, status_txt, color=status_cor, fontsize=18,
                    fontweight="bold", ha="center", va="top",
                    transform=ax_txt.transAxes)

        linhas = [
            ("Defeitos detectados",    f"{r['n_defeitos']} pts",      TEXT),
            ("% fora da tolerância",   f"{r['pct_defeito']:.2f}%",    YELLOW),
            ("Distância média",        f"{r['dist_media']:.4f} mm",   TEXT),
            ("Distância máxima",       f"{r['dist_max']:.4f} mm",
                                       RED if r["dist_max"] > tol else GREEN),
            ("Desvio padrão",          f"{r['dist_std']:.4f} mm",     TEXT),
            ("Erro residual ICP",      f"{r['erro_icp']:.6f} mm",     TEXT_DIM),
        ]

        y = 0.80
        for label, valor, cor in linhas:
            ax_txt.text(0.06, y, label, color=TEXT_DIM, fontsize=8.5,
                        transform=ax_txt.transAxes)
            ax_txt.text(0.94, y, valor, color=cor, fontsize=9,
                        fontweight="bold", ha="right",
                        transform=ax_txt.transAxes)
            # linha divisória
            ly = y - 0.048
            ax_txt.plot([0.06, 0.94], [ly, ly], color=BORDER,
                        linewidth=0.5, transform=ax_txt.transAxes)
            y -= 0.115

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=BG, highlightthickness=0)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)

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