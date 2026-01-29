import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
import os
from dotenv import load_dotenv
from db import SessionLocal
from models import Queue, QueueMember, User
import asyncio
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# Remove any non-alphanumeric characters if user pasted strangely, but keep dots/underscores
LFG_CHANNEL_ID = int(os.getenv("DISCORD_LFG_CHANNEL_ID"))
CATEGORY_ID = int(os.getenv("DISCORD_CATEGORY_ID"))

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True # Required for on_voice_state_update

bot = commands.Bot(command_prefix="!", intents=intents)

# ... (Previous code) ...

    try:
        q_update = db.query(Queue).filter_by(id=q.id).first()
        q_update.discord_channel_id = str(vc.id)
        db.commit()
        
        # Build Mentions
        mentions = " ".join([f"<@{m.discord_id}>" for m in q.members])
        
        # Notify
        await text_channel.send(
            f"✅ **Queue Full!** {mentions}\nVoice Channel Created: {vc.mention}",
            view=JoinVCView(vc.jump_url)
            # Removed delete_after so they see the ping
        )

# --- COMMANDS ---

@bot.tree.command(name="raid", description="Start a Raid Queue")
async def create_raid(interaction: discord.Interaction):
    view = RaidWizardView()
    await interaction.response.send_message("⚔️ **Setup Raid Queue:**", view=view, ephemeral=True)

@bot.tree.command(name="boss", description="Start a Boss Queue")
async def create_boss(interaction: discord.Interaction):
    # Boss list
    bosses = sorted([
        "Callisto", "Chaos Elemental", "Corporeal", "Dagannoth Kings", "Giant Mole",
        "Graardor", "Hueycoatl", "Kalphite Queen", "King Black Dragon", "Kree'arra", "K'ril",
        "Nex", "Nightmare", "Sarachnis", "Scorpia", "Scurrius", "Tempoross", "Venenatis",
        "Wintertodt", "Yama", "Zalcano", "Zilyana"
    ])
    view = BossWizardView(bosses)
    await interaction.response.send_message("👹 **Setup Boss Queue:**", view=view, ephemeral=True)

@bot.tree.command(name="link", description="Link your OSRS Username (RSN)")
@app_commands.describe(rsn="Your Old School Runescape Name")
async def link_rsn(interaction: discord.Interaction, rsn: str):
    discord_id = str(interaction.user.id)
    db = SessionLocal()
    try:
        # Check if exists
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if user:
            user.rsn = rsn
            msg = f"✅ Updated your RSN to: **{rsn}**"
        else:
            user = User(discord_id=discord_id, rsn=rsn)
            db.add(user)
            msg = f"✅ Linked RSN: **{rsn}**"
        
        db.commit()
        await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error linking RSN: {e}", ephemeral=True)
    finally:
        db.close()

@bot.command()
async def sync(ctx):
    try:
        # Syncs valid commands to the current guild (Instant)
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Synced {len(synced)} commands to this server!")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

@bot.command()
async def clearglobals(ctx):
    try:
        # Clears global commands to fix duplication
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync(guild=None)
        await ctx.send("✅ Cleared global commands! The duplicates should disappear shortly.")
    except Exception as e:
        await ctx.send(f"❌ Clear failed: {e}")

# --- WIZARD VIEWS (CONSOLIDATED) ---

class RaidWizardView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.activity = None
        self.role = None

    @discord.ui.select(placeholder="1. Choose Raid...", options=[
        discord.SelectOption(label="ToA", emoji="⚱️"),
        discord.SelectOption(label="ToB", emoji="🧛"),
        discord.SelectOption(label="CoX", emoji="🐉"),
    ], row=0)
    async def select_raid(self, interaction: discord.Interaction, select: Select):
        self.activity = select.values[0]
        await interaction.response.defer() # Acknowledge without sending message

    @discord.ui.select(placeholder="2. Choose Type/Role...", options=[
        discord.SelectOption(label="Learner", emoji="👶"),
        discord.SelectOption(label="Teacher", emoji="🎓"),
        discord.SelectOption(label="Casual", emoji="☕"),
        discord.SelectOption(label="Experienced", emoji="⚔️"),
        discord.SelectOption(label="Sweat", emoji="💦"),
        discord.SelectOption(label="Event", emoji="🎉"),
    ], row=1)
    async def select_role(self, interaction: discord.Interaction, select: Select):
        self.role = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Enter Details ->", style=discord.ButtonStyle.blurple, row=2)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if not self.activity or not self.role:
            await interaction.response.send_message("⚠️ Please select both an **Activity** and a **Role** first!", ephemeral=True)
            return
        await interaction.response.send_modal(QueueConfigModal(self.activity, self.role))

