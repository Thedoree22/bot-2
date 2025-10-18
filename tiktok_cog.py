import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Optional
import json
import os
import requests
from bs4 import BeautifulSoup
import datetime
import re

TIKTOK_DB = "tiktok_data.json"

def load_tiktok_data():
    if not os.path.exists(TIKTOK_DB): return {}
    try:
        with open(TIKTOK_DB, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_tiktok_data(data):
    with open(TIKTOK_DB, "w") as f: json.dump(data, f, indent=4)

class TikTokCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tiktok_data = load_tiktok_data()
        self.check_tiktok.start()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    def cog_unload(self):
        self.check_tiktok.cancel()

    tiktok_group = app_commands.Group(name="tiktok", description="TikTok shetyobinebebis martva")

    # --- /tiktok add ---
    @tiktok_group.command(name="add", description="Amatebs TikTok akkaunts dasakvirveblad")
    @app_commands.describe(username="TikTok akkauntis saxeli (@-is gareshe)", discord_channel="Arkhi sadac daideba shetyobineba")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_tiktok(self, interaction: discord.Interaction, username: str, discord_channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        if guild_id not in self.tiktok_data: self.tiktok_data[guild_id] = {"channels": {}}
        try:
             test_url = f"https://www.tiktok.com/@{username}"; response = requests.get(test_url, headers=self.headers, timeout=10)
             if response.status_code != 200: await interaction.response.send_message(f"Ver vipove akkaunti '{username}'.", ephemeral=True); return
        except requests.exceptions.RequestException as e:
            print(f"Error checking TikTok user {username}: {e}"); await interaction.response.send_message("Ver davukavshirdi TikTok-s.", ephemeral=True); return
        self.tiktok_data[guild_id]["channels"][username.lower()] = {"discord_channel_id": discord_channel.id, "last_post_id": None, "is_live": False, "mention": None}
        save_tiktok_data(self.tiktok_data)
        await interaction.response.send_message(f"TikTok `{username}` damatebulia #{discord_channel.name}-shi.", ephemeral=True)

    # --- /tiktok remove ---
    @tiktok_group.command(name="remove", description="Shlis TikTok akkaunts dakvirvebis siidan")
    @app_commands.describe(username="Akkauntis saxeli romlis washla ginda")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_tiktok(self, interaction: discord.Interaction, username: str):
        guild_id = str(interaction.guild.id); username_lower = username.lower()
        if guild_id in self.tiktok_data and username_lower in self.tiktok_data[guild_id]["channels"]:
            del self.tiktok_data[guild_id]["channels"][username_lower]; save_tiktok_data(self.tiktok_data)
            await interaction.response.send_message(f"Akkaunti `{username}` waishala.", ephemeral=True)
        else: await interaction.response.send_message("Es akkaunti ar aris damatebuli.", ephemeral=True)

    # --- /tiktok setmention ---
    @tiktok_group.command(name="setmention", description="Ayenebs vin moinishnos laivis dawyebisas")
    @app_commands.describe(username="TikTok akkauntis saxeli", mention_everyone="Moinishnos Tu Ara @everyone?", role="Airchiet roli (Tu @everyone ar ginda)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_mention_tiktok(self, interaction: discord.Interaction, username: str, mention_everyone: bool = False, role: Optional[discord.Role] = None):
        guild_id = str(interaction.guild.id); username_lower = username.lower()
        if guild_id not in self.tiktok_data or username_lower not in self.tiktok_data[guild_id]["channels"]:
            await interaction.response.send_message(f"Akkaunti `{username}` ar aris damatebuli.", ephemeral=True); return
        mention_target = None; message = ""
        if mention_everyone: mention_target = "everyone"; message = f"`{username}`-is laivze `@everyone` moinishneba."
        elif role: mention_target = str(role.id); message = f"`{username}`-is laivze {role.mention} moinishneba."
        else: mention_target = None; message = f"`{username}`-is laivze aravin moinishneba."
        self.tiktok_data[guild_id]["channels"][username_lower]["mention"] = mention_target
        save_tiktok_data(self.tiktok_data)
        await interaction.response.send_message(message, ephemeral=True)

    # --- /tiktok forcelive (შესწორებული გაგზავნა) ---
    @tiktok_group.command(name="forcelive", description="Agzavnis laivis shetyobinebas xelaxla (tu akkaunti laivshia)")
    @app_commands.describe(username="TikTok akkauntis saxeli (@-is gareshe)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def force_live_tiktok(self, interaction: discord.Interaction, username: str):
        guild_id = str(interaction.guild.id); username_lower = username.lower()
        if guild_id not in self.tiktok_data or username_lower not in self.tiktok_data[guild_id]["channels"]:
            await interaction.response.send_message(f"TikTok akkaunti `{username}` ar aris damatebuli.", ephemeral=True); return
        config = self.tiktok_data[guild_id]["channels"][username_lower]
        discord_channel_id = config.get("discord_channel_id")
        discord_channel = self.bot.get_channel(discord_channel_id)
        if not discord_channel: await interaction.response.send_message("ver vipove Discord arkhi.", ephemeral=True); return

        await interaction.response.defer(ephemeral=True)
        try:
            url = f"https://www.tiktok.com/@{username_lower}"
            response = requests.get(url, headers=self.headers, timeout=15); response.raise_for_status()
            is_live_now = "live" in response.text.lower()
            if is_live_now:
                mention_setting = config.get("mention"); mention_content = None
                mention_everyone_bool = False; role_mention = False
                if mention_setting == "everyone": mention_content = "@everyone"; mention_everyone_bool = True
                elif mention_setting and mention_setting.isdigit():
                    role = interaction.guild.get_role(int(mention_setting))
                    if role: mention_content = role.mention; role_mention = True
                
                # --- შესწორება აქ ---
                embed = discord.Embed(title=f"🔴 **ლაივია!** `{username}` TikTok-ზე ისევ ლაივშია!", description=f"[გადადი ლაივზე]({url})", color=discord.Color.red())
                await discord_channel.send(content=mention_content, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=mention_everyone_bool, roles=role_mention))
                # --- შესწორება მთავრდება ---

                await interaction.followup.send(f"`{username}`-is laivis shetyobineba xelaxla gaigzavna #{discord_channel.name}-shi.")
            else: await interaction.followup.send(f"`{username}` amjamad laivshi ar aris.")
        except Exception as e:
            print(f"Error force checking TikTok live for {username}: {e}")
            await interaction.followup.send(f"shecdoma laivis statusis shemowmebisas `{username}`-stvis.")

    # --- ფონური პროცესი (შესწორებული გაგზავნა) ---
    @tasks.loop(minutes=3)
    async def check_tiktok(self):
        await self.bot.wait_until_ready()
        current_data = load_tiktok_data()
        for guild_id, guild_data in current_data.items():
            guild = self.bot.get_guild(int(guild_id));
            if not guild: continue
            for username, config in list(guild_data.get("channels", {}).items()):
                discord_channel_id = config.get("discord_channel_id")
                channel = self.bot.get_channel(discord_channel_id);
                if not channel: continue
                try:
                    url = f"https://www.tiktok.com/@{username}"; response = requests.get(url, headers=self.headers, timeout=15); response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    latest_post_element = soup.find('div', {'data-e2e': 'user-post-item'})
                    if latest_post_element:
                         post_link_tag = latest_post_element.find('a')
                         if post_link_tag and post_link_tag.get('href'):
                            post_url = post_link_tag['href']; match = re.search(r'/video/(\d+)', post_url)
                            if match:
                                latest_post_id = match.group(1); last_known_id = config.get("last_post_id")
                                if last_known_id is None: current_data[guild_id]["channels"][username]["last_post_id"] = latest_post_id
                                elif last_known_id != latest_post_id:
                                    current_data[guild_id]["channels"][username]["last_post_id"] = latest_post_id
                                    await channel.send(f"📢 **ახალი TikTok ვიდეო!** `{username}`-მა დადო ახალი პოსტი:\n{post_url}")
                                    save_tiktok_data(current_data)
                    is_live_now = "live" in response.text.lower(); was_live = config.get("is_live", False)
                    if is_live_now and not was_live:
                         current_data[guild_id]["channels"][username]["is_live"] = True; save_tiktok_data(current_data)
                         mention_setting = config.get("mention"); mention_content = None
                         mention_everyone_bool = False; role_mention = False
                         if mention_setting == "everyone": mention_content = "@everyone"; mention_everyone_bool = True
                         elif mention_setting and mention_setting.isdigit():
                             role = guild.get_role(int(mention_setting))
                             if role: mention_content = role.mention; role_mention = True
                         
                         # --- შესწორება აქ ---
                         embed = discord.Embed(title=f"🔴 **ლაივია!** `{username}` TikTok-ზე ლაივშია!", description=f"[გადადი ლაივზე]({url})", color=discord.Color.red())
                         await channel.send(content=mention_content, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=mention_everyone_bool, roles=role_mention))
                         # --- შესწორება მთავრდება ---

                    elif not is_live_now and was_live:
                         current_data[guild_id]["channels"][username]["is_live"] = False; save_tiktok_data(current_data)
                except requests.exceptions.HTTPError as e:
                     if e.response.status_code == 404:
                         print(f"TikTok user {username} not found (404). Removing.")
                         if guild_id in current_data and username in current_data.get(guild_id, {}).get("channels", {}):
                             del current_data[guild_id]["channels"][username]; save_tiktok_data(current_data)
                     else: print(f"HTTP Error checking TikTok {username}: {e.response.status_code}")
                except requests.exceptions.RequestException as e: print(f"Connection Error checking TikTok {username}: {e}")
                except Exception as e: print(f"General Error checking TikTok {username}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(TikTokCog(bot))
