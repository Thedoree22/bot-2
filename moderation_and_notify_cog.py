import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import requests
import datetime
import dateutil.parser

# --- მონაცემთა ბაზის ფაილები ---
NOTIFY_DB = "notifications.json"

# --- მონაცემთა ბაზის ფუნქციები ---
def load_notify_data():
    if not os.path.exists(NOTIFY_DB): return {}
    try:
        with open(NOTIFY_DB, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_notify_data(data):
    with open(NOTIFY_DB, "w") as f: json.dump(data, f, indent=4)

# --- მთავარი კლასი (Cog) ---
class ModerationAndNotifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notify_data = load_notify_data()
        self.twitch_access_token = None
        self.check_streams.start()

    def cog_unload(self):
        self.check_streams.cancel()

    # --- შეტყობინებების წაშლის ბრძანება ---
    @app_commands.command(name="clear", description="Shლის shetyobinebebs arkhshi")
    @app_commands.describe(amount="raodenoba (max: 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount > 100:
            await interaction.response.send_message("100-ze meti shetyobinebis washlis ufleba ar maqvs!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Warmatebit waishala {len(deleted)} shetyobineba.")

    # --- შეტყობინებების სისტემის ბრძანებები ---
    notify_group = app_commands.Group(name="notifications", description="YouTube da Twitch shetyobinebebi")

    @notify_group.command(name="setup", description="Ayenebs arkhs, sadac daideba shetyobinebebi")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def notify_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        if guild_id not in self.notify_data:
            self.notify_data[guild_id] = {}
        self.notify_data[guild_id]['channel_id'] = channel.id
        save_notify_data(self.notify_data)
        await interaction.response.send_message(f"Shetyobinebebis arkhi dayenebulia {channel.mention}-ze.", ephemeral=True)

    @notify_group.command(name="add-youtube", description="Amatebs YouTube arkhs dasakvirveblad")
    @app_commands.describe(youtube_channel_id="YouTube arkhis ID (ara saxeli!)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_youtube(self, interaction: discord.Interaction, youtube_channel_id: str):
        guild_id = str(interaction.guild.id)
        if guild_id not in self.notify_data or 'channel_id' not in self.notify_data[guild_id]:
            await interaction.response.send_message("Jer /notifications setup brdzanebit daayenet arkhi!", ephemeral=True)
            return
        
        if 'youtube_channels' not in self.notify_data[guild_id]:
            self.notify_data[guild_id]['youtube_channels'] = {}
        
        self.notify_data[guild_id]['youtube_channels'][youtube_channel_id] = {'last_video_id': None}
        save_notify_data(self.notify_data)
        await interaction.response.send_message(f"YouTube arkhi `{youtube_channel_id}` damatebulia.", ephemeral=True)

    @notify_group.command(name="add-twitch", description="Amatebs Twitch arkhs dasakvirveblad")
    @app_commands.describe(username="Twitch arkhis saxeli")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_twitch(self, interaction: discord.Interaction, username: str):
        guild_id = str(interaction.guild.id)
        if guild_id not in self.notify_data or 'channel_id' not in self.notify_data[guild_id]:
            await interaction.response.send_message("Jer /notifications setup brdzanebit daayenet arkhi!", ephemeral=True)
            return

        if 'twitch_channels' not in self.notify_data[guild_id]:
            self.notify_data[guild_id]['twitch_channels'] = {}
            
        self.notify_data[guild_id]['twitch_channels'][username.lower()] = {'live': False}
        save_notify_data(self.notify_data)
        await interaction.response.send_message(f"Twitch arkhi `{username}` damatebulia.", ephemeral=True)

    # --- ფონური პროცესი, რომელიც ამოწმებს სტრიმებს/ვიდეოებს ---
    @tasks.loop(minutes=2)
    async def check_streams(self):
        await self.bot.wait_until_ready()
        
        # Twitch API-სთვის ტოკენის აღება
        try:
            client_id = os.environ['TWITCH_CLIENT_ID']
            client_secret = os.environ['TWITCH_CLIENT_SECRET']
            r = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials")
            self.twitch_access_token = r.json()['access_token']
        except Exception as e:
            print(f"Twitch token error: {e}")
            return # თუ Twitch API გასაღები არასწორია, ვჩერდებით

        # YouTube API გასაღები
        yt_api_key = os.environ.get('YOUTUBE_API_KEY')

        for guild_id, data in self.notify_data.items():
            channel_id = data.get('channel_id')
            if not channel_id: continue
            
            channel = self.bot.get_channel(channel_id)
            if not channel: continue

            # YouTube-ს შემოწმება
            if yt_api_key and 'youtube_channels' in data:
                for yt_id, yt_data in data['youtube_channels'].items():
                    try:
                        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={yt_id}&maxResults=1&order=date&type=video&key={yt_api_key}"
                        response = requests.get(url).json()
                        latest_video = response['items'][0]
                        video_id = latest_video['id']['videoId']
                        
                        if yt_data['last_video_id'] is None: # პირველი შემოწმება
                             self.notify_data[guild_id]['youtube_channels'][yt_id]['last_video_id'] = video_id
                             save_notify_data(self.notify_data)
                             continue
                        
                        if yt_data['last_video_id'] != video_id:
                            self.notify_data[guild_id]['youtube_channels'][yt_id]['last_video_id'] = video_id
                            save_notify_data(self.notify_data)
                            await channel.send(f"📢 **axali video!** {latest_video['snippet']['channelTitle']}-ma dado axali video:\nhttps://www.youtube.com/watch?v={video_id}")
                    except Exception as e:
                        print(f"YouTube check error for {yt_id}: {e}")

            # Twitch-ის შემოწმება
            if 'twitch_channels' in data:
                usernames = list(data['twitch_channels'].keys())
                try:
                    headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.twitch_access_token}"}
                    params = [("user_login", name) for name in usernames]
                    response = requests.get("https://api.twitch.tv/helix/streams", headers=headers, params=params).json()
                    
                    live_streams = {stream['user_login']: stream for stream in response.get('data', [])}

                    for username, twitch_data in data['twitch_channels'].items():
                        is_live = username in live_streams
                        was_live = twitch_data.get('live', False)

                        if is_live and not was_live:
                            stream_data = live_streams[username]
                            self.notify_data[guild_id]['twitch_channels'][username]['live'] = True
                            save_notify_data(self.notify_data)
                            
                            embed = discord.Embed(
                                title=f"🔴 **LIVE!** {stream_data['user_name']} online-shia!",
                                url=f"https://twitch.tv/{username}",
                                description=stream_data.get('title', 'striimi daiwyo!'),
                                color=0x6441a5
                            )
                            embed.set_thumbnail(url=stream_data['thumbnail_url'].replace('{width}', '320').replace('{height}', '180'))
                            await channel.send(embed=embed)
                        elif not is_live and was_live:
                            self.notify_data[guild_id]['twitch_channels'][username]['live'] = False
                            save_notify_data(self.notify_data)
                except Exception as e:
                    print(f"Twitch check error for {usernames}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationAndNotifyCog(bot))
