import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
import re
from typing import Optional

# ...(მონაცემთა ბაზის ფაილები და ფუნქციები უცვლელი)...
GIVEAWAY_DB = "giveaways.json"
AUTOMESSAGE_DB = "automessage_data.json"
SMS_LOG_DB = "sms_logs.json"
def load_data(file_path): # ... (კოდი იგივეა) ...
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}
def save_data(data, file_path): # ... (კოდი იგივეა) ...
    try:
        with open(file_path, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"ფაილში შენახვის შეცდომა ({file_path}): {e}")
def parse_duration(duration_str: str) -> datetime.timedelta: # ... (კოდი იგივეა) ...
    regex = re.compile(r'(\d+)([smhd])'); parts = regex.findall(duration_str.lower()); delta = datetime.timedelta()
    for amount, unit in parts:
        amount = int(amount);
        if unit == 's': delta += datetime.timedelta(seconds=amount)
        elif unit == 'm': delta += datetime.timedelta(minutes=amount)
        elif unit == 'h': delta += datetime.timedelta(hours=amount)
        elif unit == 'd': delta += datetime.timedelta(days=amount)
    return delta

class GiveawayView(discord.ui.View): # ... (კოდი იგივეა) ...
    def __init__(self, giveaway_message_id): super().__init__(timeout=None); self.giveaway_message_id = giveaway_message_id
    @discord.ui.button(label="მონაწილეობა", style=discord.ButtonStyle.success, custom_id="join_giveaway_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_data(GIVEAWAY_DB); giveaway = giveaways.get(str(self.giveaway_message_id))
        if not giveaway or giveaway.get('ended', False): await interaction.response.send_message("ეს გათამაშება დასრულდა ან აღარ არსებობს.", ephemeral=True); return
        user_id = str(interaction.user.id)
        if user_id not in giveaway['participants']: giveaway['participants'].append(user_id); save_data(giveaways, GIVEAWAY_DB); await interaction.response.send_message("✅ წარმატებით ჩაერთე", ephemeral=True)
        else: await interaction.response.send_message("⚠️ შენ უკვე მონაწილეობ", ephemeral=True)

# --- აქ იწყება მთავარი კლასი ---
class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ვიწყებთ ყველა ფონურ პროცესს
        if hasattr(self, 'start_giveaway'):
            self.check_giveaways.start()
            self.update_participant_counts.start() # <-- ვიწყებთ ახალ ციკლს
        self.send_auto_message.start()
        self.sms_logs = load_data(SMS_LOG_DB)

    def cog_unload(self):
        # ვაჩერებთ ყველა ფონურ პროცესს
        if hasattr(self, 'check_giveaways') and self.check_giveaways.is_running(): self.check_giveaways.cancel()
        if hasattr(self, 'update_participant_counts') and self.update_participant_counts.is_running(): self.update_participant_counts.cancel() # <-- ვაჩერებთ ახალ ციკლს
        if self.send_auto_message.is_running(): self.send_auto_message.cancel()

    # ... (log_sms ფუნქცია უცვლელი) ...
    def log_sms(self, user_id: int, direction: str, content: str, admin_id: Optional[int] = None):
        user_id_str = str(user_id);
        if user_id_str not in self.sms_logs: self.sms_logs[user_id_str] = []
        log_entry = {"timestamp": datetime.datetime.utcnow().isoformat(),"direction": direction,"content": content}
        if admin_id: log_entry["admin_id"] = admin_id
        self.sms_logs[user_id_str].append(log_entry); save_data(self.sms_logs, SMS_LOG_DB)

    # --- სხვა ბრძანებები (Clear, Userinfo, Join, Leave, daketva, gageba, auto-msg, sms, smslog) ---
    # ...(აქ ჩასვი ყველა სხვა ბრძანება წინა კოდიდან)...
    @app_commands.command(name="clear", description="შლის ჩატის შეტყობინებებს") # ... (Clear კოდი) ...
    @app_commands.describe(amount="რაოდენობა (მაქს 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount <= 0 : await interaction.response.send_message("რაოდენობა 0-ზე მეტი უნდა იყოს.", ephemeral=True); return
        if amount > 100: await interaction.response.send_message("100ზე მეტის წაშლა არ შემიძლია", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); deleted_messages = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"წარმატებით წაიშალა {len(deleted_messages)} შეტყობინება")

    # --- Giveaway ბრძანება (განახლებული Embed-ით) ---
    @app_commands.command(name="giveaway", description="ქმნის ახალ გათამაშებას")
    @app_commands.describe(duration="რამდენი ხანი (მაგ 10m 1h 30m 2d)", prize="რა თამაშდება", winners="გამარჯვებულის რაოდენობა (default 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration);
        if delta.total_seconds() <= 0: await interaction.response.send_message("არასწორი დროის ფორმატია", ephemeral=True); return
        end_time = datetime.datetime.utcnow() + delta; end_timestamp = int(end_time.timestamp())
        embed = discord.Embed(title="🎁 ახალი გათამაშება 🎁", description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს მონაწილეობისთვის!", color=discord.Color.gold())
        embed.add_field(name="მთავრდება:", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)", inline=True) # შევცვალეთ inline
        embed.add_field(name="გამარჯვებული:", value=f"{winners} კაცი", inline=True) # შევცვალეთ inline
        embed.add_field(name="👥 მონაწილეები:", value="0", inline=True) # <-- დავამატეთ მონაწილეების ველი
        embed.set_footer(text=f"ორგანიზატორი: {interaction.user.name}"); await interaction.response.send_message("გათამაშება იწყება...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed); view = GiveawayView(msg.id); await msg.edit(view=view)
        giveaways = load_data(GIVEAWAY_DB); giveaways[str(msg.id)] = {"channel_id": interaction.channel.id, "end_time": end_time.isoformat(), "prize": prize, "winners": winners, "participants": [], "host_id": interaction.user.id, "ended": False}
        save_data(giveaways, GIVEAWAY_DB)

    # --- Giveaway-ს შემმოწმებელი (განახლებული დასრულების Embed-ით) ---
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
                participants = data['participants']; prize = data.get('prize', 'უცნობი პრიზი'); participant_count = len(participants)
                if not participants: winner_text = "არავინ მიიღო მონაწილეობა"; winners_list = []
                else: winner_ids = random.sample(participants, k=min(data['winners'], len(participants))); winners_list = [f"<@{uid}>" for uid in winner_ids]; winner_text = ", ".join(winners_list)
                winner_embed = discord.Embed(title="🎉 გათამაშება დასრულდა!", description=f"**პრიზი:** {prize}\n\n**მონაწილეობდა:** {participant_count} კაცი\n\n**გამარჯვებული:** {winner_text}", color=discord.Color.green())
                await channel.send(content=winner_text, embed=winner_embed);
                try:
                    original_embed = msg.embeds[0]
                    original_embed.title = "🎁 გათამაშება დასრულდა!"; original_embed.description = f"**პრიზი:** {prize}"; original_embed.color = discord.Color.dark_grey()
                    # ვანახლებთ ველებს
                    original_embed.set_field_at(0, name="დასრულდა:", value=f"<t:{int(end_time.timestamp())}:R>", inline=True) # Index 0
                    original_embed.set_field_at(1, name="გამარჯვებული:", value=winner_text if winners_list else "არავინ", inline=True) # Index 1
                    original_embed.set_field_at(2, name="👥 მონაწილეები:", value=f"{participant_count}", inline=True) # Index 2 (განახლებული)

                    view = discord.ui.View(); view.add_item(discord.ui.Button(label="მონაწილეობა", style=discord.ButtonStyle.success, disabled=True))
                    await msg.edit(embed=original_embed, view=view)
                except Exception as edit_error: print(f"გათამაშების ძველი შეტყობინების ედიტის შეცდომა: {edit_error}")
                data['ended'] = True; save_data(giveaways, GIVEAWAY_DB)

    # --- ახალი ფონური პროცესი: მონაწილეთა რაოდენობის განახლება ---
    @tasks.loop(minutes=1) # ანახლებს ყოველ წუთში
    async def update_participant_counts(self):
        await self.bot.wait_until_ready()
        giveaways = load_data(GIVEAWAY_DB)
        for msg_id, data in giveaways.items():
            if data.get('ended', False): continue # გამოვტოვოთ დასრულებულები

            channel = self.bot.get_channel(data['channel_id'])
            if not channel: continue

            try:
                msg = await channel.fetch_message(int(msg_id))
                if not msg.embeds: continue # თუ შეტყობინებას Embed აღარ აქვს

                current_embed = msg.embeds[0]
                participant_count = len(data.get('participants', []))

                # ვპოულობთ მონაწილეების ველს (ვიგულისხმოთ რომ ის მე-3 ველია, index=2)
                # და ვანახლებთ მის მნიშვნელობას
                # ვამოწმებთ ველების რაოდენობას, რომ შეცდომა არ მოხდეს
                if len(current_embed.fields) >= 3:
                     # ვიღებთ მიმდინარე მნიშვნელობას
                     current_value_str = current_embed.fields[2].value
                     # ვანახლებთ მხოლოდ იმ შემთხვევაში, თუ მნიშვნელობა შეიცვალა
                     if current_value_str != str(participant_count):
                          current_embed.set_field_at(2, name="👥 მონაწილეები:", value=str(participant_count), inline=True)
                          await msg.edit(embed=current_embed)
                else:
                    # თუ ველი რატომღაც არ არსებობს (არ უნდა მოხდეს წესით), ვცადოთ დამატება
                    current_embed.add_field(name="👥 მონაწილეები:", value=str(participant_count), inline=True)
                    await msg.edit(embed=current_embed)


            except discord.NotFound:
                # თუ შეტყობინება წაშლილია, აღვნიშნოთ როგორც დასრულებული
                print(f"Giveaway message {msg_id} not found, marking as ended.")
                giveaways[msg_id]['ended'] = True
                save_data(giveaways, GIVEAWAY_DB)
            except discord.Forbidden:
                print(f"უფლება არ მაქვს შევცვალო giveaway message {msg_id} არხში #{channel.name}")
                # აქ შეგვიძლია გავაჩეროთ ამ კონკრეტული გათამაშების განახლება?
                pass
            except Exception as e:
                print(f"მონაწილეების განახლების შეცდომა giveaway {msg_id}: {e}")

    # ... (დანარჩენი ბრძანებები: userinfo, join, leave, daketva, gageba, auto-msg, sms, smslog უცვლელი) ...
    @app_commands.command(name="userinfo", description="აჩვენებს ინფორმაციას მომხმარებელზე") # ... (Userinfo კოდი) ...
    @app_commands.describe(user="აირჩიე მომხმარებელი (თუ არ აირჩევ შენსას აჩვენებს)")
    async def userinfo(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target_user = user or interaction.user; embed = discord.Embed(title=f"{target_user.name}#{target_user.discriminator}" if target_user.discriminator != '0' else target_user.name, color=target_user.color)
        if target_user.avatar: embed.set_thumbnail(url=target_user.avatar.url)
        embed.add_field(name="ID", value=target_user.id, inline=False); embed.add_field(name="შემოუერთდა სერვერს", value=f"<t:{int(target_user.joined_at.timestamp())}:R>", inline=True); embed.add_field(name="ანგარიში შეიქმნა", value=f"<t:{int(target_user.created_at.timestamp())}:R>", inline=True)
        roles = [role.mention for role in target_user.roles if role.name != "@everyone"];
        if roles: embed.add_field(name=f"როლები [{len(roles)}]", value=", ".join(roles) if len(roles) < 10 else f"{len(roles)} როლი", inline=False)
        else: embed.add_field(name="როლები", value="არ აქვს", inline=False)
        if target_user.top_role.name != "@everyone": embed.add_field(name="უმაღლესი როლი", value=target_user.top_role.mention, inline=True)
        embed.add_field(name="ბოტი?", value="კი" if target_user.bot else "არა", inline=True); await interaction.response.send_message(embed=embed)

    @app_commands.command(name="join", description="ბოტი შემოდის შენს ხმოვან არხში") # ... (Join კოდი) ...
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
            if interaction.guild.voice_client: await interaction.guild.voice_client.move_to(channel); await interaction.response.send_message(f"გადმოვედი `{channel.name}`-ში.")
            else: try: await channel.connect(); await interaction.response.send_message(f"შემოვედი `{channel.name}`-ში.") except Exception as e: await interaction.response.send_message(f"ვერ შემოვედი არხში: {e}", ephemeral=True)
        else: await interaction.response.send_message("ჯერ ხმოვან არხში უნდა იყო!", ephemeral=True)

    @app_commands.command(name="leave", description="ბოტი გადის ხმოვანი არხიდან") # ... (Leave კოდი) ...
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("გავედი ხმოვანი არხიდან.")
        else: await interaction.response.send_message("მე ისედაც არ ვარ ხმოვან არხში.", ephemeral=True)

    @app_commands.command(name="daketva") # ... (daketva კოდი) ...
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role; overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = False
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი დაიკეტა.")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    @app_commands.command(name="gageba") # ... (gageba კოდი) ...
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role; overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = None
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი გაიღო.")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    # --- Auto-Message ფუნქციონალი ---
    @app_commands.command(name="set-18plus-chat", description="აყენებს არხს 18+ შეხსენებისთვის") # ... (auto-msg setup კოდი) ...
    @app_commands.describe(channel="აირჩიე არხი")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def automessage_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(AUTOMESSAGE_DB); guild_id = str(interaction.guild.id); data[guild_id] = {"channel_id": channel.id}; save_data(data, AUTOMESSAGE_DB)
        await interaction.response.send_message(f"18+ შეხსენების არხი არის {channel.mention}", ephemeral=True)

    async def _send_the_message(self, channel: discord.TextChannel): # ... (_send_the_message კოდი) ...
        message_text = ("⚠️ @everyone\nწესი 1- არ ვსაუბრობთ ამ ჩათზე\nწესი 2- აუცილებლად ვიცავთ 1 წესს\nწესი 3- აქ რაც იწერება სერვერის პასუხისმგებლობაში არ არის :დ\n⚠️")
        try: await channel.send(message_text, allowed_mentions=discord.AllowedMentions(everyone=True)); return True
        except discord.Forbidden: print(f"ERROR: არ მაქვს უფლება გავაგზავნო #{channel.name} ({channel.guild.name})"); return False
        except Exception as e: print(f"ERROR: ავტო შეტყობინების გაგზავნისას: {e}"); return False

    @app_commands.command(name="gaxseneba", description="აგზავნის 18+ შეხსენებას მითითებულ არხში") # ... (gaxseneba კოდი) ...
    @app_commands.checks.has_permissions(manage_messages=True)
    async def automessage_sendnow(self, interaction: discord.Interaction):
        data = load_data(AUTOMESSAGE_DB); guild_id = str(interaction.guild.id)
        if guild_id in data and 'channel_id' in data[guild_id]:
            channel_id = data[guild_id]['channel_id']; channel = self.bot.get_channel(channel_id)
            if channel: await interaction.response.defer(ephemeral=True); success = await self._send_the_message(channel); await interaction.followup.send("შეტყობინება გაიგზავნა." if success else "ვერ გავაგზავნე შეტყობინება.", ephemeral=True)
            else: await interaction.response.send_message("ვერ ვიპოვე არხი.", ephemeral=True)
        else: await interaction.response.send_message("ჯერ დააყენე არხი /set-18plus-chat.", ephemeral=True)

    @tasks.loop(hours=5) # ... (send_auto_message კოდი) ...
    async def send_auto_message(self):
        await self.bot.wait_until_ready(); data = load_data(AUTOMESSAGE_DB)
        for guild_id, config in data.items():
            if 'channel_id' in config: channel = self.bot.get_channel(config['channel_id']);
            if channel: await self._send_the_message(channel)
            else: print(f"WARNING: ვერ მოიძებნა auto-msg არხი ID={config['channel_id']}")

    # --- /sms ბრძანება ---
    @app_commands.command(name="sms", description="უგზავნის ანონიმურ პირად შეტყობინებას მომხმარებელს") # ... (sms კოდი) ...
    @app_commands.describe(user="მომხმარებელი ვისაც უგზავნი", text="შეტყობინების ტექსტი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_sms(self, interaction: discord.Interaction, user: discord.Member, text: str):
        if user.bot: await interaction.response.send_message("ბოტს პირად შეტყობინებას ვერ გაუგზავნი.", ephemeral=True); return
        try:
            message_to_send = f"**შეტყობინება {interaction.guild.name}-დან:**\n\n{text}"; await user.send(message_to_send)
            self.log_sms(user_id=user.id, direction="outgoing", content=text, admin_id=interaction.user.id)
            await interaction.response.send_message(f"ანონიმური შეტყობინება გაეგზავნა {user.mention}-ს.", ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message(f"ვერ გავუგზავნე შეტყობინება {user.mention}-ს.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    # --- /smslog ბრძანება ---
    @app_commands.command(name="smslog", description="აჩვენებს მითითებულ მომხმარებელთან მიმოწერის ისტორიას") # ... (smslog კოდი) ...
    @app_commands.describe(user="მომხმარებელი ვისი ლოგებიც გინდა ნახო")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def view_sms_log(self, interaction: discord.Interaction, user: discord.Member):
        user_id_str = str(user.id)
        if user_id_str not in self.sms_logs or not self.sms_logs[user_id_str]: await interaction.response.send_message(f"{user.mention}-თან მიმოწერის ისტორია ცარიელია.", ephemeral=True); return
        logs = self.sms_logs[user_id_str]; embed = discord.Embed(title=f"SMS ლოგი - {user.name}", color=discord.Color.blurple()); log_text = ""
        for entry in logs[-10:]:
            timestamp = datetime.datetime.fromisoformat(entry['timestamp']); time_formatted = discord.utils.format_dt(timestamp, style='f')
            direction = "➡️ (Admin)" if entry['direction'] == "outgoing" else "⬅️ (User)"
            content = entry['content'];
            if len(content) > 150: content = content[:147] + "..."
            log_text += f"`{time_formatted}`\n{direction}: {content}\n\n"
        if not log_text: log_text = "ლოგები ვერ მოიძებნა."; embed.description = log_text; embed.set_footer(text=f"ნაჩვენებია ბოლო {len(logs[-10:])} შეტყობინება")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ივენთი შემომავალი DM ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None and not message.author.bot:
            user_id_str = str(message.author.id)
            if user_id_str in self.sms_logs:
                self.log_sms(user_id=message.author.id, direction="incoming", content=message.content)

# --- Cog-ის ჩატვირთვის ფუნქცია ---
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
