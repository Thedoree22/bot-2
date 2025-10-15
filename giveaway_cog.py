import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
import re

DB_FILE = "giveaways.json"

def load_data():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_data(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

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
        giveaways = load_data()
        giveaway = giveaways.get(str(self.giveaway_message_id))
        if not giveaway:
            await interaction.response.send_message("ეს გათამაშება აღარ არსებობს.", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        if user_id not in giveaway['participants']:
            giveaway['participants'].append(user_id)
            save_data(giveaways)
            await interaction.response.send_message("წარმატებით ჩაერთე გათამაშებაში!", ephemeral=True)
        else:
            await interaction.response.send_message("შენ უკვე მონაწილეობ ამ გათამაშებაში.", ephemeral=True)

class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    giveaway_group = app_commands.Group(name="giveaway", description="Gatamashebistvis")

    # --- შესწორება #1: ბრძანების აღწერა შეცვლილია ---
    @giveaway_group.command(name="start", description="Sheqmeni gatamasheba")
    @app_commands.describe(
        duration="ramdeni khani gagrdzeldes? (mag: 10m, 1h 30m, 2d)",
        prize="ra tamashdeba?",
        winners="gamarjvebulebis raodenoba (default: 1)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, interaction: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration)
        if delta.total_seconds() <= 0:
            await interaction.response.send_message("Araswori drois formatia!", ephemeral=True)
            return
            
        end_time = datetime.datetime.utcnow() + delta
        end_timestamp = int(end_time.timestamp())

        embed = discord.Embed(
            title="🎁 ახალი გათამაშება!",
            description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს მონაწილეობისთვის!",
            color=discord.Color.gold()
        )
        embed.add_field(name="მთავრდება:", value=f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)")
        embed.add_field(name="გამარჯვებული:", value=f"{winners} კაცი")
        embed.set_footer(text=f"ორგანიზატორი: {interaction.user.name}")

        await interaction.response.send_message("Gatamasheba iwyeba...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed)
        view = GiveawayView(msg.id)
        await msg.edit(view=view)

        giveaways = load_data()
        giveaways[str(msg.id)] = {
            "channel_id": interaction.channel.id, "end_time": end_time.isoformat(), "prize": prize,
            "winners": winners, "participants": [], "host_id": interaction.user.id, "ended": False
        }
        save_data(giveaways)

    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        await self.bot.wait_until_ready()
        giveaways = load_data()
        current_time = datetime.datetime.utcnow()
        
        for msg_id, data in list(giveaways.items()):
            if data.get('ended', False): continue
            
            end_time = datetime.datetime.fromisoformat(data['end_time'])
            
            if current_time >= end_time:
                channel = self.bot.get_channel(data['channel_id'])
                if not channel: continue
                try:
                    msg = await channel.fetch_message(int(msg_id))
                except discord.NotFound:
                    data['ended'] = True; save_data(giveaways); continue

                participants = data['participants']
                
                # --- შესწორება #2: ვიღებთ პრიზს data-დან, რომ არ დაიკრაშოს ---
                prize = data.get('prize', 'უცნობი პრიზი')

                if not participants:
                    winner_text = "არავინ მიიღო მონაწილეობა."
                    winners_list = []
                else:
                    winner_ids = random.sample(participants, k=min(data['winners'], len(participants)))
                    winners_list = [f"<@{uid}>" for uid in winner_ids]
                    winner_text = ", ".join(winners_list)
                
                winner_embed = discord.Embed(
                    title="🎉 გათამაშება დასრულდა!",
                    description=f"**პრიზი:** {prize}\n\nგილოცავთ, {winner_text}!",
                    color=discord.Color.green()
                )
                await channel.send(content=winner_text, embed=winner_embed)

                original_embed = msg.embeds[0]
                original_embed.title = "🎁 გათამაშება დასრულდა!"
                original_embed.description = f"**პრიზი:** {prize}"
                original_embed.color = discord.Color.dark_grey()
                original_embed.set_field_at(0, name="დასრულდა:", value=f"<t:{int(end_time.timestamp())}:R>")
                original_embed.add_field(name="გამარჯვებული(ები):", value=winner_text if winners_list else "არავინ")
                
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="მონაწილეობა", style=discord.ButtonStyle.success, disabled=True))
                
                await msg.edit(embed=original_embed, view=view)
                
                data['ended'] = True
                save_data(giveaways)

async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
