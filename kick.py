from telegram.ext import Application
import sqlite3
import asyncio

async def manual_kick():
    conn = sqlite3.connect('group_activity.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM members WHERE last_active < datetime('now', '-3 days')")
    inactive_users = [row[0] for row in cursor.fetchall()]
    conn.close()

    app = Application.builder().token(bot_token).build()
    for user_id in inactive_users:
        try:
            await app.bot.ban_chat_member(group_username, user_id)
            print(f"Kicked user {user_id}")
        except Exception as e:
            print(f"Failed to kick user {user_id}: {e}")

if __name__ == '__main__':
    asyncio.run(manual_kick())
