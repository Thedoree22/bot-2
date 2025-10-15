import discord
from discord.ext import commands
import os

BOT_TOKEN = os.environ['BOT_TOKEN']

# --- ძალიან მნიშვნელოვანია! ---
# ამ ფუნქციებისთვის ბოტს სჭირდება წევრების სიის წაკითხვის უფლება
intents = discord.Intents.default()
intents.members = True # <<<<

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.load_extension('welcome_cog')
    await bot.load_extension('autorole_cog')
    await bot.load_extension('moderation_and_notify_cog') 
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
        
bot.run(BOT_TOKEN)