class BossWizardView(View):
    def __init__(self, bosses):
        super().__init__(timeout=180)
        self.activity = None
        self.role = None
        
        # Add Boss Select (Dynamic)
        options = [discord.SelectOption(label=b) for b in bosses]
        self.add_item(BossSelect(options))

    @discord.ui.select(placeholder="2. Choose Type/Role...", options=[
        discord.SelectOption(label="Learner", emoji="👶"),
        discord.SelectOption(label="Teacher", emoji="🎓"),
        discord.SelectOption(label="Casual", emoji="☕"),
        discord.SelectOption(label="Experienced", emoji="⚔️"),
        discord.SelectOption(label="Sweat", emoji="💦"),
        discord.SelectOption(label="Event", emoji="🎉"),
    ], row=1)
    async def select_role(self, interaction: discord.Interaction, select: Select):
        self.role = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Enter Details ->", style=discord.ButtonStyle.blurple, row=2)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if not self.activity or not self.role:
            await interaction.response.send_message("⚠️ Please select both a **Boss** and a **Role** first!", ephemeral=True)
            return
        await interaction.response.send_modal(QueueConfigModal(self.activity, self.role))

class BossSelect(Select):
    def __init__(self, options):
        super().__init__(placeholder="1. Choose Boss...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.activity = self.values[0]
        await interaction.response.defer()

# --- CONFIG MODAL ---

class QueueConfigModal(Modal):
    def __init__(self, activity, role):
        super().__init__(title=f"Configure {activity}")
        self.activity = activity
        self.role = role

    size = TextInput(label="Group Size (2-100)", placeholder="Total people including you", default="3", min_length=1, max_length=3)
    expires = TextInput(label="Expire After (Minutes)", placeholder="Max 180, Intervals of 5", default="60", min_length=1, max_length=3)
    notes = TextInput(label="Notes (Optional)", placeholder="e.g. 300 invo, split...", style=discord.TextStyle.paragraph, required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        db = SessionLocal()
        try:
            # 1. Check RSN Link
            user = db.query(User).filter_by(discord_id=discord_id).first()
            if not user:
                await interaction.response.send_message(
                    "❌ You must link your RSN first!\nUse `/link [rsn]` here in Discord, or visit https://bosscape.com/link", 
                    ephemeral=True
                )
                return

            # 2. Validate Inputs
            try:
                g_size = int(self.size.value)
                exp_mins = int(self.expires.value)
            except ValueError:
                await interaction.response.send_message("❌ Size and Expiry must be numbers.", ephemeral=True)
                return

            if g_size < 2 or g_size > 100:
                await interaction.response.send_message("❌ Group size must be between 2 and 100.", ephemeral=True)
                return

            if exp_mins > 180:
                await interaction.response.send_message("❌ Expiration cannot exceed 180 minutes.", ephemeral=True)
                return
            
            if exp_mins % 5 != 0:
                await interaction.response.send_message("❌ Expiration must be in intervals of 5 (e.g., 30, 35, 60).", ephemeral=True)
                return

            # 3. Create Queue
            expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=exp_mins)
            
            queue = Queue(
                boss=self.activity,
                role=self.role,
                group_size=g_size,
                created_by=discord_id,
                description=self.notes.value,
                expires_at=expires_at
            )
            db.add(queue)
            db.commit()

            member = QueueMember(queue_id=queue.id, discord_id=discord_id, rsn=user.rsn)
            db.add(member)
            db.commit()

            await interaction.response.send_message(f"✅ Queue created for **{self.activity}** ({self.role})!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        finally:
            db.close()

# --- VIEW FOR BUTTONS ---
class QueueView(View):
    def __init__(self, queue_id):
        super().__init__(timeout=None)
        self.queue_id = queue_id

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="join_queue")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        await handle_join(interaction, self.queue_id)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="leave_queue")
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        await handle_leave(interaction, self.queue_id)

