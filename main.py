import os
import asyncio
import aiohttp
import aiofiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import instaloader
import shazamio

# ===================== TOKENNI SHU YERGA KIRITING =====================
BOT_TOKEN = "8272455642:AAFbmxk3KH2wtkFVKOwpxlNAs5HK2h4YbV4"
# =====================================================================

shazam = shazamio.Shazam()
loader = instaloader.Instaloader()


# ==================== START KOMANDASI ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎵 Qo'shiq qidirish (matn)", callback_data="search_text")],
        [InlineKeyboardButton("🎤 Audio yuborish (Shazam)", callback_data="search_audio")],
        [InlineKeyboardButton("📸 Instagram yuklash", callback_data="instagram")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Salom! Men sizga quyidagi xizmatlarni taqdim etaman:\n\n"
        "🎵 Qo'shiq qidirish - nom yoki so'zlari bo'yicha\n"
        "🎤 Audio orqali qo'shiq tanish (Shazam)\n"
        "📸 Instagram rasm/video/story yuklash\n"
        "🎶 Instagram videodagi qo'shiqni aniqlash\n\n"
        "Quyidan birini tanlang yoki to'g'ridan-to'g'ri yuboring:",
        reply_markup=reply_markup
    )


# ==================== CALLBACK HANDLER ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search_text":
        context.user_data["mode"] = "search_text"
        await query.message.reply_text("🎵 Qo'shiq nomini yoki so'zlarini yozing:")

    elif query.data == "search_audio":
        context.user_data["mode"] = "search_audio"
        await query.message.reply_text("🎤 Audio yoki ovozli xabar yuboring, men qo'shiqni topib beraman!")

    elif query.data == "instagram":
        context.user_data["mode"] = "instagram"
        await query.message.reply_text("📸 Instagram post, reel yoki story havolasini yuboring:")


# ==================== MATN BO'YICHA QO'SHIQ QIDIRISH ====================
async def search_song_by_text(query: str) -> str:
    async with aiohttp.ClientSession() as session:
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=5&country=UZ"
        async with session.get(url) as response:
            data = await response.json()

    results = data.get("results", [])
    if not results:
        return "❌ Qo'shiq topilmadi. Boshqa so'z bilan urinib ko'ring."

    text = "🎵 Topilgan qo'shiqlar:\n\n"
    for i, song in enumerate(results, 1):
        name = song.get("trackName", "Noma'lum")
        artist = song.get("artistName", "Noma'lum")
        album = song.get("collectionName", "Noma'lum")
        preview = song.get("previewUrl", "")
        text += f"{i}. 🎶 *{name}*\n"
        text += f"   👤 Artist: {artist}\n"
        text += f"   💿 Album: {album}\n"
        if preview:
            text += f"   🔊 [Preview eshitish]({preview})\n"
        text += "\n"
    return text


# ==================== AUDIO ORQALI SHAZAM ====================
async def recognize_audio(file_path: str) -> str:
    try:
        out = await shazam.recognize_song(file_path)
        track = out.get("track", {})
        if not track:
            return "❌ Qo'shiq aniqlanmadi. Boshqa audio yuboring."

        title = track.get("title", "Noma'lum")
        subtitle = track.get("subtitle", "Noma'lum")
        genres = track.get("genres", {}).get("primary", "Noma'lum")
        share_href = track.get("share", {}).get("href", "")

        result = (
            f"🎵 *Qo'shiq topildi!*\n\n"
            f"🎶 Nomi: *{title}*\n"
            f"👤 Artist: *{subtitle}*\n"
            f"🎸 Janr: {genres}\n"
        )
        if share_href:
            result += f"🔗 [Shazamda ochish]({share_href})"
        return result
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"


# ==================== INSTAGRAM YUKLASH ====================
async def download_instagram(url: str, chat_id, context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        shortcode = ""
        if "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        elif "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
        elif "/tv/" in url:
            shortcode = url.split("/tv/")[1].split("/")[0]
        else:
            return "❌ Noto'g'ri Instagram havolasi. Post, Reel yoki IGTV havolasini yuboring."

        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        download_dir = f"downloads/{shortcode}"
        os.makedirs(download_dir, exist_ok=True)
        loader.download_post(post, target=download_dir)

        # Fayllarni yuborish
        sent = False
        song_info = ""
        for f in os.listdir(download_dir):
            fpath = os.path.join(download_dir, f)
            if f.endswith(".mp4"):
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=open(fpath, "rb"),
                    caption="📹 Instagram Video"
                )
                # Video ichidagi qo'shiqni aniqlash
                await context.bot.send_message(chat_id=chat_id, text="🔍 Videodagi qo'shiq aniqlanmoqda...")
                song_info = await recognize_audio(fpath)
                sent = True
            elif f.endswith((".jpg", ".jpeg", ".png")):
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=open(fpath, "rb"),
                    caption="📸 Instagram Rasm"
                )
                sent = True

        # Fayllarni tozalash
        import shutil
        shutil.rmtree(download_dir, ignore_errors=True)

        if not sent:
            return "❌ Fayl yuklab olinmadi."

        return song_info if song_info else "✅ Yuklandi!"

    except Exception as e:
        return f"❌ Xatolik: {str(e)}\n\nEslatma: Ba'zi xususiy akkauntlarning postlari yuklanmaydi."


# ==================== XABAR HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode", "")
    text = update.message.text if update.message.text else ""

    # Instagram havolasi avtomatik aniqlansin
    if "instagram.com" in text:
        await update.message.reply_text("⏳ Instagram yuklanmoqda...")
        result = await download_instagram(text, update.message.chat_id, context)
        if result:
            await update.message.reply_text(result, parse_mode="Markdown")
        context.user_data["mode"] = ""
        return

    if mode == "search_text" or (text and mode == ""):
        if text:
            await update.message.reply_text("🔍 Qidirmoqda...")
            result = await search_song_by_text(text)
            await update.message.reply_text(result, parse_mode="Markdown")
            context.user_data["mode"] = ""

    elif mode == "instagram":
        await update.message.reply_text("⏳ Instagram yuklanmoqda...")
        result = await download_instagram(text, update.message.chat_id, context)
        if result:
            await update.message.reply_text(result, parse_mode="Markdown")
        context.user_data["mode"] = ""


# ==================== AUDIO HANDLER ====================
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Audio qabul qilindi, aniqlanmoqda...")

    file = update.message.audio or update.message.voice or update.message.document
    if not file:
        await update.message.reply_text("❌ Audio topilmadi.")
        return

    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{file.file_id}.ogg"
    tg_file = await context.bot.get_file(file.file_id)
    await tg_file.download_to_drive(file_path)

    result = await recognize_audio(file_path)
    await update.message.reply_text(result, parse_mode="Markdown")

    os.remove(file_path)
    context.user_data["mode"] = ""


# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.ALL, handle_audio))

    print("✅ Bot ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
