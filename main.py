import nextcord, os, re, sqlite3
from nextcord import Interaction
from nextcord.ext import commands
from dotenv import load_dotenv
from random import randint

load_dotenv()
open("history_log", "a").close()

activity = nextcord.Activity(type=nextcord.ActivityType.watching, name="#bookworm-memes")
intents = nextcord.Intents.all()
client = nextcord.Client(intents=intents, activity=activity)

filter_channel_id = int(os.getenv('TARGET'))
log_channel_id = int(os.getenv('LOG'))

conn = sqlite3.connect("bot.sqlite3")
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS threads (
    user_id integer,
    thread_id integer
)""")

async def doLog(content):
    print(content)
    f = open("history_log", "a")
    f.write(f"{content}\n")
    f.close()
    log_channel = await client.fetch_channel(log_channel_id)
    await log_channel.send(content=content)
    return 0 

@client.event
async def on_application_command_error(ctx, error):
    error = getattr(error, "original", error)
    raise error
    await doLog(error)

class renameModal(nextcord.ui.Modal):
    def __init__(self, thread):
        super().__init__("Rename Thread")
        self.thread = thread

        self.set_name = nextcord.ui.TextInput(label="Thread Name:", min_length=1, max_length=100, required=True, style=nextcord.TextInputStyle.short)
        self.add_item(self.set_name)

    async def callback(self, interaction:Interaction) -> None:
        set_name = self.set_name.value
        await self.thread.edit(name=set_name)
        await doLog(f"Thread ({self.thread.id}) renamed by {interaction.user.name}")
        return 0

class renameThread(nextcord.ui.Button):
    def __init__(self, thread, caller):
        super().__init__(emoji="📝", style=nextcord.ButtonStyle.blurple)
        self.thread = thread
        self.caller = caller

    async def callback(self, interaction:Interaction):
        if self.caller == interaction.user.id:
            await interaction.response.send_modal(renameModal(self.thread))
        else:
            await interaction.response.send_message(f"Only <@{self.caller}> may do this.", ephemeral=True)

class rejectThread(nextcord.ui.Button):
    def __init__(self, thread, caller):
        super().__init__(emoji="🚮", style=nextcord.ButtonStyle.red)
        self.thread = thread
        self.caller = caller
    
    async def callback(self, interaction:Interaction):
        if self.caller == interaction.user.id:
            await self.thread.delete()
            await doLog(f"Thread ({self.thread.id}) deleted by {interaction.user.name}")
        else:
            await interaction.response.send_message(f"Only <@{self.caller}> may do this.", ephemeral=True)

class threadView(nextcord.ui.View):
    def __init__(self, thread, caller):
        super().__init__(timeout=600)
        self.add_item(rejectThread(thread, caller))
        self.add_item(renameThread(thread, caller))
    async def on_error(self, error, item, interaction):
        await doLog(error)
        await doLog(item)

@client.event
async def on_ready():
    print("Bot ready")

url_regex = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"

@client.event
async def on_message(message):
    if message.channel.id == filter_channel_id:
        if message.attachments or re.search(url_regex, message.content):
            thread = await message.create_thread(name=f"{message.author.name}'s meme discussion")
            embed = nextcord.Embed(title="Edit thread?", description="Use 🚮 button to delete it\n *or*\nUse 📝 button to rename it.", color=randint(0,16777215))
            embed.set_footer(text="This will only be valid for the first 10 minutes. To rename the thread afterwards use /rename instead.")
            await thread.send(embed=embed, view=threadView(thread, message.author.id), delete_after=600)
            await thread.leave()
            sql = "INSERT INTO threads (user_id, thread_id) VALUES (?, ?)"
            val = (message.author.id, thread.id)
            c.execute(sql,val)
            conn.commit()
            await doLog(f"Thread auto-generated by {message.author.name}")
        elif message.author.guild_permissions.manage_channels:
            pass
            await doLog(f"Message passed ({message.author.name})")
        else:
            try:
                await message.author.send(f"In order to keep {message.channel.mention} as organized as possible, it is only possible to discuss memes via threads.")
            except:
                await message.channel.send(f"{message.author.mention}\nIn order to keep {message.channel.mention} as organized as possible, it is only possible to discuss memes via threads.", delete_after=30)
            await doLog(f"Deleted message from {message.author.name}")
            await message.delete()

@client.slash_command(description="Renames a meme discussion thread (in #bookworm-memes) you started.")
async def rename(interaction:Interaction):
    try:
        thread_id = c.execute(f"SELECT thread_id FROM threads WHERE thread_id = {interaction.channel.id}").fetchone()[0]
        user_id = c.execute(f"SELECT user_id FROM threads WHERE thread_id = {thread_id}").fetchone()[0]
    except:
        thread_id = None
        user_id = None
    if interaction.channel.id == thread_id and interaction.user.id == user_id:
        thread = await client.fetch_channel(thread_id)
        await interaction.response.send_modal(renameModal(thread))
    else:
        await interaction.response.send_message("This channel is either not a thread, not a registered thread or you don't own this thread.", ephemeral=True)

@client.slash_command(description="Check bot status and latency.")
async def stats(interaction:Interaction):
    for x in os.getenv('BOTS').split(','):
        permit = True if interaction.channel.id == int(x) else False
        if permit:
            embed = nextcord.Embed(title=f"{client.user.name} Stats", description=f"-status: {client.status}\n-latency: {client.latency}\n-user: {client.user.mention}", color=randint(0x0,0xffffff))
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("This command is only possible in the valid bots channels.", ephemeral=True)

client.run(os.getenv('TOKEN'))


