# \# Sistema de Inspeção 3D por Nuvem de Pontos

# 

# Projeto em \*\*Python\*\* para inspeção dimensional de peças utilizando \*\*nuvens de pontos 3D\*\*, com suporte a \*\*modo simulado\*\* e \*\*modo real\*\* (via Arduino), além de interface gráfica em \*\*Tkinter\*\*.

# 

# ---

# 

# \## Visão Geral

# 

# O sistema compara uma peça de teste com um \*\*modelo de referência\*\* para identificar \*\*defeitos geométricos\*\*, utilizando técnicas de processamento de nuvem de pontos e busca por vizinhos próximos (KD-Tree).

# 

# Ele pode operar de duas formas:

# 

# \* \*\*Modo Simulado\*\*: geração de geometrias 3D (cilindro ou esfera) com defeitos artificiais.

# \* \*\*Modo Real\*\*: leitura de dados reais enviados por um Arduino via comunicação serial.

# 

# ---

# 

# \## Funcionalidades

# 

# \* Geração de nuvem de pontos 3D simulada

# \* Simulação de defeitos (furo, amassado, esticado, quebrado, etc.)

# \* Carregamento de arquivos \*\*STL\*\*

# \* Salvamento e leitura de modelos de referência (\*\*.xyz\*\*)

# \* Comparação entre nuvens de pontos com tolerância configurável

# \* Visualização 3D interativa

# \* Exportação de resultados em \*\*STL\*\*

# \* Interface gráfica moderna em Tkinter

# 

# ---

# 

# \## Tipos de Defeitos Simulados

# 

# \* Nenhum

# \* Furo lateral

# \* Furo superior

# \* Amassado

# \* Esticado

# \* Falta de tampa

# \* Quebrado

# 

# ---

# 

# \## Tecnologias Utilizadas

# 

# \* \*\*Python 3\*\*

# \* \*\*NumPy\*\*

# \* \*\*SciPy\*\* (KD-Tree, Convex Hull)

# \* \*\*Matplotlib\*\* (visualização 3D)

# \* \*\*Tkinter\*\* (interface gráfica)

# \* \*\*PySerial\*\* (comunicação com Arduino)

# \* \*\*numpy-stl\*\* (leitura e exportação de STL)

# 

# ---

# 

# \## Como Executar

# 

# 1\. Clone o repositório

# 

# ```bash

# git clone https://github.com/seu-usuario/seu-repositorio.git

# ```

# 

# 2\. Instale as dependências

# 

# ```bash

# pip install numpy scipy matplotlib pyserial numpy-stl

# ```

# 

# 3\. Execute o sistema

# 

# ```bash

# python scanner\_3D.py

# ```

# 

# ---

# 

# \## Modo Real (Arduino)

# 

# O Arduino deve enviar dados no formato:

# 

# ```

# camada|distancia|angulo\_mesa|altura\_fuso

# ```

# 

# E finalizar a transmissão com:

# 

# ```

# FIM

# ```

# 

# ---

# 

# \## Estrutura do Projeto

# 

# ```

# scanner\_3D.py   # Código principal do sistema

# modelo\_ok.xyz   # Modelo de referência (gerado pelo sistema)

# README.md       # Documentação do projeto

# ```

# 

# ---

# 

# \## Autor

# 

# \*\*Yan de Lima Pereira\*\*

# 23 anos — Estudante de Python e Sistemas de Inspeção / Visão Computacional

# 

# ---

# 

# \## Status do Projeto

# 

# Projeto em desenvolvimento, utilizado para \*\*estudos e testes experimentais\*\* com foco em inspeção 3D e aprendiz

