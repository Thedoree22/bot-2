import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
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
        guild = member.guild # ვიღებთ სერვერის ობიექტს
        guild_id = str(guild.id)
        # --- როლის მინიჭება (უცვლელი) ---
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id"); role = guild.get_role(role_id)
            if role:
                try: await member.add_roles(role)
                except Exception as e: print(f"Error adding role: {e}")

        # --- ახალი Welcome სურათი (შენი დიზაინის მიხედვით) ---
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = guild.get_channel(channel_id)
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

                    # --- ზედა ნაწილი: სერვერის ლოგო და სახელი ---
                    ICON_SIZE = 100 # ლოგოს ზომა
                    icon_pos = (50, 40) # ლოგოს პოზიცია (X, Y)

                    # ვცდილობთ სერვერის ლოგოს ჩატვირთვას
                    server_icon_image = None
                    if guild.icon:
                        try:
                            icon_response = requests.get(guild.icon.url)
                            server_icon_image = Image.open(io.BytesIO(icon_response.content)).convert("RGBA")
                            server_icon_image = server_icon_image.resize((ICON_SIZE, ICON_SIZE))
                        except Exception as e:
                            print(f"Server icon download error: {e}")
                            server_icon_image = None # თუ შეცდომაა, ლოგოს არ ვხატავთ

                    if server_icon_image:
                         img.paste(server_icon_image, icon_pos) # ვხატავთ ლოგოს
                         server_name_x = icon_pos[0] + ICON_SIZE + 30 # სახელის X კოორდინატი
                    else:
                         # თუ ლოგო არ არის, სახელს მარცხნიდან ვიწყებთ
                         server_name_x = icon_pos[0]
                         draw.rectangle([icon_pos, (icon_pos[0]+ICON_SIZE, icon_pos[1]+ICON_SIZE)], outline="grey", width=2) # ცარიელი ჩარჩო ლოგოს ნაცვლად

                    # ვხატავთ სერვერის სახელს
                    try:
                        font_server_name = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 50)
                    except IOError:
                        print("შეცდომა: Noto Sans Georgian Bold ფონტი ვერ მოიძებნა!"); return
                    
                    server_name_y = icon_pos[1] + ICON_SIZE // 2 # Y კოორდინატი (ვერტიკალურად ცენტრში)
                    self.draw_text_with_shadow(draw, (server_name_x, server_name_y), guild.name, font_server_name, fill_color=(255, 255, 255), shadow_offset=(3,3))

                    # --- ქვედა ნაწილი: მომხმარებლის ავატარი, სახელი და ტექსტი ---
                    AVATAR_SIZE = 120 # ავატარის ზომა
                    avatar_pos = (80, 190) # ავატარის პოზიცია (უფრო ქვემოთ)

                    # ავატარის ჩატვირთვა და დამრგვალება
                    avatar_url = member.avatar.url; response = requests.get(avatar_url); avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                    avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                    img.paste(avatar_image, avatar_pos, mask) # ვხატავთ ავატარს

                    # ვხატავთ ტექსტს ავატარის მარჯვნივ
                    text_x = avatar_pos[0] + AVATAR_SIZE + 40
                    try:
                        font_user_name = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 45)
                        font_welcome_text = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 30)
                    except IOError:
                        print("შეცდომა: Noto Sans Georgian ფონტები ვერ მოიძებნა!"); return

                    # მომხმარებლის სახელი
                    user_name = member.name
                    if len(user_name) > 20: user_name = user_name[:17] + "..."
                    user_name_y = avatar_pos[1] + 30 # სახელის Y კოორდინატი
                    self.draw_text_with_shadow(draw, (text_x, user_name_y), user_name, font_user_name, fill_color=(255, 255, 255))

                    # მისასალმებელი ტექსტი
                    welcome_text = "წარმატებულ გართობას გისურვებთ ჩვენს დისქორდ სერვერზე"
                    welcome_text_y = user_name_y + 55 # ტექსტის Y კოორდინატი
                    self.draw_text_with_shadow(draw, (text_x, welcome_text_y), welcome_text, font_welcome_text, fill_color=(200, 200, 200))

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
