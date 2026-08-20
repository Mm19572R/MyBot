import os
import logging
import re
from io import BytesIO
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiohttp import web

# CONFIG
TOKEN = os.getenv("TOKEN") 
API_URL = "https://www.tikwm.com/api/"

logging.basicConfig(level=logging.INFO)

# Init Bot
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Global session to prevent memory leaks
session = None

async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

async def download_tiktok_video(url):
    sess = await get_session()
    try:
        async with sess.get(API_URL, params={"url": url, "hd": 1}, timeout=30) as response:
            if response.status != 200: 
                logging.error(f"API gave a bad status code: {response.status}")
                return None
            
            data = await response.json()

        # LOG THE DATA TO SEE THE REAL ERROR
        logging.info(f"API Response: {data}")

        if "data" not in data or "play" not in data["data"]: 
            logging.error("Missing 'data' or 'play' keys in API response!")
            return None
            
        video_url = data["data"]["play"]

        async with sess.get(video_url, timeout=60) as video_response:
            if video_response.status == 200:
                return BytesIO(await video_response.read())
            else:
                logging.error(f"Failed to download the actual MP4. Status: {video_response.status}")
                
    except Exception as e:
        logging.error(f"Download Error: {e}")
    return None

@dp.message_handler()
async def handle_message(message: types.Message):
    # 1. Handle the /start command FIRST
    if message.text == "/start":
        await message.reply("Welcome! Send me a TikTok link and I'll download it for you.")
        return  # Stop here

    # 2. Look for a TikTok link
    match = re.search(r'(https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+)', message.text)
    
    if match:
        tiktok_url = match.group(0)
        
        # Send "Typing..." action and status message
        await message.answer_chat_action("upload_video")
        status_msg = await message.reply("<b>Wait a second...</b>", parse_mode="HTML")

        video_file = None
        try:
            video_file = await download_tiktok_video(tiktok_url)

            if video_file:
                await message.reply_video(video=video_file, caption="✅ Done!")
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Could not get video details. The API might be busy.")
                
        except Exception as e:
            # Check if it was a file size error (common with free bots)
            if "File is too big" in str(e):
                await status_msg.edit_text("❌ File is too big for this bot to upload.")
            else:
                await status_msg.edit_text(f"❌ Error: {e}")
        finally:
            # ALWAYS clear the memory
            if video_file:
                video_file.close()

    # 3. If it's NOT /start and NOT a link, send the error helper
    else:
        await message.reply("That doesn't look like a TikTok link.\nPlease send a valid link")
        
async def health_check(request):
    return web.Response(text="I am alive!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def on_startup(dp):
    await start_web_server()
    print("🤖 Bot started with Web Server!")

async def on_shutdown(dp):
    global session
    if session and not session.closed:
        await session.close()
    print("💤 Bot shutting down cleanly.")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
