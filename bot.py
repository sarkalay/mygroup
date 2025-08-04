from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from datetime import datetime, timedelta
import sqlite3
import schedule
import asyncio
import logging
import random
import time

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot_activity.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Bot token and group username
bot_token = ''
group_username = ''  # Replace with correct group username or ID

# Database setup
conn = sqlite3.connect('group_activity.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, last_active TEXT)''')
conn.commit()

# Rate limiting variables
REQUESTS_PER_MINUTE = 20
request_timestamps = []

# Rate limiting check
def rate_limit_check():
    global request_timestamps
    now = time.time()
    request_timestamps = [t for t in request_timestamps if now - t < 60]
    if len(request_timestamps) >= REQUESTS_PER_MINUTE:
        logger.warning("Rate limit reached, waiting...")
        return False
    request_timestamps.append(now)
    return True

# Status command
async def status(update: Update, context):
    logger.info(f"Status command received from {update.effective_user.id}")
    await update.message.reply_text("Bot က အလုပ်လုပ်နေပါတယ်! Active member တွေကို တစ်ရက်တစ်ခါ မှတ်တမ်းတင်ပြီး ၃ ရက်အတွင်း active မဖြစ်တဲ့သူတွေကို kick လုပ်နေပါတယ်။")
    logger.info("Status response sent")

# Track new messages (only one message per user per day)
async def track_message(update: Update, context):
    if update.effective_chat.username == group_username.lstrip('@'):
        if rate_limit_check():
            try:
                user_id = update.effective_user.id
                today = datetime.now().date()
                
                # Check if user already has an entry for today
                cursor.execute('SELECT last_active FROM members WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                
                if result:
                    last_active = datetime.fromisoformat(result[0]).date()
                    if last_active == today:
                        logger.info(f"User {user_id} already recorded today, skipping")
                        return
                
                # Update or insert new activity
                last_active = datetime.now().isoformat()
                cursor.execute('INSERT OR REPLACE INTO members (user_id, last_active) VALUES (?, ?)',
                              (user_id, last_active))
                conn.commit()
                logger.info(f"Recorded activity for user {user_id}")
            except Exception as e:
                logger.error(f"Error in track_message: {e}")
        else:
            logger.warning(f"Skipping message processing for user {update.effective_user.id} due to rate limit")

# Kick inactive members (random 10 per day)
async def kick_inactive_members():
    kicked_count = 0
    max_kicks_per_day = 10
    logger.info("Starting to kick inactive members...")

    # Get current time and 3-day threshold
    now = datetime.now()
    three_days_ago = now - timedelta(days=3)

    # Get all group members
    async with Application.builder().token(bot_token).build() as app:
        try:
            # Get all members who are not active in the last 3 days
            cursor.execute('SELECT user_id, last_active FROM members')
            active_members = {row[0]: datetime.fromisoformat(row[1]) for row in cursor.fetchall()}
            
            inactive_members = []
            async for member in app.bot.get_chat_members(group_username):
                if rate_limit_check():
                    user_id = member.user.id
                    if user_id not in active_members or active_members[user_id] < three_days_ago:
                        inactive_members.append(user_id)
                else:
                    logger.warning("Rate limit reached while fetching members, stopping")
                    break

            # Randomly select up to 10 inactive members
            random.shuffle(inactive_members)
            members_to_kick = inactive_members[:max_kicks_per_day]

            # Kick selected members
            for user_id in members_to_kick:
                if rate_limit_check():
                    try:
                        await app.bot.ban_chat_member(group_username, user_id)
                        logger.info(f"Kicked user {user_id} from group")
                        kicked_count += 1
                    except Exception as e:
                        logger.error(f"Failed to kick user {user_id}: {e}")
                else:
                    logger.warning(f"Skipping kick for user {user_id} due to rate limit")
                    break

            logger.info(f"Kicked {kicked_count} inactive members today")
        except Exception as e:
            logger.error(f"Error in kick_inactive_members: {e}")

# Scheduling job
def job():
    logger.info("Running scheduled job...")
    asyncio.run(kick_inactive_members())
    logger.info("Scheduled job completed")

# Schedule daily at 00:00
schedule.every().day.at("00:00").do(job)

async def main():
    try:
        app = Application.builder().token(bot_token).build()
        app.add_handler(CommandHandler("status", status))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_message))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        # Run schedule loop
        while True:
            schedule.run_pending()
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == '__main__':
    logger.info("Starting bot...")
    asyncio.run(main())
