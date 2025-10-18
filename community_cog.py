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
        # --- როლის მინიჭება (უცვლელი) ---
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id")
            role = member.guild.get_role(role_id)
            if role:
                try: await member.add_roles(role)
                except Exception as e: print(f"Error adding role: {e}")

        # --- ახალი Welcome სურათის ლოგიკა (იასამნისფერი + ვარსკვლავები) ---
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = member.guild.get_channel(channel_id)
            if channel:
                try:
                    W, H = (1000, 400) # სურათის ზომა

                    # ვქმნით ფონს - იასამნისფერ-შავი გრადიენტი
                    img = Image.new("RGBA", (W, H))
                    draw = ImageDraw.Draw(img)
                    start_color = (40, 0, 80)  # მუქი იასამნისფერი
                    end_color = (0, 0, 0)      # შავი
                    for i in range(H):
                        ratio = i / H
                        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
                        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
                        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
                        draw.line([(0, i), (W, i)], fill=(r, g, b))

                    # ვამატებთ შემთხვევით ვარსკვლავებს
                    star_color = (255, 255, 255, 150) # თეთრი, ოდნავ გამჭვირვალე
                    for _ in range(100): # 100 ვარსკვლავი
                        x = random.randint(0, W)
                        y = random.randint(0, H)
                        size = random.randint(1, 3) # პატარა ვარსკვლავები
                        draw.ellipse([(x, y), (x+size, y+size)], fill=star_color)

                    # მომხმარებლის ავატარის ჩამოტვირთვა
                    avatar_url = member.avatar.url
                    response = requests.get(avatar_url)
                    avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")

                    # ავატარის ზომის შეცვლა და წრედ გადაქცევა
                    AVATAR_SIZE = 220
                    avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)

                    # ავატარის განთავსება მარცხნივ
                    avatar_pos = (50, (H // 2) - (AVATAR_SIZE // 2))
                    img.paste(avatar_image, avatar_pos, mask)

                    # ტექსტის დამატება (მარჯვნივ)
                    draw = ImageDraw.Draw(img)
                    try:
                        font_big = ImageFont.truetype("Poppins-Bold.ttf", 70)
                        font_small = ImageFont.truetype("Poppins-Regular.ttf", 40)
                        font_server = ImageFont.truetype("Poppins-Regular.ttf", 30)
                    except IOError:
                         print("გაფრთხილება: Poppins ფონტები ვერ მოიძებნა! ვიყენებ დეფოლტს.")
                         font_big = ImageFont.truetype("arial.ttf", 70) # ვცდილობთ Arial-ს
                         font_small = ImageFont.truetype("arial.ttf", 40)
                         font_server = ImageFont.truetype("arial.ttf", 30)
                         # თუ Arial-იც არ არის, Pillow გამოიყენებს თავის ჩაშენებულს

                    text_x = avatar_pos[0] + AVATAR_SIZE + 50 # ტექსტის X კოორდინატი (ავატარის მარჯვნივ)
                    
                    # Welcome ტექსტი
                    draw.text((text_x, H // 2 - 60), "მოგესალმებით", fill=(255, 255, 255), font=font_big)
                    
                    # მომხმარებლის სახელი
                    user_name = member.name
                    if len(user_name) > 15: user_name = user_name[:12] + "..."
                    draw.text((text_x, H // 2 + 20), user_name, fill=(200, 200, 200), font=font_small)
                    
                    # სერვერის სახელი
                    server_name_text = f"{member.guild.name}-ზე"
                    draw.text((text_x, H // 2 + 70), server_name_text, fill=(150, 150, 150), font=font_server)

                    # სურათის შენახვა
                    final_buffer = io.BytesIO()
                    img.save(final_buffer, "PNG")
                    final_buffer.seek(0)

                    file = discord.File(fp=final_buffer, filename="welcome.png")
                    await channel.send(f"შემოგვიერთდა {member.mention} გთხოვ გაერთო", file=file)
                except Exception as e:
                    print(f"Error creating welcome image: {e}")
                    await channel.send(f"შემოგვიერთდა {member.mention} გთხოვ გაერთო")

async def setup(bot: commands.Cog):
    await bot.add_cog(CommunityCog(bot))
