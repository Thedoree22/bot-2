import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import requests
import io

WELCOME_DB = "welcome_data.json"
AUTOROLE_DB = "autorole_data.json"

def load_data(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_data(data, file):
    with open(file, "w") as f: json.dump(data, f, indent=4)

class CommunityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="welcome", description="აყენებს მისალმების არხს")
    @app_commands.describe(channel="აირჩიე არხი სადაც მოხდება მისალმება")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(WELCOME_DB)
        data[str(interaction.guild.id)] = {"channel_id": channel.id}
        save_data(data, WELCOME_DB)
        await interaction.response.send_message(f"მისალმების არხი არის {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="აყენებს როლს რომელიც ავტომატურად მიენიჭება")
    @app_commands.describe(role="აირჩიე როლი რომ მიენიჭოს")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message("მე არ შემიძლია ამ როლის მინიჭება მიუთითე ჩემს როლზე დაბალი როლი", ephemeral=True)
            return
        data = load_data(AUTOROLE_DB)
        data[str(interaction.guild.id)] = {"role_id": role.id}
        save_data(data, AUTOROLE_DB)
        await interaction.response.send_message(f"ავტო როლი არის **{role.name}**", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id")
            role = member.guild.get_role(role_id)
            if role:
                try: await member.add_roles(role)
                except Exception as e: print(f"Error adding role: {e}")

        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = member.guild.get_channel(channel_id)
            if channel:
                try:
                    background = Image.open("welcome_background.png").convert("RGBA")
                    avatar_url = member.avatar.url
                    response = requests.get(avatar_url)
                    avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                    avatar_image = avatar_image.resize((250, 250))
                    mask = Image.new("L", (250, 250), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, 250, 250), fill=255)
                    background.paste(avatar_image, (375, 80), mask)
                    draw = ImageDraw.Draw(background)
                    font_big = ImageFont.truetype("Poppins-Bold.ttf", 60)
                    font_small = ImageFont.truetype("Poppins-Regular.ttf", 40)
                    draw.text((500, 350), "მოგესალმებით", fill=(255, 255, 255), font=font_big, anchor="ms")
                    draw.text((500, 420), member.name, fill=(255, 255, 255), font=font_small, anchor="ms")
                    server_name_text = f"სერვერზე {member.guild.name}"
                    draw.text((500, 480), server_name_text, fill=(220, 220, 220), font=font_small, anchor="ms")
                    final_buffer = io.BytesIO()
                    background.save(final_buffer, "PNG")
                    final_buffer.seek(0)
                    file = discord.File(fp=final_buffer, filename="welcome.png")
                    await channel.send(f"შემოგვიერთდა {member.mention} გთხოვ გაერთო", file=file)
                except Exception as e:
                    print(f"Error creating welcome image: {e}")

async def setup(bot: commands.Cog):
    await bot.add_cog(CommunityCog(bot))
