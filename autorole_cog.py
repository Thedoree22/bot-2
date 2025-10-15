import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DB_FILE = "autorole_data.json"

def load_data():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except json.JSONDecodeError: return {}

def save_data(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

class AutoRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.autorole_data = load_data()

    @app_commands.command(name="autorole-setup", description="Ayenebs rols")
    @app_commands.describe(role="Airchiet roli.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        guild_id = str(interaction.guild.id)
        
        if interaction.guild.me.top_role <=
