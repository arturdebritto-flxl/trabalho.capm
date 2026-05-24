# CAPM - Analise Embraer (EMBJ3)

Projeto para analise do CAPM (Capital Asset Pricing Model) aplicado a Embraer S.A.

## Conteudo

- Codigo principal da analise: `main.py`
- Painel interativo Streamlit: `streamlit_app.py`
- Dados de saida em Excel: pasta `dados/`
- Bases do painel Streamlit: pasta `dados/streamlit/`
- Graficos: pasta `graficos/`
- Relatorio Word gerado: pasta `relatorio/`

## Pre-requisitos

- Python 3.10+ recomendado
- Ambiente virtual `venv`

## Periodo de analise

- Janeiro/2021 a Dezembro/2025, com 60 retornos mensais

## Fontes de dados

- Precos historicos da Embraer: arquivos COTAHIST da B3 em `dados/cotacoes_b3/`
- Ibovespa: Yahoo Finance, ticker `^BVSP`
- Selic mensal: Banco Central do Brasil, serie SGS 4390

## Instalacao e execucao no PowerShell

1. Criar e ativar o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Rodar a analise principal:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

4. Executar sem confirmacao e sobrescrever as saidas:

```powershell
.\.venv\Scripts\python.exe .\main.py --yes
```

5. Abrir o painel Streamlit:

```powershell
streamlit run streamlit_app.py
```

## Opcoes do script principal

- `--yes`: executa sem solicitar confirmacao.
- `--quiet`: mostra apenas avisos e erros.
- `--debug`: mostra mensagens detalhadas de depuracao.

## Saidas geradas

- `dados/analise_capm_embraer.xlsx`
- `dados/resultado_capm_embraer.xlsx`
- `dados/streamlit/fato_capm_mensal.csv`
- `dados/streamlit/resumo_indicadores.csv`
- `dados/streamlit/dimensao_calendario.csv`
- `dados/streamlit/metodologia_fontes.csv`
- `graficos/retornos_mensais_embraer_ibovespa.png`
- `graficos/regressao_capm.png`
- `relatorio/nota_tecnica_capm_embraer.docx`

## Painel Streamlit

O painel `streamlit_app.py` apresenta os resultados calculados pelo Python sem recalcular a base oficial. Ele consome os CSVs em `dados/streamlit/`, exibe os graficos salvos em `graficos/` e disponibiliza downloads do Excel, do relatorio Word e das bases CSV.

As principais telas do painel sao:

- Resumo dos indicadores CAPM
- Calculadora CAPM com beta, taxa livre de risco, retorno de mercado e retorno observado editaveis
- Serie mensal da Embraer, Ibovespa e Selic
- Graficos da analise e retorno acumulado
- Fontes, metodologia e limitacoes
- Downloads dos artefatos do trabalho

## Trabalhando no VS Code

1. Abra a pasta raiz do projeto:

```powershell
code .
```

2. Atualize todas as saidas:

```powershell
.\.venv\Scripts\python.exe .\main.py --yes
```

3. Rode o painel:

```powershell
streamlit run streamlit_app.py
```

4. Estrutura principal:

```text
main.py
streamlit_app.py
README.md
dados/
dados/streamlit/
graficos/
relatorio/
imagens/
```

## Como inserir os arquivos COTAHIST da B3

Baixe os arquivos COTAHIST anuais, por exemplo `COTAHIST_A2020.ZIP`, no site da B3 e coloque os ZIPs em `dados/cotacoes_b3/` antes de executar o script.

Os arquivos ZIP podem ser grandes, portanto nao e recomendado versiona-los no Git.

## Limitacoes principais

- Os precos extraidos dos arquivos da B3 nao sao ajustados por dividendos, bonificacoes ou outros proventos.
- A Selic mensal e usada como proxy da taxa livre de risco.
- O resultado e uma aplicacao academica do CAPM e nao constitui recomendacao financeira definitiva.

## Observacoes

- A pasta `.venv/` e os arquivos ZIP de `dados/cotacoes_b3/` estao no `.gitignore`.
- Se nao tiver o Git instalado, veja: https://git-scm.com/download/win

## Licenca

Uso educacional.
