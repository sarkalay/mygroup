from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from datetime import datetime, timedelta
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_id = '22136894'  # Your api_id
api_hash = '533292888f971c49edd6f38cbeb6ca54'  # Your api_hash
bot_token = '8071347840:AAEWf0tZvJlbZbt1NWYuR78ADLlj8T__KVU'  # Your bot_token
group_username = '@airdropbombnode'  # Replace with correct group username or ID

conn = sqlite3.connect('group_activity.db')
cursor = conn.cursor()

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

async def test_update_member_activity():
    logger.info("Testing update member activity...")
    today = datetime.now()
    start_of_period = today - timedelta(days=3)
    end_of_period = today + timedelta(days=1)

    messages = []
    offset_id = 0
    async with client:
        while True:
            logger.info(f"Fetching messages with offset_id {offset_id}")
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
                logger.info("No more messages to fetch")
                break
            for message in history.messages:
                if message.date >= start_of_period:
                    messages.append(message)
                else:
                    break
            offset_id = history.messages[-1].id
            if not history.messages[-1].date >= start_of_period:
                logger.info("Reached messages older than 3 days")
                break

    logger.info(f"Found {len(messages)} messages in the last 3 days")
    for message in messages:
        if message.from_id:
            user_id = message.from_id.user_id
            last_active = datetime.now().isoformat()
            cursor.execute('INSERT OR REPLACE INTO members (user_id, last_active) VALUES (?, ?)',
                          (user_id, last_active))
            logger.info(f"Recorded activity for user {user_id}")
    conn.commit()
    logger.info("Finished testing update member activity")

with client:
    client.loop.run_until_complete(test_update_member_activity())
