import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
import re

# --- Giveaway მონაცემთა ბაზა ---
GIVEAWAY_DB = "giveaways.json"

def load_giveaway_data():
    if not os.path.exists(GIVEAWAY_DB): return {}
    try:
        with open(GIVEAWAY_DB, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_giveaway_data(data):
    with open(GIVEAWAY_DB, "w") as f: json.dump(data, f, indent=4)

def parse_duration(duration_str: str) -> datetime.timedelta:
    regex = re.compile(r'(\d+)([smhd])')
    parts = regex.findall(duration_str.lower())
    delta = datetime.timedelta()
    for amount, unit in parts:
        amount = int(amount)
        if unit == 's': delta += datetime.timedelta(seconds=amount)
        elif unit == 'm': delta += datetime.timedelta(minutes=amount)
        elif unit == 'h': delta += datetime.timedelta(hours=amount)
        elif unit == 'd': delta += datetime.timedelta(days=amount)
    return delta

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_message_id):
        super().__init__(timeout=None)
        self.giveaway_message_id = giveaway_message_id
    @discord.ui.button(label="მონაწილეობა", style=discord.ButtonStyle.success, custom_id="join_giveaway_button")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_giveaway_data()
        giveaway = giveaways.get(str(self.giveaway_message_id))
        if not giveaway:
            await interaction.response.send_message("ეს გათამაშება აღარ არსებობს", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        if user_id not in giveaway['participants']:
            giveaway['participants'].append(user_id)
            save_giveaway_data(giveaways)
            await interaction.response.send_message("წარმატებით ჩაერთე გათამაშებაში", ephemeral=True)
        else:
            await interaction.response.send_message("შენ უკვე მონაწილეობ", ephemeral=True)

# --- აქ იწყება მთავარი კლასი ---
class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    # --- გამართული Clear ბრძანება ---
    @app_commands.command(name="clear", description="შლის ჩატის შეტყობინებებს")
    @app_commands.describe(amount="რაოდენობა (მაქს 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount > 100:
            await interaction.response.send_message("100ზე მეტის წაშლა არ შემიძლია", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted_messages = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"წარმატებით წაიშალა {len(deleted_messages)} შეტყობინება")

    # --- გამართული Giveaway ბრძანება ---
    @app_commands.command(name="giveaway", description="ქმნის ახალ გათამაშებას")
    @app_commands.describe(
        duration="რამდენი ხანი (მაგ 10m 1h 30m 2d)",
        prize="რა თამაშდება",
        winners="გამარჯვებულის რაოდენობა (default 1)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration)
        if delta.total_seconds() <= 0:
            await interaction.response.send_message("არასწორი დროის ფორმატია", ephemeral=True)
            return
        end_time = datetime.datetime.utcnow() + delta
        end_timestamp = int(end_time.timestamp())
        embed = discord.Embed(title="🎁 ახალი გათამაშება 🎁", description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს მონაწილეობისთვის!", color=discord.Color.gold())
        embed.add_field(name="მთავრდება:", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)")
        embed.add_field(name="გამარჯვებული:", value=f"{winners} კაცი")
        embed.set_footer(text=f"ორგანიზატორი: {interaction.user.name}")
        await interaction.response.send_message("გათამაშება იწყება...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed)
        view = GiveawayView(msg.id)
        await msg.edit(view=view)
        giveaways = load_giveaway_data()
        giveaways[str(msg.id)] = {
            "channel_id": interaction.channel.id, "end_time": end_time.isoformat(), "prize": prize,
            "winners": winners, "participants": [], "host_id": interaction.user.id, "ended": False
        }
        save_giveaway_data(giveaways)

    # --- გამართული Giveaway-ს შემმოწმებელი ---
    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        await self.bot.wait_until_ready()
        giveaways = load_giveaway_data()
        current_time = datetime.datetime.utcnow()
        for msg_id, data in list(giveaways.items()):
            if data.get('ended', False): continue
            end_time = datetime.datetime.fromisoformat(data['end_time'])
            if current_time >= end_time:
                channel = self.bot.get_channel(data['channel_id'])
                if not channel: continue
                try: msg = await channel.fetch_message(int(msg_id))
                except discord.NotFound: data['ended'] = True; save_giveaway_data(giveaways); continue
                participants = data['participants']
                prize = data.get('prize', 'უცნობი პრიზი')
                if not participants:
                    winner_text = "არავინ მიიღო მონაწილეობა"
                    winners_list = []
                else:
                    winner_ids = random.sample(participants, k=min(data['winners'], len(participants)))
                    winners_list = [f"<@{uid}>" for uid in winner_ids]
                    winner_text = ", ".join(winners_list)
                winner_embed = discord.Embed(title="🎉 გათამაშება დასრულდა 🎉", description=f"**პრიზი:** {prize}\n\nგილოცავთ {winner_text}!", color=discord.Color.green())
                await channel.send(content=winner_text, embed=winner_embed)
                original_embed = msg.embeds[0]
                original_embed.title = "🎁 გათამაშება დასრულდა 🎁"
                original_embed.description = f"**პრიზი:** {prize}"
                original_embed.color = discord.Color.dark_grey()
                original_embed.set_field_at(0, name="დასრულდა:", value=f"<t:{int(end_time.timestamp())}:R>")
                original_embed.add_field(name="გამარჯვებული:", value=winner_text if winners_list else "არავინ")
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="მონაწილეობა", style=discord.ButtonStyle.success, disabled=True))
                await msg.edit(embed=original_embed, view=view)
                data['ended'] = True
                save_giveaway_data(giveaways)

    # --- ახალი /server ბრძანება იწყება აქ ---
    @app_commands.command(name="server", description="აჩვენებს ინფორმაციას Lazare's Croud სერვერზე")
    async def server_info(self, interaction: discord.Interaction):
        # --- ⚠️ აქ ჩაწერე Lazare's Croud სერვერის ID ---
        LAZARE_SERVER_ID = 1427644909162074165 # ჩაანაცვლე ნამდვილი ID-ით!
        # -----------------------------------------------
        
        INVITE_LINK = "https://discord.gg/tsNYpPaKkS" # შენი მოწვევის ლინკი
        
        guild = self.bot.get_guild(LAZARE_SERVER_ID)
        
        if guild is None:
            # ეს მოხდება, თუ ბოტი არ არის დამატებული Lazare's Croud სერვერზე
            await interaction.response.send_message("შეცდომა სერვერის ინფორმაციის მოძიებისას!", ephemeral=True)
            return
            
        owner = guild.owner # ვიღებთ სერვერის მფლობელს
        member_count = guild.member_count # ვიღებთ წევრების რაოდენობას

        embed = discord.Embed(
            title=guild.name, # სერვერის სახელი
            description="""
            **ეს არის საუკეთესო ქართული ქომუნითი!**
            აქ შეგიძლია გაერთო იპოვო მეგობრები
            ითამაშო თამაშები და უბრალოდ დრო გაატარო
            
            შემოგვიერთდი!
            """,
            color=discord.Color.blue() # შეგიძლია ფერი შეცვალო
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url) # სერვერის იკონკა
            
        # ვამატებთ ინფორმაციას ველებად
        embed.add_field(name="👑 მფლობელი", value=owner.mention if owner else "უცნობია", inline=True)
        embed.add_field(name="👥 წევრები", value=str(member_count), inline=True)
        embed.add_field(name="🔗 მოსაწვევი ლინკი", value=f"[დააჭირე აქ]({INVITE_LINK})", inline=False)
        
        embed.set_footer(text="გელოდებით!")
        
        await interaction.response.send_message(embed=embed)

# --- მთავრდება /server ბრძანება ---

# ეს ფუნქცია საჭიროა, რომ ბოტმა ეს ფაილი ჩატვირთოს
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
