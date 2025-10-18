import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import requests
import dateutil.parser

YOUTUBE_DB = "youtube.json"

def load_yt_data():
    if not os.path.exists(YOUTUBE_DB): return {}
    try:
        with open(YOUTUBE_DB, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_yt_data(data):
    with open(YOUTUBE_DB, "w") as f: json.dump(data, f, indent=4)

class YouTubeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_youtube.start()

    def cog_unload(self):
        self.check_youtube.cancel()

    youtube_group = app_commands.Group(name="youtube", description="YouTube shetyobinebebis martva")

    @youtube_group.command(name="add", description="Amatebs YouTube arkhs dasakvirveblad")
    @app_commands.describe(
        youtube_channel_id="arkhis ID (mag: UClgRkhTL3_hImCAmdLfDE4g)",
        discord_channel="arkhi sadac daideba shetyobineba",
        notify_type="ra shetyobineba gaigzavnos?"
    )
    @app_commands.choices(notify_type=[
        app_commands.Choice(name="Axali Videoebi", value="video"),
        app_commands.Choice(name="Laiv Strimebi", value="live"),
        app_commands.Choice(name="Oriვე (Video da Live)", value="both")
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_youtube(self, interaction: discord.Interaction, youtube_channel_id: str, discord_channel: discord.TextChannel, notify_type: str):
        data = load_yt_data()
        guild_id = str(interaction.guild.id)
        if guild_id not in data:
            data[guild_id] = {}
        
        data[guild_id][youtube_channel_id] = {
            "discord_channel_id": discord_channel.id,
            "notify_type": notify_type,
            "last_video_id": None,
            "is_live": False
        }
        save_yt_data(data)
        await interaction.response.send_message(f"arkhi `{youtube_channel_id}` damatebulia. shetyobinebebi gaigzavneba #{discord_channel.name}-shi.", ephemeral=True)

    @youtube_group.command(name="remove", description="Shlis YouTube arkhs dakvirvebis siidan")
    @app_commands.describe(youtube_channel_id="arkhis ID romlis washla ginda")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_youtube(self, interaction: discord.Interaction, youtube_channel_id: str):
        data = load_yt_data()
        guild_id = str(interaction.guild.id)
        if guild_id in data and youtube_channel_id in data[guild_id]:
            del data[guild_id][youtube_channel_id]
            save_yt_data(data)
            await interaction.response.send_message(f"arkhi `{youtube_channel_id}` warmatebit waishala.", ephemeral=True)
        else:
            await interaction.response.send_message("es arkhi ar aris damatebuli.", ephemeral=True)

    # --- ფონური პროცესი, რომელიც ამოწმებს YouTube-ს ---
    @tasks.loop(minutes=2)
    async def check_youtube(self):
        await self.bot.wait_until_ready()
        yt_api_key = os.environ.get('YOUTUBE_API_KEY')
        if not yt_api_key:
            print("YOUTUBE_API_KEY ar moidzebna Railway-shi. Shetyobinebebi gaishveba.")
            return

        data = load_yt_data()
        for guild_id, channels in data.items():
            for yt_id, config in channels.items():
                discord_channel_id = config.get("discord_channel_id")
                notify_type = config.get("notify_type", "both")
                channel = self.bot.get_channel(discord_channel_id)
                if not channel:
                    continue

                # 1. ვამოწმებთ ახალ ვიდეოებს
                if notify_type in ["video", "both"]:
                    try:
                        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={yt_id}&maxResults=1&order=date&type=video&key={yt_api_key}"
                        response = requests.get(url).json()
                        latest_video = response['items'][0]
                        video_id = latest_video['id']['videoId']
                        last_saved_id = config.get("last_video_id")
                        
                        if last_saved_id is None: # pirveli shemowmeba
                             data[guild_id][yt_id]['last_video_id'] = video_id
                             save_yt_data(data)
                             continue
                        
                        if last_saved_id != video_id:
                            # Vamowmebt laivi xom ar aris
                            video_details_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={yt_api_key}"
                            video_details = requests.get(video_details_url).json()['items'][0]
                            if video_details['snippet'].get('liveBroadcastContent') == 'none': # es nishnavs rom videoa da ara laivi
                                data[guild_id][yt_id]['last_video_id'] = video_id
                                save_yt_data(data)
                                await channel.send(f"📢 **axali video!** {latest_video['snippet']['channelTitle']}-ma dado axali video:\nhttps://www.youtube.com/watch?v={video_id}")
                    except Exception as e:
                        print(f"YouTube (video) check error for {yt_id}: {e}")

                # 2. ვამოწმებთ ლაივ სტრიმებს
                if notify_type in ["live", "both"]:
                    try:
                        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={yt_id}&eventType=live&type=video&key={yt_api_key}"
                        response = requests.get(url).json()
                        was_live = config.get("is_live", False)

                        if response.get('items'): # Tu laivi aris
                            if not was_live:
                                live_video = response['items'][0]
                                video_id = live_video['id']['videoId']
                                data[guild_id][yt_id]['is_live'] = True
                                save_yt_data(data)
                                await channel.send(f"🔴 **LAIVIA!** {live_video['snippet']['channelTitle']} laivshi shemovida!\nhttps://www.youtube.com/watch?v={video_id}")
                        else: # Tu laivi ar aris
                            if was_live:
                                data[guild_id][yt_id]['is_live'] = False
                                save_yt_data(data)
                    except Exception as e:
                        print(f"YouTube (live) check error for {yt_id}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeCog(bot))
