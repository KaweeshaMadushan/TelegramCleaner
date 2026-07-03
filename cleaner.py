import asyncio
import sys
import os
from dotenv import load_dotenv

# Load variables from .env file for local testing
load_dotenv()

# --- 1. SPECIAL FIX FOR PYTHON 3.14 ---
# Manually handle the event loop to prevent RuntimeError in Python 3.14
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client
from pyrogram.enums import ChatType

# --- 2. CONFIGURATION ---
# We get keys from Environment Variables for security
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")

async def main_task():
    # Check if API credentials are provided
    if not API_ID or not API_HASH:
        print("❌ Error: API_ID or API_HASH not found in Environment Variables!")
        return

    # Initialize the Telegram Client
    app = Client("my_account", api_id=API_ID, api_hash=API_HASH)
    
    async with app:
        print("\n🔍 Successfully logged in! Scanning for groups and channels...")
        
        # Load Whitelist from file
        try:
            with open("whitelist.txt", "r") as f:
                whitelist = [line.strip().lower() for line in f.readlines()]
        except FileNotFoundError:
            whitelist = []

        to_leave = []

        # Iterate through all chats
        async for dialog in app.get_dialogs():
            # Check if chat is a Group, Supergroup, or Channel
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                title = dialog.chat.title or "Unknown"
                
                # Check if chat is in the whitelist
                if title.lower() in whitelist:
                    print(f"✅ Keeping (Whitelisted): {title}")
                else:
                    to_leave.append((dialog.chat.id, title))

        if not to_leave:
            print("✨ Your account is already clean!")
            return

        print(f"\n⚠️ FOUND {len(to_leave)} ITEMS TO REMOVE.")
        
        # Execution Loop (Auto-leaves without asking, as servers don't support input)
        for chat_id, title in to_leave:
            try:
                print(f"🚪 Leaving: {title}")
                await app.leave_chat(chat_id)
                # 2-second delay to prevent Telegram flood wait/ban
                await asyncio.sleep(2) 
            except Exception as e:
                print(f"❌ Error leaving {title}: {e}")
                # Wait longer if an error occurs (safety measure)
                await asyncio.sleep(5)
                
        print("\n✅ Cleanup complete! Your Telegram is now clean.")

if __name__ == "__main__":
    try:
        # Start the main task
        asyncio.run(main_task())
    except KeyboardInterrupt:
        print("\nStopping the script...")