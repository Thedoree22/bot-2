import discord
from discord.ext import commands
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if BOT_TOKEN is None:
    print("ფატალური შეცდომა: BOT_TOKEN არ არის Railway-ს ცვლადებში.")
    exit()

# --- ბოტის უფლებები (Intents) ---
intents = discord.Intents.default()
intents.members = True       # aucilebelia Welcome da Auto-Role-istvis
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"ბოტი ჩაირთო როგორც {bot.user}")
    print("-" * 30)
    
    # --- ყველა ფუნქციის (Cogs) ჩატვირთვა ---
    cogs_to_load = [
        'utility_cog',        # aq aris Clear da Giveaway
        'community_cog',      # aq aris Welcome da Auto-Role
        'youtube_cog'         # aq aris YouTube shetyobinebebi
    ]
    
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"წარმატებით ჩაიტვირთა: {cog}")
        except Exception as e:
            print(f"შეცდომა: ვერ ჩაიტვირთა {cog}: {e}")

    print("-" * 30)

    # --- სლეშ ბრძანებების რეგისტრაცია ---
    try:
        synced = await bot.tree.sync()
        print(f"წარმატებით დარეგისტრირდა {len(synced)} ბრძანება.")
    except Exception as e:
        print(f"შეცდომა ბრძანებების რეგისტრაციისას: {e}")
    
    print("-" * 30)

bot.run(BOT_TOKEN)
