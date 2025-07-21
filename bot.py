from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.events import NewMessage
from datetime import datetime, timedelta
import sqlite3
import schedule
import time
import logging

# Logging အတွက် ပြင်ဆင်မှု
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_activity.log'),  # Log file ထဲမှာ သိမ်းမယ်
        logging.StreamHandler()  # Console မှာလည်း ပြမယ်
    ]
)
logger = logging.getLogger(__name__)

# Telegram API အတွက် လိုအပ်တဲ့ အချက်အလက်များ
api_id = 'YOUR_API_ID'  # [my.telegram.org] ကနေ ရယူပါ
api_hash = 'YOUR_API_HASH'  # [my.telegram.org] ကနေ ရယူပါ
bot_token = 'YOUR_BOT_TOKEN'  # @BotFather ကနေ ရယူပါ
group_username = 'your_group_username'  # သင့်ဂရုပ်ရဲ့ username (ဥပမာ: @YourGroup)

# Database ဖန်တီးပြီး ချိတ်ဆက်ပါ
conn = sqlite3.connect('group_activity.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, last_active TEXT)''')
conn.commit()

# Telegram Client စတင်ပါ
client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# Status Command အတွက်
@client.on(NewMessage(pattern='/status'))
async def status(event):
    logger.info(f"Status command received from {event.sender_id}")
    await event.respond("Bot က အလုပ်လုပ်နေပါတယ်! Database ထဲမှာ active members တွေကို မှတ်တမ်းတင်နေပြီး inactive members တွေကို နေ့စဉ် kick လုပ်နေပါတယ်။")
    logger.info("Status response sent")

async def update_member_activity():
    logger.info("Starting to update member activity...")
    async with client:
        # နောက်ဆုံး ၇ ရက်အတွင်းရဲ့ ရက်စွဲအပိုင်းအခြားကို သတ်မှတ်ပါ
        today = datetime.now()
        start_of_period = today - timedelta(days=7)  # နောက်ဆုံး ၇ ရက်
        end_of_period = today + timedelta(days=1)  # ဒီနေ့အထိ

        # နောက်ဆုံး ၇ ရက်အတွင်းရဲ့ မက်ဆေ့ချ်တွေကို ရယူပါ
        messages = []
        offset_id = 0
        while True:
            history = await client(GetHistoryRequest(
                peer=group_username,
                limit=100,
                offset_id=offset_id,
                offset_date=end_of_period,
                add_offset=0,
                max_id=0,
                min_id=0,
                hash=0
            ))
            if not history.messages:
                break
            for message in history.messages:
                if message.date >= start_of_period:
                    messages.append(message)
                else:
                    break
            offset_id = history.messages[-1].id
            if not history.messages[-1].date >= start_of_period:
                break

        # မက်ဆေ့ချ်ပို့တဲ့သူတွေရဲ့ အချက်အလက်ကို သိမ်းပါ
        for message in messages:
            if message.from_id:
                user_id = message.from_id.user_id
                last_active = datetime.now().isoformat()
                cursor.execute('INSERT OR REPLACE INTO members (user_id, last_active) VALUES (?, ?)',
                              (user_id, last_active))
                logger.info(f"Recorded activity for user {user_id}")
        conn.commit()
        logger.info(f"Updated {len(messages)} messages in database")

async def kick_inactive_members():
    kicked_count = 0  # တစ်နေ့မှာ kick လုပ်တဲ့ အရေအတွက်
    max_kicks_per_day = 10  # တစ်နေ့ကို အများဆုံး ၁၀ ယောက်
    logger.info("Starting to kick inactive members...")

    async with client:
        async for user in client.iter_participants(group_username):
            if kicked_count >= max_kicks_per_day:
                logger.info(f"Reached daily kick limit of {max_kicks_per_day}")
                break

            user_id = user.id
            cursor.execute('SELECT last_active FROM members WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            if result is None:
                try:
                    await client.kick_participant(group_username, user_id)
                    logger.info(f"Kicked user {user_id} from group")
                    kicked_count += 1
                except Exception as e:
                    logger.error(f"Failed to kick user {user_id}: {e}")
            else:
                logger.info(f"User {user_id} is active, not kicked")
        logger.info(f"Kicked {kicked_count} inactive members today")

# တစ်နေ့တစ်ကြိမ် run ဖို့ scheduling လုဪပါ
def job():
    logger.info("Running scheduled job...")
    client.loop.run_until_complete(update_member_activity())
    client.loop.run_until_complete(kick_inactive_members())
    logger.info("Scheduled job completed")

# နေ့စဉ် သတ်မှတ်ထားတဲ့ အချိန်မှာ run ဖို့ schedule သတ်မှတ်ပါ
schedule.every().day.at("00:00").do(job)

# Bot ကို စတင်ပါ
logger.info("Starting bot...")
with client:
    client.run_until_disconnected()
