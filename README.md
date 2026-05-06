# Gerador de Relatórios OAB

Aplicação desktop para gerar relatórios Excel a partir de arquivos XML exportados pelo sistema da OAB.

---

## Funcionalidades

- Lê arquivos XML no formato Microsoft Office Spreadsheet (gerados pela OAB)
- Gera relatório **Geral** com todos os registros
- Gera relatório **Geral Ativos** filtrando apenas advogados com categoria ativa (Advogado / Suplementar) e situação ativa
- Ajuste automático de largura de colunas e formatação de datas no Excel
- Interface gráfica simples — sem necessidade de conhecimento técnico

---

## Como usar o executável

1. Baixe o arquivo `Gerador_OAB.exe` da pasta `dist/` (ou da [aba Releases](../../releases))
2. Dê dois cliques para abrir — não precisa instalar nada
3. Clique em **Selecionar XML** e escolha o arquivo exportado da OAB
4. Confirme (ou altere) a **pasta de saída**
5. Marque os relatórios desejados e clique em **Gerar Relatórios**
6. A pasta de saída abrirá automaticamente ao concluir

---

## Como executar pelo código-fonte

### Pré-requisitos

- Python 3.10 ou superior
- pip

### Instalação

```bash
pip install -r requirements.txt
```

### Execução

```bash
python main.py
```

---

## Como gerar o executável (.exe)

Com o Python instalado, basta executar o script de build:

**Opção 1 — Dois cliques:**
```
build.bat
```

**Opção 2 — Terminal:**
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Gerador_OAB" --add-data "assets;assets" --add-data "core;core" --hidden-import lxml.etree --hidden-import openpyxl --hidden-import pandas main.py
```

O executável gerado ficará em `dist\Gerador_OAB.exe`.

---

## Estrutura do projeto

```
automationPyOAB-/
├── main.py              # Ponto de entrada
├── app.py               # Interface gráfica (Tkinter)
├── build.bat            # Script de build com um clique
├── requirements.txt     # Dependências Python
├── assets/
│   └── logo.png         # Logo da aplicação
└── core/
    ├── leitor.py        # Leitura e parsing do XML
    └── gerador.py       # Geração dos arquivos Excel
```

---

## Dependências

| Pacote       | Uso                              |
|--------------|----------------------------------|
| `pandas`     | Manipulação de dados             |
| `openpyxl`   | Geração de arquivos `.xlsx`      |
| `lxml`       | Parsing de XML                   |
| `Pillow`     | Carregamento de imagens (logo)   |
| `pyinstaller`| Geração do executável `.exe`     |

---

## Filtros do relatório "Geral Ativos"

**Categorias aceitas:** `ADVOGADO`, `SUPLEMENTAR`

**Situações aceitas:**
- ATIVO COM IMPEDIMENTO
- ATIVO PLENO
- EXECUTADO
- SUSPENSO EM OUTRA SECCIONAL
- SUSPENSO POR PROCESSO
