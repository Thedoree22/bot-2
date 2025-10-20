import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
import re
from typing import Optional

# --- მონაცემთა ბაზის ფაილები ---
GIVEAWAY_DB = "giveaways.json"
AUTOMESSAGE_DB = "automessage_data.json" # ფაილი ავტო-შეტყობინებისთვის

# --- მონაცემთა ბაზის ფუნქციები ---
def load_data(file_path):
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_data(data, file_path):
    try:
        with open(file_path, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"ფაილში შენახვის შეცდომა ({file_path}): {e}")

# ...(Giveaway ფუნქციები: parse_duration, GiveawayView უცვლელი)...
def parse_duration(duration_str: str) -> datetime.timedelta:
    regex = re.compile(r'(\d+)([smhd])'); parts = regex.findall(duration_str.lower()); delta = datetime.timedelta()
    for amount, unit in parts:
        amount = int(amount);
        if unit == 's': delta += datetime.timedelta(seconds=amount)
        elif unit == 'm': delta += datetime.timedelta(minutes=amount)
        elif unit == 'h': delta += datetime.timedelta(hours=amount)
        elif unit == 'd': delta += datetime.timedelta(days=amount)
    return delta
class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_message_id): super().__init__(timeout=None); self.giveaway_message_id = giveaway_message_id
    @discord.ui.button(label="მონაწილეობა", style=discord.ButtonStyle.success, custom_id="join_giveaway_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_data(GIVEAWAY_DB); giveaway = giveaways.get(str(self.giveaway_message_id))
        if not giveaway: await interaction.response.send_message("ეს გათამაშება აღარ არსებობს", ephemeral=True); return
        user_id = str(interaction.user.id)
        if user_id not in giveaway['participants']: giveaway['participants'].append(user_id); save_data(giveaways, GIVEAWAY_DB); await interaction.response.send_message("წარმატებით ჩაერთე", ephemeral=True)
        else: await interaction.response.send_message("შენ უკვე მონაწილეობ", ephemeral=True)

# --- აქ იწყება მთავარი კლასი ---
class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if hasattr(self, 'start_giveaway'): self.check_giveaways.start()
        self.send_auto_message.start() # ვიწყებთ ავტო-შეტყობინების ციკლს

    def cog_unload(self):
        if hasattr(self, 'check_giveaways') and self.check_giveaways.is_running(): self.check_giveaways.cancel()
        if self.send_auto_message.is_running(): self.send_auto_message.cancel()

    # --- სხვა ბრძანებები (Clear, Giveaway, Userinfo, Join, Leave, daketva, gageba) უცვლელი რჩება ---
    # ... (აქ ჩასვი ყველა ის ბრძანება წინა კოდიდან, რომელიც გჭირდება) ...
    # მაგალითად Clear:
    @app_commands.command(name="clear", description="შლის ჩატის შეტყობინებებს")
    @app_commands.describe(amount="რაოდენობა (მაქს 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount <= 0 : await interaction.response.send_message("რაოდენობა 0-ზე მეტი უნდა იყოს.", ephemeral=True); return
        if amount > 100: await interaction.response.send_message("100ზე მეტის წაშლა არ შემიძლია", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); deleted_messages = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"წარმატებით წაიშალა {len(deleted_messages)} შეტყობინება")

    # --- Giveaway ბრძანება ---
    @app_commands.command(name="giveaway", description="ქმნის ახალ გათამაშებას")
    @app_commands.describe(duration="რამდენი ხანი (მაგ 10m 1h 30m 2d)", prize="რა თამაშდება", winners="გამარჯვებულის რაოდენობა (default 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration)
        if delta.total_seconds() <= 0: await interaction.response.send_message("არასწორი დროის ფორმატია", ephemeral=True); return
        end_time = datetime.datetime.utcnow() + delta; end_timestamp = int(end_time.timestamp())
        embed = discord.Embed(title="🎁 ახალი გათამაშება 🎁", description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს მონაწილეობისთვის!", color=discord.Color.gold())
        embed.add_field(name="მთავრდება:", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)"); embed.add_field(name="გამარჯვებული:", value=f"{winners} კაცი")
        embed.set_footer(text=f"ორგანიზატორი: {interaction.user.name}"); await interaction.response.send_message("გათამაშება იწყება...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed); view = GiveawayView(msg.id); await msg.edit(view=view)
        giveaways = load_data(GIVEAWAY_DB); giveaways[str(msg.id)] = {"channel_id": interaction.channel.id, "end_time": end_time.isoformat(), "prize": prize, "winners": winners, "participants": [], "host_id": interaction.user.id, "ended": False}
        save_data(giveaways, GIVEAWAY_DB)

    # --- Giveaway-ს შემმოწმებელი ---
    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        await self.bot.wait_until_ready(); giveaways = load_data(GIVEAWAY_DB); current_time = datetime.datetime.utcnow()
        for msg_id, data in list(giveaways.items()):
            if data.get('ended', False): continue
            end_time = datetime.datetime.fromisoformat(data['end_time'])
            if current_time >= end_time:
                channel = self.bot.get_channel(data['channel_id']);
                if not channel: continue
                try: msg = await channel.fetch_message(int(msg_id))
                except discord.NotFound: data['ended'] = True; save_data(giveaways, GIVEAWAY_DB); continue
                participants = data['participants']; prize = data.get('prize', 'უცნობი პრიზი')
                if not participants: winner_text = "არავინ მიიღო მონაწილეობა"; winners_list = []
                else: winner_ids = random.sample(participants, k=min(data['winners'], len(participants))); winners_list = [f"<@{uid}>" for uid in winner_ids]; winner_text = ", ".join(winners_list)
                winner_embed = discord.Embed(title="🎉 გათამაშება დასრულდა 🎉", description=f"**პრიზი:** {prize}\n\nგილოცავთ {winner_text}!", color=discord.Color.green())
                await channel.send(content=winner_text, embed=winner_embed); original_embed = msg.embeds[0]
                original_embed.title = "🎁 გათამაშება დასრულდა 🎁"; original_embed.description = f"**პრიზი:** {prize}"; original_embed.color = discord.Color.dark_grey()
                original_embed.set_field_at(0, name="დასრულდა:", value=f"<t:{int(end_time.timestamp())}:R>"); original_embed.add_field(name="გამარჯვებული:", value=winner_text if winners_list else "არავინ")
                view = discord.ui.View(); view.add_item(discord.ui.Button(label="მონაწილეობა", style=discord.ButtonStyle.success, disabled=True))
                await msg.edit(embed=original_embed, view=view); data['ended'] = True; save_data(giveaways, GIVEAWAY_DB)

    # --- Userinfo ბრძანება ---
    @app_commands.command(name="userinfo", description="აჩვენებს ინფორმაციას მომხმარებელზე")
    @app_commands.describe(user="აირჩიე მომხმარებელი (თუ არ აირჩევ შენსას აჩვენებს)")
    async def userinfo(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target_user = user or interaction.user
        embed = discord.Embed(title=f"{target_user.name}#{target_user.discriminator}" if target_user.discriminator != '0' else target_user.name, color=target_user.color)
        if target_user.avatar: embed.set_thumbnail(url=target_user.avatar.url)
        embed.add_field(name="ID", value=target_user.id, inline=False)
        embed.add_field(name="შემოუერთდა სერვერს", value=f"<t:{int(target_user.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="ანგარიში შეიქმნა", value=f"<t:{int(target_user.created_at.timestamp())}:R>", inline=True)
        roles = [role.mention for role in target_user.roles if role.name != "@everyone"]
        if roles: embed.add_field(name=f"როლები [{len(roles)}]", value=", ".join(roles) if len(roles) < 10 else f"{len(roles)} როლი", inline=False)
        else: embed.add_field(name="როლები", value="არ აქვს", inline=False)
        if target_user.top_role.name != "@everyone": embed.add_field(name="უმაღლესი როლი", value=target_user.top_role.mention, inline=True)
        embed.add_field(name="ბოტი?", value="კი" if target_user.bot else "არა", inline=True)
        await interaction.response.send_message(embed=embed)

    # --- Join ბრძანება ---
    @app_commands.command(name="join", description="ბოტი შემოდის შენს ხმოვან არხში")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
            if interaction.guild.voice_client: await interaction.guild.voice_client.move_to(channel); await interaction.response.send_message(f"გადმოვედი `{channel.name}`-ში.")
            else:
                try: await channel.connect(); await interaction.response.send_message(f"შემოვედი `{channel.name}`-ში.")
                except Exception as e: await interaction.response.send_message(f"ვერ შემოვედი არხში: {e}", ephemeral=True)
        else: await interaction.response.send_message("ჯერ ხმოვან არხში უნდა იყო!", ephemeral=True)

    # --- Leave ბრძანება ---
    @app_commands.command(name="leave", description="ბოტი გადის ხმოვანი არხიდან")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("გავედი ხმოვანი არხიდან.")
        else: await interaction.response.send_message("მე ისედაც არ ვარ ხმოვან არხში.", ephemeral=True)

    # --- daketva / gageba ბრძანებები ---
    @app_commands.command(name="daketva")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role
        overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = False
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი დაიკეტა.")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    @app_commands.command(name="gageba")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role
        overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = None # ან True
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი გაიღო.")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    # --- ახალი Auto-Message ფუნქციონალი (ახალი ბრძანებებით) ---

    # არხის დაყენების ბრძანება
    @app_commands.command(name="set-18plus-chat", description="აყენებს არხს 18+ შეხსენებისთვის")
    @app_commands.describe(channel="აირჩიე არხი")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def automessage_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(AUTOMESSAGE_DB)
        guild_id = str(interaction.guild.id)
        data[guild_id] = {"channel_id": channel.id}
        save_data(data, AUTOMESSAGE_DB)
        await interaction.response.send_message(f"18+ შეხსენების არხი არის {channel.mention}", ephemeral=True)

    # ფუნქცია, რომელიც აგზავნის შეტყობინებას
    async def _send_the_message(self, channel: discord.TextChannel):
        message_text = (
            "⚠️ @everyone\n"
            "წესი 1- არ ვსაუბრობთ ამ ჩათზე\n"
            "წესი 2- აუცილებლად ვიცავთ 1 წესს\n"
            "წესი 3- აქ რაც იწერება სერვერის პასუხისმგებლობაში არ არის :დ\n"
            "⚠️"
        )
        try:
            await channel.send(message_text, allowed_mentions=discord.AllowedMentions(everyone=True))
            return True
        except discord.Forbidden: print(f"ERROR: არ მაქვს უფლება გავაგზავნო #{channel.name} ({channel.guild.name})"); return False
        except Exception as e: print(f"ERROR: ავტო შეტყობინების გაგზავნისას: {e}"); return False

    # ხელით გაგზავნის ბრძანება
    @app_commands.command(name="gaxseneba", description="აგზავნის 18+ შეხსენებას მითითებულ არხში")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def automessage_sendnow(self, interaction: discord.Interaction):
        data = load_data(AUTOMESSAGE_DB)
        guild_id = str(interaction.guild.id)
        if guild_id in data and 'channel_id' in data[guild_id]:
            channel_id = data[guild_id]['channel_id']
            channel = self.bot.get_channel(channel_id)
            if channel:
                await interaction.response.defer(ephemeral=True)
                success = await self._send_the_message(channel)
                if success: await interaction.followup.send("შეტყობინება გაიგზავნა.", ephemeral=True)
                else: await interaction.followup.send("ვერ გავაგზავნე შეტყობინება შეამოწმე უფლებები.", ephemeral=True)
            else: await interaction.response.send_message("ვერ ვიპოვე არხი. დააყენე თავიდან /set-18plus-chat.", ephemeral=True)
        else: await interaction.response.send_message("ჯერ დააყენე არხი /set-18plus-chat ბრძანებით.", ephemeral=True)

    # ფონური პროცესი ავტომატური შეტყობინებისთვის
    @tasks.loop(minutes=15)
    async def send_auto_message(self):
        await self.bot.wait_until_ready()
        data = load_data(AUTOMESSAGE_DB)
        for guild_id, config in data.items():
            if 'channel_id' in config:
                channel = self.bot.get_channel(config['channel_id'])
                if channel: await self._send_the_message(channel)
                else: print(f"WARNING: ვერ მოიძებნა auto-msg არხი ID={config['channel_id']}")

# --- Cog-ის ჩატვირთვის ფუნქცია ---
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
