from telegram.ext import Application
import sqlite3
import asyncio
import logging
import time

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('kick_activity.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Bot token and group username
bot_token = 'YOUR_BOT_TOKEN_HERE'  # သင့်ရဲ့ Bot Token ထည့်ပါ
group_username = 'YOUR_GROUP_USERNAME_HERE'  # သင့်ရဲ့ Group Username ဒါမှမဟုတ် Chat ID ထည့်ပါ

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

async def manual_kick():
    logger.info("Starting manual kick process...")
    
    # Initialize Telegram bot
    logger.info("Initializing Telegram bot...")
    app = Application.builder().token(bot_token).build()
    
    try:
        # Connect to database
        conn = sqlite3.connect('group_activity.db')
        cursor = conn.cursor()
        logger.info("Connected to database successfully")
        
        # Get active users from database
        cursor.execute("SELECT user_id, last_active FROM members")
        active_members = {row[0]: row[1] for row in cursor.fetchall()}
        logger.info(f"Found {len(active_members)} users in database: {list(active_members.keys())}")
        
        # Get all group members
        all_members = []
        logger.info(f"Fetching all members from group {group_username}...")
        async for member in app.bot.get_chat_members(group_username):
            if rate_limit_check():
                user_id = member.user.id
                if not member.user.is_bot:  # Exclude bots
                    all_members.append(user_id)
            else:
                logger.warning("Rate limit reached while fetching members, stopping")
                break
        logger.info(f"Found {len(all_members)} members in group: {all_members}")
        
        # Determine inactive members
        three_days_ago = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time() - 3 * 24 * 60 * 60))
        inactive_members = []
        for user_id in all_members:
            if user_id not in active_members or active_members[user_id] < three_days_ago:
                inactive_members.append(user_id)
        logger.info(f"Found {len(inactive_members)} inactive members: {inactive_members}")
        
        # Kick inactive members (max 10)
        max_kicks = 10
        kicked_count = 0
        for user_id in inactive_members[:max_kicks]:
            if rate_limit_check():
                try:
                    await app.bot.ban_chat_member(group_username, user_id)
                    logger.info(f"Kicked user {user_id}")
                    kicked_count += 1
                except Exception as e:
                    logger.error(f"Failed to kick user {user_id}: {e}")
            else:
                logger.warning(f"Skipping kick for user {user_id} due to rate limit")
                break
        
        logger.info(f"Completed kicking {kicked_count} inactive members")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error in manual_kick: {e}")
    finally:
        await app.shutdown()

if __name__ == '__main__':
    logger.info("Running kick.py...")
    asyncio.run(manual_kick())
