import asyncio
import io
import os
import subprocess as sp

import discord
import mss
from dotenv import load_dotenv
from linux_brasil import resumir_r_linux_brasil
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)


async def capture_screenshot() -> bytes:
    def capturar() -> bytes:
        with mss.MSS() as tela:
            imagem = tela.grab(tela.monitors[0])
            return mss.tools.to_png(imagem.rgb, imagem.size)

    return await asyncio.to_thread(capturar)


async def format_uptime() -> str:
    try:
        resultado = sp.run(["uptime", "-p"], capture_output=True, text=True, check=True)
        texto = resultado.stdout.strip()
        if texto.startswith("up "):
            texto = texto[3:]

        traducao = {
            "day": "d",
            "days": "d",
            "hour": "h",
            "hours": "h",
            "minute": "m",
            "minutes": "m",
        }

        for ingles, portugues in traducao.items():
            texto = texto.replace(ingles, portugues)

        return texto or "Não foi possível obter o uptime."
    except (FileNotFoundError, sp.CalledProcessError):
        return "Não foi possível obter o uptime do sistema."


@bot.event
async def on_ready():
    print(f"Conectado como {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print(f"{message.author}: {message.content}")

    if message.content.startswith("!shut"):
        await message.channel.send("Desligando pc...")
        sp.Popen(["shutdown", "now"])
    elif message.content.startswith("!rebo"):
        await message.channel.send("Reiniciando pc...")
        sp.Popen(["reboot"])
    elif message.content.startswith("!resu"):
        await message.channel.send("Iniciando o resumo dos posts do r/linuxbrasil...")
        try:
            resultados = await asyncio.to_thread(resumir_r_linux_brasil)
            for res in resultados:
                if len(res) > 2000:
                    res = res[:1997] + "..."
                await message.channel.send(res)
        except Exception as e:
            await message.channel.send(f"Erro ao resumir os posts: {e}")
    elif message.content.startswith("!fast"):
        fastfetch = sp.Popen(["fastfetch"], stdout=sp.PIPE, stderr=sp.PIPE)
        await message.channel.send(fastfetch.stdout.read().decode("utf-8"))
    elif message.content.startswith("!up"):
        await message.channel.send(await format_uptime())
    elif message.content.startswith("!abrir"):
        message_content = message.content.split(" ", 1)
        if len(message_content) < 2:
            await message.channel.send("Por favor, forneça o caminho do arquivo ou programa a ser aberto.")
            return
        sp.Popen([message_content[1]])
    elif message.content.startswith("!print"):
        try:
            screenshot = await capture_screenshot()
            arquivo = discord.File(io.BytesIO(screenshot), filename="screenshot.png")
            await message.channel.send(file=arquivo)
        except Exception as error:
            await message.channel.send(f"Erro ao capturar a tela: {error}")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("A variável DISCORD_TOKEN não foi definida no ambiente.")
    bot.run(token)