class JoinVCView(View):
    def __init__(self, url):
        super().__init__(timeout=None)
        self.add_item(Button(label="🔊 Join Voice Channel", url=url))

# --- HELPER: ARCHIVE QUEUE ---
async def archive_queue(q: Queue, reason: str = "Finished"):
    channel = bot.get_channel(LFG_CHANNEL_ID)
    archive_channel = bot.get_channel(int(os.getenv("DISCORD_ARCHIVE_CHANNEL_ID", 0)))
    
    # Delete from active
    if q.discord_message_id and channel:
        try:
            msg = await channel.fetch_message(int(q.discord_message_id))
            await msg.delete()
        except:
            pass

    # Post to Archive
    if archive_channel:
        try:
            embed = build_embed(q)
            embed.title = f"[{reason}] {embed.title}"
            embed.color = discord.Color.dark_grey()
            # Calculate end time properly
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            embed.set_footer(text=f"Ended at {now_naive.strftime('%H:%M UTC')} | ID: {q.id}")
            await archive_channel.send(embed=embed)
        except Exception as e:
            print(f"Archive Error: {e}")

    # Delete from DB
    db = SessionLocal()
    try:
        # Re-fetch to ensure attached
        to_del = db.query(Queue).filter_by(id=q.id).first()
        if to_del:
            db.delete(to_del)
            db.commit()
    finally:
        db.close()

# --- EVENT HANDLERS ---

async def handle_join(interaction: discord.Interaction, queue_id: int):
    discord_id = str(interaction.user.id)
    db = SessionLocal()
    try:
        # Check RSN link
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            await interaction.response.send_message(
                "❌ You must link your RSN first!\nUse `/link [rsn]` here in Discord, or visit https://bosscape.com/link", 
                ephemeral=True
            )
            return

        queue = db.query(Queue).filter_by(id=queue_id).first()
        if not queue:
            await interaction.response.send_message("❌ Queue not found (it may have expired).", ephemeral=True)
            return

        # Check existing
        if any(m.discord_id == discord_id for m in queue.members):
            await interaction.response.send_message("⚠️ You are already in this queue.", ephemeral=True)
            return

        # Check full
        if len(queue.members) >= queue.group_size:
            await interaction.response.send_message("❌ Queue is full.", ephemeral=True)
            return

        # Add member
        new_member = QueueMember(queue_id=queue.id, discord_id=discord_id, rsn=user.rsn)
        db.add(new_member)
        db.commit()
        await interaction.response.send_message(f"✅ Joined **{queue.boss}** queue!", ephemeral=True)
        
        # Trigger update immediately
        await update_queue_message(queue.id)

    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)
    finally:
        db.close()

async def handle_leave(interaction: discord.Interaction, queue_id: int):
    discord_id = str(interaction.user.id)
    db = SessionLocal()
    try:
        queue = db.query(Queue).filter_by(id=queue_id).first()
        if not queue:
            await interaction.response.send_message("⚠️ Queue not found.", ephemeral=True)
            return

        # 1. CHECK IF HOST
        if str(queue.created_by) == discord_id:
            await interaction.response.send_message("🛑 **Host Left:** Disbanding Queue...", ephemeral=True)
            db.close() # Close session before async call might be cleaner
            await archive_queue(queue, "Disbanded by Host")
            return

        # 2. NORMAL MEMBER LEAVE
        member = db.query(QueueMember).filter_by(queue_id=queue_id, discord_id=discord_id).first()
        if member:
            db.delete(member)
            db.commit()
            await interaction.response.send_message("👋 Left the queue.", ephemeral=True)
            await update_queue_message(queue_id)
        else:
            await interaction.response.send_message("⚠️ You are not in this queue.", ephemeral=True)
    finally:
        # Only close if not already closed
        pass
    db.close() # Ensuring closure

# --- AUTO-DELETE VOICE CHANNELS ---
@bot.event
async def on_voice_state_update(member, before, after):
    # If user left a channel
    if before.channel:
        # Check if it is in our category
        if before.channel.category_id == CATEGORY_ID:
            # Check if empty (0 members)
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                except Exception as e:
                    print(f"Error deleting empty VC: {e}")

