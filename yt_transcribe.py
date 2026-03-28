#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api>=1.0.0",
#   "yt-dlp>=2024.1.0",
# ]
# ///
"""
yt_transcribe.py — Transcrição de playlists e vídeos do YouTube via CLI.

Uso básico:
    ./yt_transcribe.py <URL>

Exemplos:
    ./yt_transcribe.py "https://youtube.com/playlist?list=PL..."
    ./yt_transcribe.py "https://youtu.be/dQw4w9WgXcQ"
    ./yt_transcribe.py "https://youtube.com/playlist?list=PL..." -o ./saida -l pt en -d 3
"""

import argparse
import http.cookiejar
import json
import re
import subprocess
import sys
import time
from pathlib import Path


# ── Helpers de texto ────────────────────────────────────────────────────────

def limpar_texto(texto: str) -> str:
    """Remove artefatos comuns de legendas automáticas do YouTube."""
    texto = re.sub(r"<[^>]+>", "", texto)       # tags HTML/YouTube
    texto = re.sub(r"\[.*?\]", "", texto)        # [Música], [Aplausos], etc.
    texto = re.sub(r"\s+", " ", texto)           # espaços múltiplos
    return texto.strip()


def sanitizar_nome(nome: str, max_len: int = 80) -> str:
    """Transforma um título em nome de arquivo seguro."""
    return re.sub(r'[\\/*?:"<>|]', "", nome)[:max_len]


# ── Cookies ──────────────────────────────────────────────────────────────────

NAVEGADORES_SUPORTADOS = ["chrome", "firefox", "brave", "edge", "safari", "opera", "chromium"]

def exportar_cookies_do_navegador(navegador: str, destino: Path) -> Path:
    """Usa yt-dlp para exportar cookies do navegador para um arquivo Netscape."""
    print(f"🍪 Exportando cookies do {navegador}...")
    arquivo = destino / "cookies.txt"
    try:
        subprocess.run(
            ["yt-dlp", f"--cookies-from-browser", navegador,
             "--cookies", str(arquivo),
             "--flat-playlist", "--print", "NA",
             "--no-warnings",
             "https://www.youtube.com"],
            capture_output=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Falha ao exportar cookies do {navegador}: {e.stderr.decode().strip()}")
        sys.exit(1)
    print(f"  ✅ Cookies salvos em: {arquivo}\n")
    return arquivo


def carregar_cookie_jar(caminho: Path) -> http.cookiejar.MozillaCookieJar:
    """Carrega um arquivo de cookies no formato Netscape/Mozilla."""
    jar = http.cookiejar.MozillaCookieJar()
    try:
        jar.load(str(caminho), ignore_discard=True, ignore_expires=True)
    except Exception as e:
        print(f"❌ Não foi possível carregar o arquivo de cookies: {e}")
        sys.exit(1)
    return jar


# ── Obtenção de vídeos ───────────────────────────────────────────────────────

def obter_videos(url: str, cookies: Path | None = None) -> list[dict]:
    """
    Usa yt-dlp para listar todos os vídeos de uma URL
    (funciona com playlist, canal ou vídeo único).
    """
    print(f"🔍 Buscando vídeos em: {url}")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|||%(title)s",
        "--no-warnings",
    ]
    if cookies:
        cmd += ["--cookies", str(cookies)]
    cmd.append(url)

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print("❌ yt-dlp não encontrado. Execute o script com:  uv run yt_transcribe.py")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao acessar a URL: {e.stderr.strip()}")
        sys.exit(1)

    videos = []
    for linha in resultado.stdout.strip().splitlines():
        if "|||" in linha:
            vid_id, titulo = linha.split("|||", 1)
            videos.append({"id": vid_id.strip(), "titulo": titulo.strip()})

    if not videos:
        print("❌ Nenhum vídeo encontrado na URL fornecida.")
        sys.exit(1)

    print(f"✅ {len(videos)} vídeo(s) encontrado(s).\n")
    return videos


# ── Transcrição ──────────────────────────────────────────────────────────────

def transcrever(video_id: str, idiomas: list[str],
                cookie_jar: http.cookiejar.MozillaCookieJar | None = None) -> str | None:
    """Busca a transcrição de um vídeo. Retorna texto limpo ou None."""
    from youtube_transcript_api import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeTranscriptApi,
    )

    try:
        api = YouTubeTranscriptApi(cookie_jar=cookie_jar)
        transcript = api.fetch(video_id, languages=idiomas)
        trechos = [limpar_texto(s.text) for s in transcript]
        return " ".join(t for t in trechos if t)
    except NoTranscriptFound:
        print("  ⚠️  Nenhuma transcrição nos idiomas solicitados.")
    except TranscriptsDisabled:
        print("  ⚠️  Transcrições desabilitadas para este vídeo.")
    except VideoUnavailable:
        print("  ⚠️  Vídeo indisponível ou privado.")
    except Exception as e:
        print(f"  ❌ Erro inesperado: {e}")
    return None


# ── Salvamento ───────────────────────────────────────────────────────────────

def salvar_individual(saida_dir: Path, titulo: str, video_id: str, texto: str, indice: int) -> Path:
    nome = saida_dir / f"{indice:02d}_{sanitizar_nome(titulo)}.txt"
    with open(nome, "w", encoding="utf-8") as f:
        f.write(f"Título : {titulo}\n")
        f.write(f"ID     : {video_id}\n")
        f.write(f"URL    : https://www.youtube.com/watch?v={video_id}\n")
        f.write("=" * 60 + "\n\n")
        f.write(texto)
    return nome


