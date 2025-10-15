import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import requests
import io

DB_FILE = "welcome_data.json"

def load_data():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_data(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_data = load_data()

    @app_commands.command(name="welcome-setup", description="აყენებს არხს, სადაც გაიგზავნება მისალმების შეტყობინებები.")
    @app_commands.describe(channel="აირჩიეთ მისალმების არხი.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        self.welcome_data[guild_id] = {"channel_id": channel.id}
        save_data(self.welcome_data)
        await interaction.response.send_message(f"მისალმების არხი დაყენებულია {channel.mention}-ზე!", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        if guild_id not in self.welcome_data:
            return

        channel_id = self.welcome_data[guild_id].get("channel_id")
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        # --- სურათის შექმნა ---
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
            
            draw.text((500, 350), "WELCOME", fill=(255, 255, 255), font=font_big, anchor="ms")
            draw.text((500, 420), member.name, fill=(255, 255, 255), font=font_small, anchor="ms")

            # --- აი, ახალი ხაზი სერვერის სახელისთვის ---
            # member.guild.name ავტომატურად იღებს სერვერის სახელს
            server_name_text = f"სერვერზე {member.guild.name}"
            draw.text((500, 480), server_name_text, fill=(220, 220, 220), font=font_small, anchor="ms") # ოდნავ ღია ფერით

            final_buffer = io.BytesIO()
            background.save(final_buffer, "PNG")
            final_buffer.seek(0)
            
            file = discord.File(fp=final_buffer, filename="welcome.png")
            await channel.send(f"სერვერზე შემოგვიერთდა {member.mention}! კეთილი იყოს შენი მობრძანება!", file=file)

        except FileNotFoundError:
            print("შეცდომა: welcome_background.png ან ფონტები არ არის ატვირთული GitHub-ზე!")
            await channel.send(f"სერვერზე შემოგვიერთდა {member.mention}! კეთილი იყოს შენი მობრძანება!")
        except Exception as e:
            print(f"მოხდა შეცდომა მისალმების სურათის შექმნისას: {e}")
            await channel.send(f"სერვერზე შემოგვიერთდა {member.mention}! კეთილი იყოს შენი მობრძანება!")

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
