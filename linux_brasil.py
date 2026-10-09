import html
import json
import re
import sys
import urllib.request
import urllib.parse
import feedparser
import ollama
import time
import urllib.error
import subprocess

MODEL_NAME = "qwen2.5:3b"
USER_AGENT = "desktop:com.lucas.resumidor:v1.0 (by /u/lucas_arch)"


def fetch_with_retry(url: str, retries: int = 10) -> bytes:
    """Busca conteúdo de uma URL com tratamento de User-Agent, retries e rate limit (429)."""
    encoded_url = urllib.parse.quote(url, safe=":/?&=#")
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(retries):
        try:
            req = urllib.request.Request(encoded_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                sleep_time = 20 * (attempt + 1)
                print(
                    f"\n[Aviso: Rate limit (429) em {url}. Tentando novamente em {sleep_time}s...]"
                )
                time.sleep(sleep_time)
                continue
            raise e
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(10)
                continue
            raise e
    raise Exception(f"Falha ao buscar {url} após {retries} tentativas.")


def verificar_imagem(raw_html: str, link: str) -> tuple[bool, str]:
    """Detecta se o post possui imagem/mídia associada."""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html)
    if img_match:
        return True, html.unescape(img_match.group(1))

    if (
        any(link.endswith(ext) for ext in [".jpg", ".png", ".jpeg", ".gif", ".webp"])
        or "i.redd.it" in link
    ):
        return True, link

    return False, ""


def obter_comentarios_top(post_url: str, limite: int = 3) -> list[str]:
    """Busca comentários via JSON descartando a busca imediatamente se tomar 429."""
#    clean_url = post_url.split("?")[0].rstrip("/")
#    json_url = f"{clean_url}.json?sort=top"
#    encoded_url = urllib.parse.quote(json_url, safe=":/?&=#")
#
#    headers = {
#       "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
#        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
#        "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
#        "DNT": "1",
#        "Connection": "keep-alive",
#        "Upgrade-Insecure-Requests": "1",
#    }
#
#    try:
#        req = urllib.request.Request(encoded_url, headers=headers)
#        with urllib.request.urlopen(req, timeout=5) as resp:
#            data = json.loads(resp.read().decode("utf-8"))
#            comentarios = []
#            if len(data) > 1:
#                children = data[1]["data"]["children"]
#                for child in children:
#                    if child["kind"] == "t1":
#                        body = child["data"].get("body", "").strip()
#                        if body and body not in ["[deleted]", "[removed]"]:
#                            comentarios.append(body[:300])
#                    if len(comentarios) >= limite:
#                        break
#            return comentarios

#    # --- ENTRA AQUI ---
#    except urllib.error.HTTPError as e:
#        if e.code == 429:
#            print(" [429 Rate Limit: pulando comentários para não travar o terminal]")
#            return []
#        print(f"\n[Aviso: Erro HTTP ao buscar comentários ({e})]")
#        return []
#    except Exception as e:
#        print(f"\n[Aviso: Falha geral ao carregar comentários ({e})]")
#        return []

    return []
def extrair_posts_recentes(
    subreddit: str = "linuxbrasil", limite: int = 5
) -> list[dict]:
    """Puxa posts do RSS do subreddit e complementa com comentários e detecção de mídia."""
    rss_url = f"https://www.reddit.com/r/{subreddit}/new.rss"

    try:
        xml_data = fetch_with_retry(rss_url)
    except Exception as e:
        raise Exception(f"Erro ao baixar o RSS do r/{subreddit}: {e}")

    feed = feedparser.parse(xml_data)
    if not feed.entries:
        raise Exception(f"Nenhum post encontrado no r/{subreddit}.")

    posts = []
    for entry in feed.entries[:limite]:
        titulo = entry.get("title", "Sem título")
        link = entry.get("link", "")
        raw_html = entry.get("summary", "")

        eh_imagem, url_imagem = verificar_imagem(raw_html, link)

        texto_limpo = re.sub(r"<[^<]+?>", "", raw_html)
        texto_limpo = html.unescape(texto_limpo).strip()

        # Delay conservador entre posts
        time.sleep(5)
        comentarios = obter_comentarios_top(link, limite=3)

        posts.append(
            {
                "titulo": titulo,
                "link": link,
                "conteudo": texto_limpo if texto_limpo else "(Post sem corpo de texto)",
                "eh_imagem": eh_imagem,
                "url_imagem": url_imagem,
                "comentarios": comentarios,
            }
        )

    return posts