def salvar_completo(saida_dir: Path, url_origem: str, resultados: list[dict]) -> Path:
    caminho = saida_dir / "_COMPLETO.txt"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("TRANSCRIÇÃO COMPLETA\n")
        f.write(f"Origem : {url_origem}\n")
        f.write(f"Vídeos : {len(resultados)}\n")
        f.write("=" * 60 + "\n")
        for r in resultados:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"[{r['indice']:02d}] {r['titulo']}\n")
            f.write(f"URL: https://www.youtube.com/watch?v={r['id']}\n")
            f.write(f"{'=' * 60}\n\n")
            f.write(r["texto"])
            f.write("\n\n")
    return caminho


def salvar_relatorio(saida_dir: Path, url_origem: str, videos: list[dict],
                     resultados: list[dict], erros: list[dict]) -> Path:
    caminho = saida_dir / "_relatorio.json"
    dados = {
        "origem": url_origem,
        "total": len(videos),
        "transcritos": len(resultados),
        "falhas": len(erros),
        "videos_ok": [{"indice": r["indice"], "titulo": r["titulo"], "id": r["id"]} for r in resultados],
        "videos_falha": erros,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return caminho


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="yt_transcribe",
        description="Transcreve playlists e vídeos do YouTube usando legendas existentes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
exemplos:
  ./yt_transcribe.py "https://youtube.com/playlist?list=PL..."
  ./yt_transcribe.py "https://youtu.be/VIDEO_ID" -o ./saida
  ./yt_transcribe.py "https://youtube.com/playlist?list=PL..." -l pt en -d 3
  ./yt_transcribe.py "https://youtube.com/playlist?list=PL..." --cookies-do-navegador chrome
  ./yt_transcribe.py "https://youtube.com/playlist?list=PL..." --cookies ./cookies.txt
        """,
    )

    parser.add_argument(
        "url",
        help="URL da playlist, canal ou vídeo do YouTube",
    )
    parser.add_argument(
        "-o", "--saida",
        default="transcricoes",
        metavar="DIR",
        help="Pasta de destino das transcrições (padrão: ./transcricoes)",
    )
    parser.add_argument(
        "-l", "--idiomas",
        nargs="+",
        default=["pt", "pt-BR", "en"],
        metavar="LANG",
        help="Idiomas por prioridade (padrão: pt pt-BR en)",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=2.0,
        metavar="SEG",
        help="Segundos de espera entre vídeos para evitar bloqueio (padrão: 2)",
    )
    parser.add_argument(
        "--cookies",
        metavar="ARQUIVO",
        help="Caminho para arquivo de cookies no formato Netscape/txt (exportado pelo browser ou yt-dlp)",
    )
    parser.add_argument(
        "--cookies-do-navegador",
        metavar="NAVEGADOR",
        choices=NAVEGADORES_SUPORTADOS,
        help=f"Exporta cookies diretamente do navegador. Opções: {', '.join(NAVEGADORES_SUPORTADOS)}",
    )
    parser.add_argument(
        "--sem-arquivo-completo",
        action="store_true",
        help="Não gera o arquivo _COMPLETO.txt com todas as transcrições unidas",
    )
    parser.add_argument(
        "--sem-relatorio",
        action="store_true",
        help="Não gera o arquivo _relatorio.json",
    )

    return parser.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Verifica dependência
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        print("❌ Dependência não encontrada. Execute com:  uv run yt_transcribe.py <URL>")
        sys.exit(1)

    saida_dir = Path(args.saida)
    saida_dir.mkdir(parents=True, exist_ok=True)

    # ── Resolve cookies ──────────────────────────────────────────────────────
    cookie_path: Path | None = None
    cookie_jar: http.cookiejar.MozillaCookieJar | None = None

    if args.cookies_do_navegador:
        cookie_path = exportar_cookies_do_navegador(args.cookies_do_navegador, saida_dir)
    elif args.cookies:
        cookie_path = Path(args.cookies)
        if not cookie_path.exists():
            print(f"❌ Arquivo de cookies não encontrado: {cookie_path}")
            sys.exit(1)

    if cookie_path:
        cookie_jar = carregar_cookie_jar(cookie_path)
        print(f"🍪 Usando cookies de: {cookie_path}\n")

    # ── Busca e transcrição ──────────────────────────────────────────────────
    videos = obter_videos(args.url, cookies=cookie_path)
    resultados: list[dict] = []
    erros: list[dict] = []

    for i, video in enumerate(videos, start=1):
        vid_id = video["id"]
        titulo = video["titulo"]

        print(f"[{i:02d}/{len(videos)}] {titulo}")
        print(f"         https://youtu.be/{vid_id}")

        texto = transcrever(vid_id, args.idiomas, cookie_jar=cookie_jar)

        if texto:
            arquivo = salvar_individual(saida_dir, titulo, vid_id, texto, i)
            print(f"  ✅ Salvo → {arquivo.name}")
            resultados.append({"indice": i, "titulo": titulo, "id": vid_id, "texto": texto})
        else:
            erros.append({"indice": i, "titulo": titulo, "id": vid_id})

        if i < len(videos):
            time.sleep(args.delay)

    # Resumo
    print("\n" + "=" * 60)
    print(f"✅ Transcritos : {len(resultados)}/{len(videos)}")
    if erros:
        print(f"⚠️  Falhas     : {len(erros)}")
        for e in erros:
            print(f"   • [{e['indice']:02d}] {e['titulo']}")

    # Arquivo único com tudo
    if resultados and not args.sem_arquivo_completo:
        completo = salvar_completo(saida_dir, args.url, resultados)
        print(f"\n📄 Arquivo completo : {completo}")

    # Relatório JSON
    if not args.sem_relatorio:
        relatorio = salvar_relatorio(saida_dir, args.url, videos, resultados, erros)
        print(f"📊 Relatório JSON   : {relatorio}")

    print(f"\n📁 Saída em : {saida_dir.resolve()}/")


if __name__ == "__main__":
    main()