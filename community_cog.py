import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
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

    # --- ტექსტის დახატვის დამხმარე ფუნქცია Shadow ეფექტით ---
    def draw_text_with_shadow(self, draw, xy, text, font, fill_color, shadow_color=(0, 0, 0, 150), shadow_offset=(2, 2)):
        x, y = xy; sx, sy = shadow_offset
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_color) # Shadow
        draw.text(xy, text, font=font, fill=fill_color) # Main text

    # --- Welcome სურათის გენერირების ფუნქცია ---
    # (გამოვიტანეთ ცალკე ფუნქციად, რომ ტესტმაც გამოიყენოს)
    async def create_welcome_image(self, member_name: str, guild_name: str, avatar_url: Optional[str] = None) -> Optional[discord.File]:
        try:
            W, H = (1000, 400) # სურათის ზომა

            # ფონი: იასამნისფერ-შავი გრადიენტი + ვარსკვლავები
            img = Image.new("RGBA", (W, H)); draw = ImageDraw.Draw(img)
            start_color = (40, 0, 80); end_color = (0, 0, 0)
            for i in range(H):
                ratio=i/H; r=int(start_color[0]*(1-ratio)+end_color[0]*ratio); g=int(start_color[1]*(1-ratio)+end_color[1]*ratio); b=int(start_color[2]*(1-ratio)+end_color[2]*ratio)
                draw.line([(0,i),(W,i)], fill=(r,g,b))
            star_color = (255, 255, 255, 150)
            for _ in range(100):
                x=random.randint(0,W); y=random.randint(0,H); size=random.randint(1,3)
                draw.ellipse([(x,y),(x+size,y+size)], fill=star_color)

            # ავატარი
            AVATAR_SIZE = 180
            avatar_pos = (80, (H // 2) - (AVATAR_SIZE // 2)) # პოზიცია მარცხნივ

            if avatar_url: # თუ ავატარის ლინკი მოგვაწოდეს (ნამდვილი წევრი)
                response = requests.get(avatar_url); avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                img.paste(avatar_image, avatar_pos, mask)
            else: # თუ ავატარი არ არის (ტესტისთვის)
                # ვხატავთ ცარიელ წრეს
                draw.ellipse([avatar_pos, (avatar_pos[0]+AVATAR_SIZE, avatar_pos[1]+AVATAR_SIZE)], outline="grey", width=3)

            # ტექსტის დამატება
            draw = ImageDraw.Draw(img)
            try:
                font_regular = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 50)
                font_bold = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 65) # სახელი
                font_server = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 40)
            except IOError:
                print("შეცდომა: Noto Sans Georgian ფონტები ვერ მოიძებნა!"); return None # ვბრუნდებით None, თუ ფონტი არაა

            text_x = avatar_pos[0] + AVATAR_SIZE + 50 # ტექსტის X კოორდინატი

            # ტექსტები
            welcome_text = "მოგესალმებით"
            user_name = member_name
            if len(user_name) > 18: user_name = user_name[:15] + "..."
            server_text = f"{guild_name} - ში!"

            line_height_multiplier = 1.3
            total_text_height = (font_regular.getbbox(welcome_text)[3] - font_regular.getbbox(welcome_text)[1]) + \
                                (font_bold.getbbox(user_name)[3] - font_bold.getbbox(user_name)[1]) + \
                                (font_server.getbbox(server_text)[3] - font_server.getbbox(server_text)[1]) + \
                                (font_regular.size * line_height_multiplier * 0.5) * 2

            current_y = (H // 2) - (total_text_height // 2)

            self.draw_text_with_shadow(draw, (text_x, current_y), welcome_text, font_regular, fill_color=(220, 220, 220))
            current_y += int(font_regular.size * line_height_multiplier)
            self.draw_text_with_shadow(draw, (text_x, current_y), user_name, font_bold, fill_color=(255, 255, 255))
            current_y += int(font_bold.size * line_height_multiplier)
            self.draw_text_with_shadow(draw, (text_x, current_y), server_text, font_server, fill_color=(180, 180, 180))

            # სურათის შენახვა
            final_buffer = io.BytesIO()
            img.save(final_buffer, "PNG")
            final_buffer.seek(0)
            return discord.File(fp=final_buffer, filename="welcome_test.png")
        except Exception as e:
            print(f"Error creating welcome image: {e}")
            return None # ვბრუნდებით None, თუ რამე შეცდომა მოხდა

    # --- Welcome ჯგუფი ---
    welcome_group = app_commands.Group(name="welcome", description="Misalmebis sistemis martva")

    @welcome_group.command(name="setup", description="აყენებს მისალმების არხს")
    @app_commands.describe(channel="აირჩიე არხი სადაც მოხდება მისალმება")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(WELCOME_DB); data[str(interaction.guild.id)] = {"channel_id": channel.id}; save_data(data, WELCOME_DB)
        await interaction.response.send_message(f"მისალმების არხი არის {channel.mention}", ephemeral=True)

    # --- ახალი ტესტ ბრძანება ---
    @welcome_group.command(name="test", description="Agzavnis test misalmebis surats am arkhshi")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True) # ბოტს ვაძლევთ დროს სურათის შესაქმნელად
        
        # ვიძახებთ სურათის გენერირების ფუნქციას ტესტ მონაცემებით
        test_file = await self.create_welcome_image(
            member_name="Testing",
            guild_name=interaction.guild.name, # ვიღებთ მიმდინარე სერვერის სახელს
            avatar_url=None # არ ვაწვდით ავატარს
        )
        
        if test_file:
            await interaction.followup.send("⚠️ **ტესტ შეტყობინება:**", file=test_file)
        else:
            await interaction.followup.send("შეცდომა ტესტ სურათის შექმნისას. შეამოწმე ფონტები ატვირთულია თუ არა.", ephemeral=True)


    # --- AutoRole Setup (უცვლელი) ---
    @app_commands.command(name="autorole", description="აყენებს როლს რომელიც ავტომატურად მიენიჭება")
    @app_commands.describe(role="აირჩიე როლი რომ მიენიჭოს")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message("მე არ შემიძლია ამ როლის მინიჭება მიუთითე ჩემს როლზე დაბალი როლი", ephemeral=True); return
        data = load_data(AUTOROLE_DB); data[str(interaction.guild.id)] = {"role_id": role.id}; save_data(data, AUTOROLE_DB)
        await interaction.response.send_message(f"ავტო როლი არის **{role.name}**", ephemeral=True)

    # --- on_member_join ივენთი (ახლა იყენებს გენერირების ფუნქციას) ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        # როლის მინიჭება
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id"); role = member.guild.get_role(role_id)
            if role:
                try: await member.add_roles(role)
                except Exception as e: print(f"Error adding role: {e}")

        # მისალმების გაგზავნა
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id")
            channel = member.guild.get_channel(channel_id)
            if channel:
                # ვიძახებთ სურათის გენერირების ფუნქციას ნამდვილი მონაცემებით
                welcome_file = await self.create_welcome_image(
                    member_name=member.name,
                    guild_name=member.guild.name,
                    avatar_url=member.avatar.url
                )
                if welcome_file:
                    await channel.send(f"შემოგვიერთდა {member.mention} გთხოვ გაერთო", file=welcome_file)
                else: # თუ სურათი ვერ შეიქმნა
                    await channel.send(f"შემოგვიერთდა {member.mention} გთხოვ გაერთო")

async def setup(bot: commands.Cog):
    await bot.add_cog(CommunityCog(bot))
