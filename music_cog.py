import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

# yt-dlp პარამეტრები (მუსიკისთვის ოპტიმიზებული)
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # შეიძლება დაეხმაროს ბლოკირების არიდებაში
}

# ffmpeg პარამეტრები (ხმის ნორმალიზებისთვის)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.25"' # ხმას ოდნავ დავუწიოთ
}

ytdl = yt_dlp.YoutubeDL(YDL_OPTIONS)

class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {} # აქ შევინახავთ, რომელ სერვერზე რომელ ხმოვან კლიენტშია ბოტი

    async def get_player(self, url_or_search: str, loop=None) -> discord.PCMVolumeTransformer:
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url_or_search, download=False))

        if 'entries' in data: # თუ ძებნისას რამდენიმე შედეგი იპოვა
            data = data['entries'][0]

        filename = data['url']
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS))

    # --- ბრძანებები ---
    music_group = app_commands.Group(name="music", description="Musikistvis")

    @music_group.command(name="join", description="Shemodis shen khmovan arkhshi")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("Shen ar khar khmovan arkhshi!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        if interaction.guild.voice_client is not None:
             await interaction.guild.voice_client.move_to(channel)
        else:
            self.voice_clients[interaction.guild.id] = await channel.connect()
        
        await interaction.response.send_message(f"Shemovedi `{channel.name}`-shi")

    @music_group.command(name="leave", description="Gadis khmovani arkhidan")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is None:
            await interaction.response.send_message("Me ar var khmovan arkhshi!", ephemeral=True)
            return
        
        await interaction.guild.voice_client.disconnect()
        if interaction.guild.id in self.voice_clients:
            del self.voice_clients[interaction.guild.id]
        await interaction.response.send_message("Gavedi arkhidan.")

    @music_group.command(name="play", description="Ukravs musikas YouTube-idan (saxeli an linki)")
    @app_commands.describe(search="Musikis saxeli an YouTube linki")
    async def play(self, interaction: discord.Interaction, search: str):
        if not interaction.user.voice:
            await interaction.response.send_message("Jer khmovan arkhshi shemodi!", ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            # თუ ბოტი არ არის არხში, შევდივართ მომხმარებლის არხში
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()
            self.voice_clients[interaction.guild.id] = voice_client

        if voice_client.is_playing() or voice_client.is_paused():
             voice_client.stop() # ვაჩერებთ მიმდინარე მუსიკას (შემდგომში რიგს დავამატებთ)

        await interaction.response.defer(thinking=True) # ბოტს ვაძლევთ დროს მოსაძებნად

        try:
            player = await self.get_player(search)
            # --- მნიშვნელოვანია: ვიწყებთ დაკვრას და ვამატებთ error callback-ს ---
            voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            
            # ვცდილობთ ავიღოთ ინფორმაცია ვიდეოზე ytdl-დან (შეიძლება იყოს ნელი)
            try:
                 loop = asyncio.get_event_loop()
                 data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False))
                 if 'entries' in data: data = data['entries'][0]
                 await interaction.followup.send(f'▶️ Axla ukravs: **{data.get("title", search)}**')
            except Exception as e:
                 print(f"Error getting video title: {e}")
                 await interaction.followup.send(f'▶️ Musikis chartva daiwyo...') # ზოგადი შეტყობინება

        except yt_dlp.utils.DownloadError as e:
            await interaction.followup.send(f"Shecdoma: Ver vipove video `{search}`. {e}")
        except Exception as e:
            await interaction.followup.send(f"Mokhda shecdoma musikis chartvisas: {e}")

    @music_group.command(name="pause", description="Apauzebs mimdinare musikas")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Dapauzda.")
        else:
            await interaction.response.send_message("Araferi ar ukravs.", ephemeral=True)

    @music_group.command(name="resume", description="Aghdgens dapauzebul musikas")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Gagrdzelda.")
        else:
            await interaction.response.send_message("Musika ar aris dapauzebuli.", ephemeral=True)

    @music_group.command(name="stop", description="Agherebs dakvras da gadis arkhidan")
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            if interaction.guild.id in self.voice_clients:
                 del self.voice_clients[interaction.guild.id]
            await interaction.response.send_message("⏹️ Gavcherdi da gavedi.")
        else:
            await interaction.response.send_message("Me ar var khmovan arkhshi!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
