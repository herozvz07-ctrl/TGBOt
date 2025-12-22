import os
import uuid
from flask import Flask, request
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ================== НАСТРОЙКИ ==================
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
PORT = int(os.environ.get("PORT", 5000))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]

# ================== FLASK (Render healthcheck) ==================
@app.route("/")
def home():
    return "Bot is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.stream.read().decode("utf-8"))]
    )
    return "OK", 200


# ================== SOUNDCLOUD DOWNLOAD ==================
def download_soundcloud(query):
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    uid = str(uuid.uuid4())[:8]

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": f"downloads/{uid}.%(ext)s",
        "default_search": "scsearch",
        "format": "bestaudio/best",
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]

        filename = ydl.prepare_filename(info)
        filename = os.path.splitext(filename)[0] + ".mp3"

        return filename, info.get("title", "Music")


# ================== START ==================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🎵 <b>Музыкальный бот</b>\n\n"
        "Отправь название песни 🎧\n"
        "Скачивание идёт через <b>SoundCloud</b>\n\n"
        "⚠️ YouTube не используется (анти-бан)",
    )


# ================== SEARCH ==================
@bot.message_handler(func=lambda m: True)
def search(message):
    query = message.text.strip()
    msg = bot.send_message(message.chat.id, f"🔎 Ищу <b>{query}</b>...")

    try:
        with YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            results = ydl.extract_info(
                f"ytsearch6:{query}",
                download=False
            ).get("entries", [])

        if not results:
            bot.edit_message_text("❌ Ничего не найдено", message.chat.id, msg.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        text = "<b>🎶 Выбери трек:</b>\n\n"

        for i, item in enumerate(results):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = item["title"]
            text += f"{EMOJI_NUMS[i]} {item['title'][:45]}\n"
            markup.add(
                types.InlineKeyboardButton(
                    EMOJI_NUMS[i],
                    callback_data=f"dl_{rid}"
                )
            )

        bot.edit_message_text(
            text,
            message.chat.id,
            msg.message_id,
            reply_markup=markup
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка поиска\n<code>{e}</code>")


# ================== DOWNLOAD ==================
@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def download(call):
    key = call.data.split("_")[1]
    query = user_data.get(key)

    bot.edit_message_text(
        "⬇️ Скачиваю через SoundCloud...\n⏳ Подожди ~20 сек",
        call.message.chat.id,
        call.message.message_id
    )

    try:
        path, title = download_soundcloud(query)

        with open(path, "rb") as audio:
            bot.send_audio(
                call.message.chat.id,
                audio,
                caption=f"🎵 <b>{title}</b>"
            )

        os.remove(path)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception as e:
        bot.send_message(
            call.message.chat.id,
            "❌ Ошибка скачивания\n"
            "Попробуй другой трек\n\n"
            f"<code>{str(e)[:120]}</code>"
        )


# ================== RUN ==================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.polling(none_stop=True)
