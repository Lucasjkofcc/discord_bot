import asyncio
import io
import os
import subprocess as sp
import sys

import discord
import mss
from dotenv import load_dotenv
from linux_brasil import resumir_r_linux_brasil
load_dotenv()
shutdown_command = None
reboot_command = None
intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

if sys.platform.startswith("win"):
    shutdown_command = "shutdown /s /f /t 0"
    reboot_command = "shutdown /r /f /t 0"
elif sys.platform.startswith("linux"):
    shutdown_command = "shutdown now"
    reboot_command = "reboot"
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


async def atualizar_sistema(channel):
    await channel.send("Iniciando atualização via paru...")
    try:
        resultado = await asyncio.to_thread(
            lambda: sp.run(["paru", "-Syu", "--noconfirm"], capture_output=True, text=True)
        )

        if resultado.returncode == 0:
            await channel.send("Atualização concluída.")
        else:
            erro = (resultado.stderr or resultado.stdout or "Erro desconhecido").strip()
            await channel.send(f"Atualização finalizada com erro: {erro[:1500]}")
    except FileNotFoundError:
        await channel.send("Comando `paru` não foi encontrado no sistema.")
    except Exception as e:
        await channel.send(f"Erro ao atualizar o sistema: {e}")


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
        sp.Popen(shutdown_command,shell=True)
    elif message.content.startswith("!rebo"):
        await message.channel.send("Reiniciando pc...")
        sp.Popen(reboot_command,shell=True)
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
    elif message.content.startswith("!pc_se"):
        sp.Popen(["/home/lucas/Projetos/anti_curioso/dist/pc_seguro"])
        await message.channel.send("pc_seguro iniciado.")
    elif message.content.startswith("!pc_na"):
        sp.Popen(["pkill", "pc_seguro"])
        await message.channel.send("pc_seguro encerrado.")
    elif message.content.startswith("!atua") or message.content.startswith("!upda"):
        await atualizar_sistema(message.channel)

    elif message.content.startswith("!abrir") or message.content.startswith("!rodar") or message.content.startswith("!exec"):
        message_content = message.content.split(" ", 1)[1:]
        message_content = " ".join(message_content)
        if len(message_content) < 1:
            await message.channel.send("Por favor, forneça o caminho do arquivo ou programa a ser aberto.")
            return
        await message.channel.send(f"rodando: {message_content}")
        sp.Popen(message_content,shell=True)
    elif message.content.startswith("!print") or message.content.startswith("!tela"):
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
