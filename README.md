# yt_transcribe

Ferramenta de linha de comando para transcrever playlists e vídeos do YouTube usando as legendas disponíveis (manuais ou automáticas). Sem instalação manual de dependências — basta ter o [uv](https://docs.astral.sh/uv/) instalado.

---

## Requisitos

- Python 3.11 ou superior
- [uv](https://docs.astral.sh/uv/) — gerenciador de pacotes/ambiente

### Instalando o uv

```bash
# macOS e Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> O uv instala todas as dependências Python automaticamente na primeira execução. Não é necessário rodar `pip install` manualmente.

---

## Instalação

```bash
# Clone ou baixe o repositório
git clone https://github.com/DIEGOHORVATTI/youtube-transcribe.git
cd youtube-transcribe

# Dê permissão de execução ao script
chmod +x yt_transcribe.py
```

---

## Uso

```bash
./yt_transcribe.py <URL> [opções]
```

A `<URL>` pode ser:
- Uma **playlist** do YouTube
- Um **vídeo** individual
- A página de **vídeos de um canal**

---

## Exemplos

```bash
# Transcrever uma playlist inteira (configurações padrão)
./yt_transcribe.py "https://youtube.com/playlist?list=PLxxxx"

# Especificar pasta de saída
./yt_transcribe.py "https://youtube.com/playlist?list=PLxxxx" -o ./minhas-transcricoes

# Transcrever um vídeo único
./yt_transcribe.py "https://youtu.be/VIDEO_ID"

# Alterar idiomas por prioridade (espanhol, depois inglês)
./yt_transcribe.py "https://youtube.com/playlist?list=PLxxxx" -l es en

# Aumentar delay entre vídeos (útil para playlists grandes)
./yt_transcribe.py "https://youtube.com/playlist?list=PLxxxx" -d 5

# Não gerar o arquivo unificado nem o relatório JSON
./yt_transcribe.py "https://youtube.com/playlist?list=PLxxxx" --sem-arquivo-completo --sem-relatorio
```

---

## Opções

| Opção | Padrão | Descrição |
|---|---|---|
| `url` | — | URL da playlist ou vídeo *(obrigatório)* |
| `-o`, `--saida` | `./transcricoes` | Pasta de destino das transcrições |
| `-l`, `--idiomas` | `pt pt-BR en` | Idiomas por ordem de prioridade |
| `-d`, `--delay` | `2` | Segundos de espera entre vídeos |
| `--sem-arquivo-completo` | — | Não gera o `_COMPLETO.txt` |
| `--sem-relatorio` | — | Não gera o `_relatorio.json` |

---

## Arquivos gerados

Após a execução, a pasta de saída (`./transcricoes/` por padrão) conterá:

```
transcricoes/
├── 01_Titulo do primeiro video.txt
├── 02_Titulo do segundo video.txt
├── ...
├── _COMPLETO.txt       ← todas as transcrições unidas em um só arquivo
└── _relatorio.json     ← metadados: quais vídeos funcionaram e quais falharam
```

Cada arquivo `.txt` individual contém:

```
Título : Nome do vídeo
ID     : abc123xyz
URL    : https://www.youtube.com/watch?v=abc123xyz
============================================================

Conteúdo da transcrição...
```

---

## Limitações

- O script depende das **legendas existentes** no YouTube (manuais ou automáticas geradas pelo próprio YouTube). Ele **não transcreve o áudio diretamente**.
- Se um vídeo não tiver legenda em nenhum dos idiomas configurados, ele será listado como falha no relatório e o script continuará nos próximos.
- Vídeos privados ou indisponíveis são ignorados automaticamente.

---

## Dependências

Gerenciadas automaticamente pelo `uv` via metadados PEP 723 embutidos no script:

| Pacote | Função |
|---|---|
| `youtube-transcript-api` | Busca e extrai as legendas dos vídeos |
| `yt-dlp` | Lista os vídeos de playlists e canais |

---

## Licença

MIT