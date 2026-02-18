# 🔍 Sistema de Inspeção 3D — v2.0

## Estrutura do projeto

```
scanner3d/
├── config.py       — Todos os parâmetros configuráveis
├── logica.py       — Matemática, ICP, métricas, I/O
├── serial_comm.py  — Comunicação serial com Arduino
├── interface.py    — Interface gráfica Tkinter
├── main.py         — Ponto de entrada + logging
└── logs/
    └── inspecao_YYYY_MM_DD.log
```

## Como rodar

```bash
cd scanner3d
python main.py
```

## Melhorias implementadas (v2.0)

| # | Melhoria | Arquivo |
|---|----------|---------|
| 1 | Arquitetura modular (5 arquivos) | todos |
| 2 | ICP — alinhamento antes da comparação | `logica.py` → `icp()` |
| 3 | Métricas industriais completas | `logica.py` → `verificar_defeito()` |
| 4 | Geração vetorizada com NumPy (sem loops) | `logica.py` → `gerar_casca_*()` |
| 5 | STL Delaunay (alternativa ao casco convexo) | `logica.py` → `exportar_stl_delaunay()` |
| 6 | Logging em arquivo rotativo diário | `main.py` → `configurar_logging()` |

## Dependências

```
numpy
scipy
matplotlib
numpy-stl
pyserial
```

## Parâmetros ajustáveis

Edite `config.py` para alterar:

- `TOLERANCIA_PADRAO` — tolerância padrão de inspeção (mm)
- `ICP_MAX_ITERACOES` — iterações máximas do algoritmo ICP
- `N_PONTOS_SIMULACAO` — densidade da nuvem simulada
- `LOG_LEVEL` — nível de detalhe dos logs (`DEBUG` / `INFO` / `WARNING`)
- `BAUDRATE_SERIAL` — taxa de comunicação com o Arduino
