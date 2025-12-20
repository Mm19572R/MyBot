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

async def download_tiktok_video(url):
    async with aiohttp.ClientSession() as session:
        try:
            params = {"url": url, "hd": 1}
            async with session.get(API_URL, params=params) as response:
                if response.status != 200: return None
                data = await response.json()

            if "data" not in data or "play" not in data["data"]: return None
            video_url = data["data"]["play"]

            async with session.get(video_url) as video_response:
                if video_response.status == 200:
                    return BytesIO(await video_response.read())
        except Exception as e:
            logging.error(f"Download Error: {e}")
    return None

@dp.message_handler()
async def handle_message(message: types.Message):
    match = re.search(r'(https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+)', message.text)
    if match:
        tiktok_url = match.group(0)
        await message.answer_chat_action("upload_video")
        status_msg = await message.reply("⏳ <b>Downloading...</b>", parse_mode="HTML")

        video_file = await download_tiktok_video(tiktok_url)

        if video_file:
            try:
                # sending the video
                await message.reply_video(video=video_file, caption="✅ Done")
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"❌ Upload Error: {e}")
        else:
            await status_msg.edit_text("❌ Could not download video. API might be busy.")

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

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)