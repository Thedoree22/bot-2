import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DB_FILE = "autorole_data.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AutoRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.autorole_data = load_data()

    # აქ არის შენთვის სასურველი აღწერა
    @app_commands.command(name="autorole-setup", description="Ayenebs rols")
    @app_commands.describe(role="Airchiet roli.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        guild_id = str(interaction.guild.id)
        
        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message("Shecdoma: Me ar shemidzlia am rolis minicheba, radgan is chemze maglaa!", ephemeral=True)
            return

        self.autorole_data[guild_id] = {"role_id": role.id}
        save_data(self.autorole_data)
        # აქ არის შენთვის სასურველი პასუხი
        await interaction.response.send_message(f"Avtomaturi roli dayenebulia **{role.name}**-ze!", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        
        if guild_id not in self.autorole_data:
            return

        role_id = self.autorole_data[guild_id].get("role_id")
        role = member.guild.get_role(role_id)

        if role:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"Error adding role on guild {member.guild.name}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRoleCog(bot))
