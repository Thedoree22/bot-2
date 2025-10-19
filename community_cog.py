import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
import io
import random

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

    # --- Setup ბრძანებები (უცვლელი) ---
    @app_commands.command(name="welcome", description="აყენებს მისალმების არხს")
    @app_commands.describe(channel="აირჩიე არხი სადაც მოხდება მისალმება")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(WELCOME_DB); data[str(interaction.guild.id)] = {"channel_id": channel.id}; save_data(data, WELCOME_DB)
        await interaction.response.send_message(f"მისალმების არხი არის {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="აყენებს როლს რომელიც ავტომატურად მიენიჭება")
    @app_commands.describe(role="აირჩიე როლი რომ მიენიჭოს")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message("მე არ შემიძლია ამ როლის მინიჭება მიუთითე ჩემს როლზე დაბალი როლი", ephemeral=True); return
        data = load_data(AUTOROLE_DB); data[str(interaction.guild.id)] = {"role_id": role.id}; save_data(data, AUTOROLE_DB)
        await interaction.response.send_message(f"ავტო როლი არის **{role.name}**", ephemeral=True)

    # --- ტექსტის დახატვის დამხმარე ფუნქცია Shadow ეფექტით ---
    def draw_text_with_shadow(self, draw, xy, text, font, fill_color, shadow_color=(0, 0, 0, 150), shadow_offset=(2, 2)):
        x, y = xy; sx, sy = shadow_offset
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_color) # Shadow
        draw.text(xy, text, font=font, fill=fill_color) # Main text

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        # --- როლის მინიჭება (უცვლელი) ---
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id"); role = member.guild.get_role(role_id)
            if role:
                try: await member.add_roles(role)
                except Exception as e: print(f"Error adding role: {e}")

        # --- ახალი Welcome სურათი (ძველი სტილი, გაზრდილი ტექსტი) ---
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = member.guild.get_channel(channel_id)
            if channel:
                try:
                    W, H = (1000, 400) # სურათის ზომა

                    # ფონი: იასამნისფერ-შავი გრადიენტი + ვარსკვლავები (უცვლელი)
                    img = Image.new("RGBA", (W, H)); draw = ImageDraw.Draw(img)
                    start_color = (40, 0, 80); end_color = (0, 0, 0)
                    for i in range(H):
                        ratio=i/H; r=int(start_color[0]*(1-ratio)+end_color[0]*ratio); g=int(start_color[1]*(1-ratio)+end_color[1]*ratio); b=int(start_color[2]*(1-ratio)+end_color[2]*ratio)
                        draw.line([(0,i),(W,i)], fill=(r,g,b))
                    star_color = (255, 255, 255, 150)
                    for _ in range(100):
                        x=random.randint(0,W); y=random.randint(0,H); size=random.randint(1,3)
                        draw.ellipse([(x,y),(x+size,y+size)], fill=star_color)

                    # ავატარი (ისევ მარცხნივ, ოდნავ პატარა)
                    avatar_url = member.avatar.url; response =