# --- SYNC LOOP ---

@tasks.loop(seconds=5)
async def sync_queues():
    await bot.wait_until_ready()
    channel = bot.get_channel(LFG_CHANNEL_ID)
    
    if not channel:
        print(f"Error: LFG Channel {LFG_CHANNEL_ID} not found.")
        return

    db = SessionLocal()
    try:
        # DB stores naive UTC, so we must compare with naive UTC
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # 1. PROCESS ACTIVE QUEUES
        active_queues = db.query(Queue).filter(Queue.expires_at > now_naive).all()
        
        for q in active_queues:
            # Update Message
            embed = build_embed(q)
            view = QueueView(q.id)
            
            if q.discord_message_id:
                try:
                    msg = await channel.fetch_message(int(q.discord_message_id))
                    await msg.edit(embed=embed, view=view)
                except discord.NotFound:
                    # Message deleted manually? Re-post
                    msg = await channel.send(embed=embed, view=view)
                    q.discord_message_id = str(msg.id)
                    db.commit()
            else:
                # New Queue
                msg = await channel.send(embed=embed, view=view)
                q.discord_message_id = str(msg.id)
                db.commit()

            # Check Voice Channel (Full Team)
            if len(q.members) >= q.group_size:
                if not q.discord_channel_id:
                    await create_voice_channel(q, channel)

        # 2. PROCESS EXPIRED QUEUES (Cleanup)
        # Use Helper
        expired_queues = db.query(Queue).filter(Queue.expires_at <= now_naive).all()
        for q in expired_queues:
            # We must close this DB session's query or just use the IDs, 
            # because `archive_queue` creates a new session. 
            # Actually, `archive_queue` works on ID logic so it's fine.
            # But the object `q` is bound to `db`.
            await archive_queue(q)
        
    except Exception as e:
        print(f"Sync Loop Error: {e}")
    finally:
        db.close()

def build_embed(q: Queue):
    is_full = len(q.members) >= q.group_size
    color = discord.Color.green() if not is_full else discord.Color.red()
    
    embed = discord.Embed(title=f"{q.boss} ({q.role})", color=color)
    embed.add_field(name="Host", value=q.members[0].rsn if q.members else "Unknown", inline=True)
    embed.add_field(name="Size", value=f"{len(q.members)} / {q.group_size}", inline=True)
    
    if q.description:
        embed.add_field(name="Note", value=q.description, inline=False)
        
    member_list = "\n".join([f"• {m.rsn}" for m in q.members])
    embed.add_field(name="Members", value=member_list if member_list else "None", inline=False)
    
    # Calculate expiry using naive UTC math
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_in = int((q.expires_at - now_naive).total_seconds() / 60)
    embed.set_footer(text=f"Expires in {expires_in} mins | ID: {q.id}")
    
    return embed

async def create_voice_channel(q: Queue, text_channel):
    guild = text_channel.guild
    category = discord.utils.get(guild.categories, id=CATEGORY_ID)
    
    if not category:
        print("Category not found")
        return

    # Create VC
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=False),
        guild.me: discord.PermissionOverwrite(connect=True)
    }
    
    # Allow members
    channel_name = f"{q.boss} - Team {q.id}"
    vc = await guild.create_voice_channel(channel_name, category=category)
    
    db = SessionLocal()
    try:
        q_update = db.query(Queue).filter_by(id=q.id).first()
        q_update.discord_channel_id = str(vc.id)
        db.commit()
        
        # Build Mentions
        mentions = " ".join([f"<@{m.discord_id}>" for m in q.members])
        
        # Notify
        await text_channel.send(
            f"✅ **Queue Full!** {mentions}\nVoice Channel Created: {vc.mention}",
            view=JoinVCView(vc.jump_url)
        )
        
    except Exception as e:
        print(f"VC Create Error: {e}")
    finally:
        db.close()

# --- UPDATE HELPER ---
async def update_queue_message(queue_id):
    # Triggers the loop logic immediately/forcefully or waits for next cycle
    # Since loop runs every 5s, we can just wait.
    pass

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    sync_queues.start()

if __name__ == "__main__":
    bot.run(TOKEN)
