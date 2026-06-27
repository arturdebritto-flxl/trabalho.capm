# Analise CAPM

Ferramenta Python generica para calcular CAPM (Capital Asset Pricing Model) a
partir de precos de um ativo, de um indice de mercado e de uma serie de taxa
livre de risco. A configuracao academica da Embraer fica apenas como exemplo
reproduzivel em `configs/embraer.toml`.

## Arquitetura

- `src/capm/config.py`: leitura e validacao de configuracoes TOML.
- `src/capm/data_sources.py`: fontes CSV/offline, Yahoo Finance, BCB e B3.
- `src/capm/returns.py`: precos mensais, retornos, RF mensal e anualizacao.
- `src/capm/regression.py`: OLS com constante e beta diagnostico por covariancia.
- `src/capm/model.py`: orquestracao do calculo CAPM generico.
- `src/capm/exports.py`: exportacao de Excel, CSVs do painel e graficos PNG.
- `main.py`: CLI.
- `streamlit_app.py`: painel generico.

## Instalacao

Python suportado: 3.11 e 3.12.

Windows:

```powershell
git clone <URL_DO_REPOSITORIO>
cd <PASTA_DO_REPOSITORIO>
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

macOS:

```bash
git clone <URL_DO_REPOSITORIO>
cd <PASTA_DO_REPOSITORIO>
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install -r requirements-dev.txt
```

## Uso por CLI

Com configuracao offline:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/example.toml --offline --yes
```

Com o exemplo academico da Embraer:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/embraer.toml --offline --yes
```

No macOS:

```bash
./.venv/bin/python main.py --config configs/example.toml --offline --yes
./.venv/bin/python main.py --config configs/embraer.toml --offline --yes
```

Com Yahoo Finance e taxa livre constante:

```powershell
.\.venv\Scripts\python.exe main.py --ticker PETR4.SA --market ^BVSP --start 2018-01-01 --end 2025-12-31 --source yahoo --risk-free-source annual_constant --risk-free-annual-rate 10 --yes
```

Com arquivos proprios:

```powershell
.\.venv\Scripts\python.exe main.py --ticker ATIVO --market MERCADO --start 2024-01-01 --end 2024-12-31 --source csv --asset-prices-csv caminho/ativo.csv --market-prices-csv caminho/mercado.csv --risk-free-source csv --risk-free-csv caminho/taxa_livre.csv --output-dir dados --yes
```

Os CSVs de precos devem conter `Data` e `preco` (ou `Close`). O CSV da
taxa livre deve conter `Data` e `rf_anual`, em percentual ao ano. Datas devem
ser unicas e validas; precos devem ser numericos, finitos e positivos; a taxa
livre deve ser numerica e finita. As tres series precisam cobrir os mesmos
meses do periodo analisado, incluindo o mes anterior ao inicio para calcular
o primeiro retorno mensal.

## Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

```bash
./.venv/bin/python -m streamlit run streamlit_app.py
```

O painel permite selecionar uma configuracao, ajustar ticker, mercado, datas,
fonte de precos e taxa livre de risco, enviar os tres CSVs locais, visualizar
beta, alfa, R2, retornos, CAPM preciso, CAPM arredondado e baixar Excel/graficos.

## Fontes

- `offline`/`csv`: arquivos locais com colunas `Data` e `preco`.
- `yahoo`: precos de fechamento via Yahoo Finance.
- `bcb_sgs`: taxa livre anual via Banco Central.
- `b3`: COTAHIST local para ativos brasileiros, quando configurado.

## Metodologia

- Precos mensais: `precos_diarios.resample("ME").last()`.
- Retornos: `pct_change()`.
- RF mensal, quando a entrada e anual: `(1 + rf_anual / 100) ** (1 / 12) - 1`.
- Retornos excedentes: retorno do ativo/mercado menos RF mensal.
- Regressao: `excesso_ativo = alfa + beta * excesso_mercado + erro`.
- OLS usa constante explicita.
- Beta principal: coeficiente angular da regressao dos retornos excedentes.
- Beta por covariancia/variancia: apenas diagnostico.
- Periodo anualizado: dias entre os precos efetivamente usados dividido por 365.
- CAPM preciso: `rf + beta * (rm - rf)`.
- CAPM academico: `round(capm_preciso, 3)`.
- Classificacao academica: compara retorno anualizado do ativo com o CAPM
  arredondado.

## Saidas

Os nomes usam um slug seguro da analise:

- `dados/analise_capm_<slug>.xlsx`
- `dados/resultado_capm_<slug>.xlsx`
- `dados/dados_capm_<slug>.xlsx`
- `dados/graficos/retornos_mensais_<slug>.png`
- `dados/graficos/regressao_capm_<slug>.png`
- `dados/streamlit/<slug>/*.csv`

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\ruff.exe check . --no-cache
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall main.py streamlit_app.py src tests
.\.venv\Scripts\python.exe main.py --config configs/example.toml --offline --yes
.\.venv\Scripts\python.exe main.py --config configs/embraer.toml --offline --yes
```

No macOS, execute as mesmas verificacoes substituindo
`.\.venv\Scripts\python.exe` por `./.venv/bin/python` e `ruff.exe` por
`./.venv/bin/ruff`.

## Exemplo academico: Embraer

`configs/embraer.toml` contem o estudo academico com ativo Embraer S.A.,
mercado Ibovespa, CDI como taxa livre de risco e regra de ticker historico
`EMBR3`/`EMBJ3`. Essa configuracao nao faz parte do nucleo generico.

## Limitacoes

Esta ferramenta tem finalidade academica e educacional. A classificacao gerada
nao constitui recomendacao financeira profissional. Fontes externas como Yahoo,
Banco Central e B3 podem ficar indisponiveis ou revisar dados.
