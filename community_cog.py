import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter # ImageFilter დავამატეთ Glow-სთვის
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

    # --- Welcome Setup (უცვლელი) ---
    @app_commands.command(name="welcome", description="აყენებს მისალმების არხს")
    @app_commands.describe(channel="აირჩიე არხი სადაც მოხდება მისალმება")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(WELCOME_DB)
        data[str(interaction.guild.id)] = {"channel_id": channel.id}
        save_data(data, WELCOME_DB)
        await interaction.response.send_message(f"მისალმების არხი არის {channel.mention}", ephemeral=True)

    # --- AutoRole Setup (უცვლელი) ---
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

    # --- ტექსტის დახატვის დამხმარე ფუნქცია Glow ეფექტით ---
    def draw_text_with_glow(self, draw, xy, text, font, fill_color, glow_color=(255, 255, 255), glow_radius=3):
        x, y = xy
        # ვხატავთ "ჩრდილს" (Glow) რამდენჯერმე ოდნავ გადაწეულს
        shadow_offset = glow_radius // 2 + 1
        draw.text((x-shadow_offset, y-shadow_offset), text, font=font, fill=glow_color)
        draw.text((x+shadow_offset, y-shadow_offset), text, font=font, fill=glow_color)
        draw.text((x-shadow_offset, y+shadow_offset), text, font=font, fill=glow_color)
        draw.text((x+shadow_offset, y+shadow_offset), text, font=font, fill=glow_color)
        # ვხატავთ მთავარ ტექსტს ზემოდან
        draw.text(xy, text, font=font, fill=fill_color)


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

        # --- ახალი Welcome სურათი (Glow ეფექტით და პოზიციით) ---
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = member.guild.get_channel(channel_id)
            if channel:
                try:
                    W, H = (1000, 400) # სურათის ზომა

                    # ფონი: იასამნისფერ-შავი გრადიენტი + ვარსკვლავები (უცვლელი)
                    img = Image.new("RGBA", (W, H))
                    draw = ImageDraw.Draw(img)
                    start_color = (40, 0, 80); end_color = (0, 0, 0)
                    for i in range(H):
                        ratio = i / H; r = int(start_color[0]*(1-ratio)+end_color[0]*ratio); g = int(start_color[1]*(1-ratio)+end_color[1]*ratio); b = int(start_color[2]*(1-ratio)+end_color[2]*ratio)
                        draw.line([(0,i),(W,i)], fill=(r,g,b))
                    star_color = (255, 255, 255, 150)
                    for _ in range(100):
                        x=random.randint(0,W); y=random.randint(0,H); size=random.randint(1,3)
                        draw.ellipse([(x,y),(x+size,y+size)], fill=star_color)

                    # ავატარი (უცვლელი)
                    avatar_url = member.avatar.url; response = requests.get(avatar_url); avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                    AVATAR_SIZE = 200 # ოდნავ დავაპატარავოთ
                    avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                    avatar_pos = (70, (H // 2) - (AVATAR_SIZE // 2)) # პოზიცია მარცხნივ
                    img.paste(avatar_image, avatar_pos, mask)

                    # ტექსტის დამატება (ქართული ფონტით, Glow და ახალი პოზიცია)
                    draw = ImageDraw.Draw(img)
                    try:
                        font_regular = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 40) # გავზარდოთ ცოტა
                        font_bold = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 55) # გავზარდოთ ცოტა
                        font_server = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 35) # გავზარდოთ ცოტა
                    except IOError:
                        print("შეცდომა: Noto Sans Georgian ფონტები ვერ მოიძებნა!"); return # შევწყვიტოთ თუ ფონტი არაა

                    text_x = avatar_pos[0] + AVATAR_SIZE + 60 # ტექსტის X კოორდინატი (უფრო მარჯვნივ)

                    # ტექსტები
                    welcome_text = "მოგესალმებით"
                    user_name = member.name
                    if len(user_name) > 15: user_name = user_name[:12] + "..."
                    server_text = f"{member.guild.name} - ში!"

                    # ვათავსებთ ტექსტს ვერტიკალურად ცენტრში (ოდნავ ზემოთ)
                    current_y = H // 2 - 80 # დავიწყოთ უფრო ზემოდან

                    # ვიყენებთ ახალ ფუნქციას Glow ეფექტით
                    self.draw_text_with_glow(draw, (text_x, current_y), welcome_text, font_regular, fill_color=(200, 200, 200))
                    current_y += 60 # დაშორება
                    self.draw_text_with_glow(draw, (text_x, current_y), user_name, font_bold, fill_color=(255, 255, 255))
                    current_y += 60 # დაშორება
                    self.draw_text_with_glow(draw, (text_x, current_y), server_text, font_server, fill_color=(170, 170, 170)) # სერვერის სახელი უფრო მუქად

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
