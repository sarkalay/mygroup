from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from datetime import datetime, timedelta
import sqlite3
import schedule
import time

# Telegram API အတွက် လိုအပ်တဲ့ အချက်အလက်များ
api_id = 'YOUR_API_ID'  # BotFather ကနေ ရယူပါ
api_hash = 'YOUR_API_HASH'  # BotFather ကနေ ရယူပါ
bot_token = 'YOUR_BOT_TOKEN'  # BotFather ကနေ ရယူပါ
group_username = 'your_group_username'  # သင့်ဂရုပ်ရဲ့ username (ဥပမာ: @YourGroup)

# Database ဖန်တီးပြီး ချိတ်ဆက်ပါ
conn = sqlite3.connect('group_activity.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, last_active TEXT)''')
conn.commit()

# Telegram Client စတင်ပါ
client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

async def update_member_activity():
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
                limit=500,  
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
            if message.from_id:  # မက်ဆေ့ချ်ပို့သူရဲ့ ID
                user_id = message.from_id.user_id
                last_active = datetime.now().isoformat()
                cursor.execute('INSERT OR REPLACE INTO members (user_id, last_active) VALUES (?, ?)',
                              (user_id, last_active))
        conn.commit()

async def kick_inactive_members():
    kicked_count = 0  # တစ်နေ့မှာ kick လုပ်တဲ့ အရေအတွက်
    max_kicks_per_day = 10  # တစ်နေ့ကို အများဆုံး ၁၀ ယောက်

    async with client:
        # ဂရုပ်ထဲက အဖွဲ့ဝင်တွေကို ရယူပါ
        async for user in client.iter_participants(group_username):
            if kicked_count >= max_kicks_per_day:
                break  # ၁၀ ယောက်ထိ kick လုပ်ပြီးရင် ရပ်ပါ

            user_id = user.id
            # Database ထဲမှာ ဒီအဖွဲ့ဝင်ရဲ့ နောက်ဆုံး active အချိန်ကို စစ်ပါ
            cursor.execute('SELECT last_active FROM members WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            if result is None:  # နောက်ဆုံး ၇ ရက်အတွင်း မက်ဆေ့ချ်တစ်ခါမှ မပို့ဖူးရင်
                try:
                    await client.kick_participant(group_username, user_id)
                    print(f'{user_id} ကို ဂရုပ်ထဲက ထုတ်လိုက်ပါပြီ။')
                    kicked_count += 1
                except Exception as e:
                    print(f'{user_id} ကို ထုတ်မရပါ: {e}')

# တစ်�နေ့တစ်ကြိမ် run ဖို့ scheduling လုပ်ပါ
def job():
    client.loop.run_until_complete(update_member_activity())  # နောက်ဆုံး ၇ ရက်မက်ဆေ့ချ်ပို့သူတွေကို မှတ်ပါ
    client.loop.run_until_complete(kick_inactive_members())  # Inactive သူတွေကို kick လုပ်ပါ

# နေ့စဉ် သတ်မှတ်ထားတဲ့ အချိန်မှာ run ဖို့ schedule သတ်မှတ်ပါ (ဥပမာ: ည ၁၂:၀၀)
schedule.every().day.at("00:00").do(job)

# Script ကို အမြဲ run ထားပါ
while True:
    schedule.run_pending()
    time.sleep(60)  # ၁ မိနစ်တစ်ကြိမ် schedule ကို စစ်ပါ
