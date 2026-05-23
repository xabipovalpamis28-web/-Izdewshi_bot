import os
import asyncio
import aiohttp
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
loader = instaloader.Instaloader()

async def recognize_song(file_path: str) -> str:
    try:
        url = "https://shazam.p.rapidapi.com/songs/detect"
        with open(file_path, "rb") as f:
            data = f.read()
        import base64
        encoded = base64.b64encode(data).decode("utf-8")
        headers = {
            "content-type": "text/plain",
            "X-RapidAPI-Key": "SIGN-UP-FOR-KEY",
            "X-RapidAPI-Host": "shazam.p.rapidapi.com"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=encoded, headers=headers) as resp:
                result = await resp.json()
        track = result.get("track", {})
        if not track:
            return "❌ Qo'shiq aniqlanmadi."
        title = track.get("title", "Noma'lum")
        subtitle = track.get("subtitle", "Noma'lum")
        return f"🎵 *{title}*\n👤 {subtitle}"
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"

async def search_song(query: str) -> str:
    async with aiohttp.ClientSession() as session:
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=5"
        async with session.get(url) as resp:
            data = await resp.json()
    results = data.get("results", [])
    if not results:
        return "❌ Qo'shiq topilmadi."
    text = "🎵 Topilgan qo'shiqlar:\n\n"
    for i, song in enumerate(results, 1):
        name = song.get("trackName", "?")
        artist = song.get("artistName", "?")
        preview = song.get("previewUrl", "")
        text += f"{i}. *{name}* — {artist}\n"
        if preview:
            text += f"   🔊 [Tinglash]({preview})\n"
        text += "\n"
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎵 Qo'shiq qidirish", callback_data="search")],
        [InlineKeyboardButton("🎤 Audio yuborish (Shazam)", callback_data="audio")],
        [InlineKeyboardButton("📸 Instagram yuklash", callback_data="instagram")],
    ]
    await update.message.reply_text(
        "👋 Salom! Quyidagilardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "search":
        context.user_data["mode"] = "search"
        await query.message.reply_text("🎵 Qo'shiq nomini yozing:")
    elif query.data == "audio":
        context.user_data["mode"] = "audio"
        await query.message.reply_text("🎤 Audio yuboring:")
    elif query.data == "instagram":
        context.user_data["mode"] = "instagram"
        await query.message.reply_text("📸 Instagram havolasini yuboring:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    mode = context.user_data.get("mode", "")

    if "instagram.com" in text:
        await update.message.reply_text("⏳ Yuklanmoqda...")
        try:
            if "/p/" in text:
                shortcode = text.split("/p/")[1].split("/")[0]
            elif "/reel/" in text:
                shortcode = text.split("/reel/")[1].split("/")[0]
            else:
                await update.message.reply_text("❌ Noto'g'ri havola.")
                return
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            os.makedirs("downloads", exist_ok=True)
            loader.download_post(post, target="downloads")
            sent = False
            for f in os.listdir("downloads"):
                fpath = os.path.join("downloads", f)
                if f.endswith(".mp4"):
                    await context.bot.send_video(chat_id=update.message.chat_id, video=open(fpath, "rb"))
                    sent = True
                elif f.endswith((".jpg", ".jpeg", ".png")):
                    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open(fpath, "rb"))
                    sent = True
            import shutil
            shutil.rmtree("downloads", ignore_errors=True)
            if not sent:
                await update.message.reply_text("❌ Yuklab bo'lmadi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")
        return

    if mode == "search" and text:
        await update.message.reply_text("🔍 Qidirmoqda...")
        result = await search_song(text)
        await update.message.reply_text(result, parse_mode="Markdown")
        context.user_data["mode"] = ""

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Aniqlanmoqda...")
    file = update.message.audio or update.message.voice
    if not file:
        await update.message.reply_text("❌ Audio topilmadi.")
        return
    os.makedirs("downloads", exist_ok=True)
    fpath = f"downloads/{file.file_id}.ogg"
    tg_file = await context.bot.get_file(file.file_id)
    await tg_file.download_to_drive(fpath)
    result = await recognize_song(fpath)
    await update.message.reply_text(result, parse_mode="Markdown")
    os.remove(fpath)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
