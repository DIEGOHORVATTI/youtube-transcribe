#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "youtube-transcript-api==0.6.3",
#   "yt-dlp>=2024.1.0",
#   "requests>=2.31.0",
# ]
# ///
"""
yt_transcribe.py — Transcrição de playlists e vídeos do YouTube via CLI.

NOTA: Usa youtube-transcript-api==0.6.3 (última versão com suporte a cookies/proxy).
As versões 1.x desabilitaram autenticação por cookies temporariamente.

Uso básico:
    ./yt_transcribe.py <URL>

Exemplos:
    ./yt_transcribe.py "https://youtube.com/playlist?list=PL..."
    ./yt_transcribe.py "https://youtu.be/VIDEO_ID" -o ./saida
    ./yt_transcribe.py "URL" -l pt en -d 3
    ./yt_transcribe.py "URL" --cookies-do-navegador chrome
    ./yt_transcribe.py "URL" --cookies ./cookies.txt
    ./yt_transcribe.py "URL" --proxy http://user:pass@host:porta
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


NAVEGADORES_SUPORTADOS = ["chrome", "firefox", "brave", "edge", "safari", "opera", "chromium"]


# ── Helpers de texto ─────────────────────────────────────────────────────────

def limpar_texto(texto: str) -> str:
    """Remove artefatos comuns de legendas automáticas do YouTube."""
    texto = re.sub(r"<[^>]+>", "", texto)    # tags HTML/YouTube
    texto = re.sub(r"\[.*?\]", "", texto)     # [Música], [Aplausos], etc.
    texto = re.sub(r"\s+", " ", texto)        # espaços múltiplos
    return texto.strip()


def sanitizar_nome(nome: str, max_len: int = 80) -> str:
    """Transforma um título em nome de arquivo seguro."""
    return re.sub(r'[\\/*?:"<>|]', "", nome)[:max_len]


# ── Cookies e proxy ──────────────────────────────────────────────────────────

def exportar_cookies_do_navegador(navegador: str, destino: Path) -> Path:
    """Usa yt-dlp para exportar cookies do navegador para arquivo Netscape."""
    print(f"🍪 Exportando cookies do {navegador}...")
    arquivo = destino / "cookies.txt"
    try:
        subprocess.run(
                [
                    "yt-dlp",
                    "--cookies-from-browser", navegador,
                    "--cookies", str(arquivo),
                    "--skip-download",     
                    "--no-warnings",
                    "--print", "NA",
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                ],
                capture_output=True,
                check=True,
            )
    except subprocess.CalledProcessError as e:
        print(f"❌ Falha ao exportar cookies do {navegador}:\n{e.stderr.decode().strip()}")
        sys.exit(1)
    print(f"  ✅ Cookies salvos em: {arquivo}\n")
    return arquivo


def carregar_cookies_header(cookies_path: Path | None = None) -> str | None:
    """Converte cookies Netscape para header HTTP Cookie."""
    import http.cookiejar

    if not cookies_path:
        return None

    jar = http.cookiejar.MozillaCookieJar()
    try:
        jar.load(str(cookies_path), ignore_discard=True, ignore_expires=True)
    except Exception as e:
        print(f"❌ Erro ao carregar cookies: {e}")
        sys.exit(1)

    pares = [f"{c.name}={c.value}" for c in jar]
    return "; ".join(pares) if pares else None


# ── Obtenção de vídeos ───────────────────────────────────────────────────────

def obter_videos(url: str, cookies_path: Path | None = None) -> list[dict]:
    """
    Usa yt-dlp para listar todos os vídeos de uma URL.
    Funciona com playlist, canal ou vídeo único.
    """
    print(f"🔍 Buscando vídeos em: {url}")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|||%(title)s",
        "--no-warnings",
    ]
    if cookies_path:
        cmd += ["--cookies", str(cookies_path)]
    cmd.append(url)

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print("❌ yt-dlp não encontrado. Execute:  uv run yt_transcribe.py <URL>")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao acessar a URL:\n{e.stderr.strip()}")
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

def transcrever(
    video_id: str,
    idiomas: list[str],
    cookies_header: str | None = None,
    proxies: dict | None = None,
) -> str | None:
    """
    Busca a transcrição de um vídeo via youtube-transcript-api 0.6.3.

    Nota: a assinatura dessa versão não aceita `http_client`.
    """
    from youtube_transcript_api import (
        CouldNotRetrieveTranscript,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeTranscriptApi,
    )

    try:
        kwargs = {"languages": idiomas}
        if cookies_header:
            kwargs["cookies"] = cookies_header
        if proxies:
            kwargs["proxies"] = proxies

        transcript = YouTubeTranscriptApi.get_transcript(video_id, **kwargs)
        trechos = [limpar_texto(item["text"]) for item in transcript]
        return " ".join(t for t in trechos if t)

    except NoTranscriptFound:
        print("  ⚠️  Nenhuma transcrição nos idiomas solicitados.")
    except TranscriptsDisabled:
        print("  ⚠️  Transcrições desabilitadas para este vídeo.")
    except VideoUnavailable:
        print("  ⚠️  Vídeo indisponível ou privado.")
    except CouldNotRetrieveTranscript as e:
        print(f"  ⚠️  Não foi possível obter transcrição: {e}")
    except Exception as e:
        print(f"  ❌ Erro inesperado: {e}")
    return None


# ── Salvamento ───────────────────────────────────────────────────────────────

def salvar_individual(saida_dir: Path, titulo: str, video_id: str,
                      texto: str, indice: int) -> Path:
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
        "videos_ok": [
            {"indice": r["indice"], "titulo": r["titulo"], "id": r["id"]}
            for r in resultados
        ],
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
  ./yt_transcribe.py "URL" -l pt en -d 3
  ./yt_transcribe.py "URL" --cookies-do-navegador chrome
  ./yt_transcribe.py "URL" --cookies ./cookies.txt
  ./yt_transcribe.py "URL" --proxy http://usuario:senha@host:porta
        """,
    )
    parser.add_argument("url", help="URL da playlist, canal ou vídeo do YouTube")
    parser.add_argument(
        "-o", "--saida", default="transcricoes", metavar="DIR",
        help="Pasta de destino (padrão: ./transcricoes)",
    )
    parser.add_argument(
        "-l", "--idiomas", nargs="+", default=["pt", "pt-BR", "en"], metavar="LANG",
        help="Idiomas por prioridade (padrão: pt pt-BR en)",
    )
    parser.add_argument(
        "-d", "--delay", type=float, default=2.0, metavar="SEG",
        help="Segundos de espera entre vídeos (padrão: 2)",
    )
    parser.add_argument(
        "--cookies", metavar="ARQUIVO",
        help="Arquivo de cookies no formato Netscape/txt",
    )
    parser.add_argument(
        "--cookies-do-navegador", metavar="NAVEGADOR",
        choices=NAVEGADORES_SUPORTADOS,
        help=f"Exporta cookies direto do navegador. Opções: {', '.join(NAVEGADORES_SUPORTADOS)}",
    )
    parser.add_argument(
        "--proxy", metavar="URL",
        help="URL de proxy HTTP/HTTPS (ex: http://user:pass@host:porta)",
    )
    parser.add_argument(
        "--sem-arquivo-completo", action="store_true",
        help="Não gera o _COMPLETO.txt",
    )
    parser.add_argument(
        "--sem-relatorio", action="store_true",
        help="Não gera o _relatorio.json",
    )
    return parser.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        print("❌ Dependência não encontrada. Execute:  uv run yt_transcribe.py <URL>")
        sys.exit(1)

    saida_dir = Path(args.saida)
    saida_dir.mkdir(parents=True, exist_ok=True)

    # ── Resolve autenticação / proxy ─────────────────────────────────────────
    cookies_path: Path | None = None
    cookies_header: str | None = None
    proxies: dict[str, str] | None = None

    if args.cookies_do_navegador:
        cookies_path = exportar_cookies_do_navegador(args.cookies_do_navegador, saida_dir)
    elif args.cookies:
        cookies_path = Path(args.cookies)
        if not cookies_path.exists():
            print(f"❌ Arquivo de cookies não encontrado: {cookies_path}")
            sys.exit(1)

    if cookies_path:
        cookies_header = carregar_cookies_header(cookies_path)
        print(f"🍪 Usando cookies de: {cookies_path}\n")

    if args.proxy:
        proxies = {"http": args.proxy, "https": args.proxy}
        print(f"🌐 Usando proxy: {args.proxy}\n")

    # ── Listagem e transcrição ───────────────────────────────────────────────
    videos = obter_videos(args.url, cookies_path=cookies_path)
    resultados: list[dict] = []
    erros: list[dict] = []

    for i, video in enumerate(videos, start=1):
        vid_id = video["id"]
        titulo = video["titulo"]

        print(f"[{i:02d}/{len(videos)}] {titulo}")
        print(f"         https://youtu.be/{vid_id}")

        texto = transcrever(
            vid_id,
            args.idiomas,
            cookies_header=cookies_header,
            proxies=proxies,
        )

        if texto:
            arquivo = salvar_individual(saida_dir, titulo, vid_id, texto, i)
            print(f"  ✅ Salvo → {arquivo.name}")
            resultados.append({"indice": i, "titulo": titulo, "id": vid_id, "texto": texto})
        else:
            erros.append({"indice": i, "titulo": titulo, "id": vid_id})

        if i < len(videos):
            time.sleep(args.delay)

    # ── Resumo ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✅ Transcritos : {len(resultados)}/{len(videos)}")
    if erros:
        print(f"⚠️  Falhas     : {len(erros)}")
        for e in erros:
            print(f"   • [{e['indice']:02d}] {e['titulo']}")

    if resultados and not args.sem_arquivo_completo:
        completo = salvar_completo(saida_dir, args.url, resultados)
        print(f"\n📄 Arquivo completo : {completo}")

    if not args.sem_relatorio:
        relatorio = salvar_relatorio(saida_dir, args.url, videos, resultados, erros)
        print(f"📊 Relatório JSON   : {relatorio}")

    print(f"\n📁 Saída em : {saida_dir.resolve()}/")


if __name__ == "__main__":
    main()