def resumir_com_ollama(post: dict):
    system_prompt = (
        "Você é um assistente de síntese extremamente preciso.\n"
        "Sua tarefa é resumir o post do Reddit e a discussão dos comentários usando APENAS as informações fornecidas.\n\n"
        "REGRAS ESTRITAS:\n"
        "- NÃO invente fatos, detalhes ou descrições visuais não contidas no texto fornecido.\n"
        "- Se a imagem não tiver descrição textual, não tente descrevê-la, apenas cite que 'Contém Imagem/Mídia'.\n"
        "- NÃO use formatação Markdown (proibido **, #, *, _, ---).\n"
        "- Escreva em TEXTO PURO (ASCII plano).\n"
        "- Seja conciso.\n"
        "- Estruture em 3 seções: CONTEXTO DO POST, CONTEÚDO e REPERCUSSÃO DOS COMENTÁRIOS."
    )

    detalhes = [f"Título: {post['titulo']}"]

    if post["eh_imagem"]:
        detalhes.append("Tipo de Post: Contém Imagem/Mídia")

    detalhes.append(f"Conteúdo do Post: {post['conteudo']}")

    if post["comentarios"]:
        coments_formatted = "\n".join([f"- {c}" for c in post["comentarios"]])
        detalhes.append(f"Principais Comentários da Comunidade:\n{coments_formatted}")
    else:
        detalhes.append(
            "Principais Comentários da Comunidade: Nenhum comentário carregado."
        )

    user_prompt = f"Resuma o post e os comentários abaixo:\n\n" + "\n\n".join(detalhes)

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0.0,
            "top_p": 0.1,
            "num_ctx": 1024,
        },
        keep_alive="5m",
        stream=False,
    )

    return response["message"]["content"]

def resumir_r_linux_brasil():
    SUBREDDIT = "linuxbrasil"
    LIMITE = 5

    print(f"=== BUSCANDO OS {LIMITE} POSTS MAIS RECENTES DO r/{SUBREDDIT} ===\n")

    try:
        posts = extrair_posts_recentes(SUBREDDIT, limite=LIMITE)
    except Exception as e:
        print(f"Erro CRÍTICO na extração: {e}")
        try:
            subprocess.run(["notify-send", "Erro no Resumidor", str(e)])
        except:
            pass
        raise e

    resultados = []
    for idx, post in enumerate(posts, start=1):
        print("=" * 65)
        print(f"POST [{idx}/{LIMITE}]")
        print(f"TÍTULO: {post['titulo']}")
        print(f"LINK:   {post['link']}")
        if post["eh_imagem"]:
            print(f"MÍDIA:  [Imagem Detectada: {post['url_imagem']}]")
        print("-" * 65)
        print("RESUMO:")

        try:
            resumo_texto = resumir_com_ollama(post)
            print(resumo_texto)
        except Exception as e:
            print(f"Erro ao resumir o post {idx}: {e}")
            resumo_texto = f"Erro ao resumir o post: {e}"
            try:
                subprocess.run(["notify-send", f"Erro no Resumo do post {idx}", str(e)])
            except:
                pass

        post_formatado = (
            f"**POST [{idx}/{LIMITE}]**\n"
            f"**TÍTULO:** {post['titulo']}\n"
            f"**LINK:** {post['link']}\n"
        )
        if post["eh_imagem"]:
            post_formatado += f"**MÍDIA:** [Imagem Detectada: {post['url_imagem']}]\n"
        post_formatado += f"**RESUMO:**\n{resumo_texto}"

        resultados.append(post_formatado)
        print("=" * 65)
        print("\n")

    return resultados

if __name__ == "__main__":
    resumir_r_linux_brasil()