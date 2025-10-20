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
AUTOMESSAGE_DB = "automessage_data.json"
SMS_LOG_DB = "sms_logs.json" # ახალი ფაილი SMS ლოგებისთვის

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

# ...(Giveaway ფუნქციები უცვლელი)...
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
        self.send_auto_message.start()
        # ვტვირთავთ SMS ლოგებს ბოტის ჩართვისას
        self.sms_logs = load_data(SMS_LOG_DB)

    def cog_unload(self):
        if hasattr(self, 'check_giveaways') and self.check_giveaways.is_running(): self.check_giveaways.cancel()
        if self.send_auto_message.is_running(): self.send_auto_message.cancel()

    # --- დამხმარე ფუნქცია SMS ლოგირებისთვის ---
    def log_sms(self, user_id: int, direction: str, content: str, admin_id: Optional[int] = None):
        """Logs an SMS message."""
        user_id_str = str(user_id)
        if user_id_str not in self.sms_logs:
            self.sms_logs[user_id_str] = []
        
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "direction": direction, # "outgoing" or "incoming"
            "content": content
        }
        if admin_id:
            log_entry["admin_id"] = admin_id
            
        self.sms_logs[user_id_str].append(log_entry)
        # შევინახოთ ლოგები (შეიძლება დიდი ფაილი გახდეს დროთა განმავლობაში)
        save_data(self.sms_logs, SMS_LOG_DB)

    # --- სხვა ბრძანებები (Clear, Giveaway, Userinfo, Join, Leave, daketva, gageba, auto-msg) უცვლელი ---
    # ...(აქ ჩასვი ყველა ის ბრძანება წინა კოდიდან, რომელიც გჭირდება)...
    @app_commands.command(name="clear", description="შლის ჩატის შეტყობინებებს")
    @app_commands.describe(amount="რაოდენობა (მაქს 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount <= 0 : await interaction.response.send_message("რაოდენობა 0-ზე მეტი უნდა იყოს.", ephemeral=True); return
        if amount > 100: await interaction.response.send_message("100ზე მეტის წაშლა არ შემიძლია", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); deleted_messages = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"წარმატებით წაიშალა {len(deleted_messages)} შეტყობინება")

    @app_commands.command(name="giveaway", description="ქმნის ახალ გათამაშებას")
    @app_commands.describe(duration="რამდენი ხანი (მაგ 10m 1h 30m 2d)", prize="რა თამაშდება", winners="გამარჯვებულის რაოდენობა (default 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration);
        if delta.total_seconds() <= 0: await interaction.response.send_message("არასწორი დროის ფორმატია", ephemeral=True); return
        end_time = datetime.datetime.utcnow() + delta; end_timestamp = int(end_time.timestamp())
        embed = discord.Embed(title="🎁 ახალი გათამაშება 🎁", description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს მონაწილეობისთვის!", color=discord.Color.gold())
        embed.add_field(name="მთავრდება:", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)"); embed.add_field(name="გამარჯვებული:", value=f"{winners} კაცი")
        embed.set_footer(text=f"ორგანიზატორი: {interaction.user.name}"); await interaction.response.send_message("გათამაშება იწყება...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed); view = GiveawayView(msg.id); await msg.edit(view=view)
        giveaways = load_data(GIVEAWAY_DB); giveaways[str(msg.id)] = {"channel_id": interaction.channel.id, "end_time": end_time.isoformat(), "prize": prize, "winners": winners, "participants": [], "host_id": interaction.user.id, "ended": False}
        save_data(giveaways, GIVEAWAY_DB)

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

    @app_commands.command(name="join", description="ბოტი შემოდის შენს ხმოვან არხში")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
            if interaction.guild.voice_client: await interaction.guild.voice_client.move_to(channel); await interaction.response.send_message(f"გადმოვედი `{channel.name}`-ში.")
            else:
                try: await channel.connect(); await interaction.response.send_message(f"შემოვედი `{channel.name}`-ში.")
                except Exception as e: await interaction.response.send_message(f"ვერ შემოვედი არხში: {e}", ephemeral=True)
        else: await interaction.response.send_message("ჯერ ხმოვან არხში უნდა იყო!", ephemeral=True)

    @app_commands.command(name="leave", description="ბოტი გადის ხმოვანი არხიდან")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("გავედი ხმოვანი არხიდან.")
        else: await interaction.response.send_message("მე ისედაც არ ვარ ხმოვან არხში.", ephemeral=True)

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

    # --- Auto-Message ფუნქციონალი ---
    @app_commands.command(name="set-18plus-chat", description="აყენებს არხს 18+ შეხსენებისთვის")
    @app_commands.describe(channel="აირჩიე არხი")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def automessage_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(AUTOMESSAGE_DB); guild_id = str(interaction.guild.id)
        data[guild_id] = {"channel_id": channel.id}; save_data(data, AUTOMESSAGE_DB)
        await interaction.response.send_message(f"18+ შეხსენების არხი არის {channel.mention}", ephemeral=True)

    async def _send_the_message(self, channel: discord.TextChannel):
        message_text = ("⚠️ @everyone\nწესი 1- არ ვსაუბრობთ ამ ჩათზე\nწესი 2- აუცილებლად ვიცავთ 1 წესს\nწესი 3- აქ რაც იწერება სერვერის პასუხისმგებლობაში არ არის :დ\n⚠️")
        try: await channel.send(message_text, allowed_mentions=discord.AllowedMentions(everyone=True)); return True
        except discord.Forbidden: print(f"ERROR: არ მაქვს უფლება გავაგზავნო #{channel.name} ({channel.guild.name})"); return False
        except Exception as e: print(f"ERROR: ავტო შეტყობინების გაგზავნისას: {e}"); return False

    @app_commands.command(name="gaxseneba", description="აგზავნის 18+ შეხსენებას მითითებულ არხში")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def automessage_sendnow(self, interaction: discord.Interaction):
        data = load_data(AUTOMESSAGE_DB); guild_id = str(interaction.guild.id)
        if guild_id in data and 'channel_id' in data[guild_id]:
            channel_id = data[guild_id]['channel_id']; channel = self.bot.get_channel(channel_id)
            if channel:
                await interaction.response.defer(ephemeral=True); success = await self._send_the_message(channel)
                if success: await interaction.followup.send("შეტყობინება გაიგზავნა.", ephemeral=True)
                else: await interaction.followup.send("ვერ გავაგზავნე შეტყობინება შეამოწმე უფლებები.", ephemeral=True)
            else: await interaction.response.send_message("ვერ ვიპოვე არხი. დააყენე თავიდან /set-18plus-chat.", ephemeral=True)
        else: await interaction.response.send_message("ჯერ დააყენე არხი /set-18plus-chat ბრძანებით.", ephemeral=True)

    @tasks.loop(hours=5)
    async def send_auto_message(self):
        await self.bot.wait_until_ready(); data = load_data(AUTOMESSAGE_DB)
        for guild_id, config in data.items():
            if 'channel_id' in config:
                channel = self.bot.get_channel(config['channel_id'])
                if channel: await self._send_the_message(channel)
                else: print(f"WARNING: ვერ მოიძებნა auto-msg არხი ID={config['channel_id']}")

    # --- /sms ბრძანება (ანონიმური + ლოგირება) ---
    @app_commands.command(name="sms", description="უგზავნის ანონიმურ პირად შეტყობინებას მომხმარებელს")
    @app_commands.describe(user="მომხმარებელი ვისაც უგზავნი", text="შეტყობინების ტექსტი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_sms(self, interaction: discord.Interaction, user: discord.Member, text: str):
        if user.bot:
            await interaction.response.send_message("ბოტს პირად შეტყობინებას ვერ გაუგზავნი.", ephemeral=True); return
        try:
            # ვაგზავნით შეტყობინებას გამგზავნის მითითების გარეშე
            message_to_send = f"**შეტყობინება {interaction.guild.name}-დან:**\n\n{text}"
            await user.send(message_to_send)
            
            # ვლოგავთ გაგზავნილ შეტყობინებას
            self.log_sms(user_id=user.id, direction="outgoing", content=text, admin_id=interaction.user.id)
            
            await interaction.response.send_message(f"ანონიმური შეტყობინება წარმატებით გაეგზავნა {user.mention}-ს.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"ვერ გავუგზავნე შეტყობინება {user.mention}-ს. შესაძლოა დაბლოკილი მაქვს ან PM გამორთული აქვს.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"მოხდა შეცდომა შეტყობინების გაგზავნისას: {e}", ephemeral=True)

    # --- ახალი /smslog ბრძანება ---
    @app_commands.command(name="smslog", description="აჩვენებს მითითებულ მომხმარებელთან მიმოწერის ისტორიას")
    @app_commands.describe(user="მომხმარებელი ვისი ლოგებიც გინდა ნახო")
    @app_commands.checks.has_permissions(manage_messages=True) # იგივე უფლება, რაც /sms-ს
    async def view_sms_log(self, interaction: discord.Interaction, user: discord.Member):
        user_id_str = str(user.id)
        
        if user_id_str not in self.sms_logs or not self.sms_logs[user_id_str]:
            await interaction.response.send_message(f"{user.mention}-თან მიმოწერის ისტორია ცარიელია.", ephemeral=True)
            return

        logs = self.sms_logs[user_id_str]
        
        embed = discord.Embed(
            title=f"SMS ლოგი - {user.name}",
            color=discord.Color.blurple()
        )
        
        log_text = ""
        # ვაჩვენოთ ბოლო 10 შეტყობინება (ან ნაკლები)
        for entry in logs[-10:]:
            timestamp = datetime.datetime.fromisoformat(entry['timestamp'])
            time_formatted = discord.utils.format_dt(timestamp, style='f') # დროის ფორმატირება
            direction = "➡️ (Admin)" if entry['direction'] == "outgoing" else "⬅️ (User)"
            
            # ვამოკლებთ გრძელ შეტყობინებებს
            content = entry['content']
            if len(content) > 150:
                content = content[:147] + "..."
                
            log_text += f"`{time_formatted}`\n{direction}: {content}\n\n"

        if not log_text:
            log_text = "ლოგები ვერ მოიძებნა."

        embed.description = log_text
        embed.set_footer(text=f"ნაჩვენებია ბოლო {len(logs[-10:])} შეტყობინება")

        await interaction.response.send_message(embed=embed, ephemeral=True) # ლოგებს ვხედავთ მხოლოდ ჩვენ

    # --- ივენთი შემომავალი DM შეტყობინებების დასალოგად ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ვამოწმებთ, არის თუ არა DM და არა ბოტისგან
        if message.guild is None and not message.author.bot:
            user_id_str = str(message.author.id)
            # ვლოგავთ მხოლოდ იმ მომხმარებლების პასუხებს, ვისაც ჩვენ მივწერეთ (/sms)
            if user_id_str in self.sms_logs:
                self.log_sms(user_id=message.author.id, direction="incoming", content=message.content)
        
        # ვუშვებთ ბრძანებების დამუშავებას (თუ პრეფიქსი გაქვს)
        # await self.bot.process_commands(message) # ეს აღარ არის საჭირო discord.py 2.0+ ვერსიებში, თუ ჰიბრიდულ ბოტს არ იყენებ

# --- Cog-ის ჩატვირთვის ფუნქცია ---
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
