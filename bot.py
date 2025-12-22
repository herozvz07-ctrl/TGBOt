import os
import telebot
import uuid
from telebot import types
from yt_dlp import YoutubeDL
from flask import Flask, request

# --- НАСТРОЙКИ ---
TOKEN = "7284903125:AAHrn9g2xWH4ydcGfGgfV6l8dyn0zhg22qM"
REQUIRED_CHANNEL = "@ttimperia"
RENDER_URL = "https://tgbot-1-ow0e.onrender.com"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

user_data = {}
user_lang = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

MESSAGES = {
    'RU': {
        'start': "<b>💎 Музыкальный Бот</b>\n\nПришли название песни или исполнителя. Я найду музыку в SoundCloud и пришлю её тебе в MP3.\n\n⚡️ <i>Без ошибок и ограничений!</i>",
        'sub': "❌ <b>Доступ закрыт!</b>\nСначала подпишись на наш канал:",
        'search': "🔎 Ищу: <i>{}</i> в SoundCloud...",
        'found': "<b>Найдено! Выберите трек:</b>",
        'downloading': "🚀 Загрузка... Пожалуйста, подождите.",
        'top': "🔥 ТОП Хитов",
        'lang': "⚙️ Язык / Language",
        'choose_lang': "Выберите язык:",
    },
    'EN': {
        'start': "<b>💎 Music Downloader</b>\n\nSend me a song title or artist. I will find music on SoundCloud and send it in MP3.\n\n⚡️ <i>Fast & No Limits!</i>",
        'sub': "❌ <b>Access Denied!</b>\nPlease subscribe to our channel first:",
        'search': "🔎 Searching: <i>{}</i> on SoundCloud...",
        'found': "<b>Found! Choose a track:</b>",
        'downloading': "🚀 Downloading... Please wait.",
        'top': "🔥 Top Hits",
        'lang': "⚙️ Language",
        'choose_lang': "Choose language:",
    }
}

# --- ФУНКЦИИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(REQUIRED_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

def get_lang(uid):
    return user_lang.get(uid, 'RU')

def main_menu(uid):
    lang = get_lang(uid)
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton(MESSAGES[lang]['top'], callback_data="btn_top"),
        types.InlineKeyboardButton(MESSAGES[lang]['lang'], callback_data="btn_lang")
    )
    return markup

# --- СКАЧИВАНИЕ (ТОЛЬКО SOUNDCLOUD) ---
def download_music(url):
    file_id = str(uuid.uuid4())[:8]

    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    ydl_opts = {
        'outtmpl': f'downloads/{file_id}.%(ext)s',
        'quiet': True,
        'format': 'bestaudio/best',
        'noplaylist': True,

        # ⛔ YouTube запрещён
        'allowed_extractors': ['soundcloud'],

        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        fname = ydl.prepare_filename(info)
        return os.path.splitext(fname)[0] + ".mp3", info.get('title', 'Music')

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    lang = get_lang(uid)

    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "➕ Подписаться",
                url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"
            )
        )
        bot.send_message(message.chat.id, MESSAGES[lang]['sub'], reply_markup=markup)
        return

    bot.send_message(message.chat.id, MESSAGES[lang]['start'], reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: call.data.startswith('btn_'))
def menu_logic(call):
    uid = call.from_user.id
    lang = get_lang(uid)

    if call.data == "btn_lang":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Русский 🇷🇺", callback_data="set_RU"),
            types.InlineKeyboardButton("English 🇺🇸", callback_data="set_EN")
        )
        bot.edit_message_text(
            MESSAGES[lang]['choose_lang'],
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    elif call.data == "btn_top":
        handle_search(call.message, "Popular Music Hits")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_'))
def lang_logic(call):
    new_lang = call.data.split('_')[1]
    user_lang[call.from_user.id] = new_lang
    bot.edit_message_text(
        MESSAGES[new_lang]['start'],
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu(call.from_user.id)
    )

def handle_search(message, query):
    lang = get_lang(message.chat.id)
    msg = bot.send_message(message.chat.id, MESSAGES[lang]['search'].format(query))

    try:
        # 🔎 ПОИСК (scsearch РАБОТАЕТ)
        with YoutubeDL({
            'quiet': True,
            'extract_flat': True
        }) as ydl:
            res = ydl.extract_info(f"scsearch9:{query}", download=False).get('entries', [])

        if not res:
            bot.edit_message_text("❌ Ничего не найдено.", message.chat.id, msg.message_id)
            return

        markup = types.InlineKeyboardMarkup()
        btns = []
        text = f"<b>{MESSAGES[lang]['found']}</b>\n\n"

        index = 0
        for entry in res:
            if entry.get('ie_key') != 'SoundCloud':
                continue

            if index >= 9:
                break

            rid = str(uuid.uuid4())[:8]
            user_data[rid] = entry['url']

            btns.append(
                types.InlineKeyboardButton(
                    EMOJI_NUMS[index],
                    callback_data=f"dl_{rid}"
                )
            )

            text += f"{EMOJI_NUMS[index]} {entry.get('title', '')[:55]}\n"
            index += 1

        if not btns:
            bot.edit_message_text("❌ SoundCloud треки не найдены.", message.chat.id, msg.message_id)
            return

        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])

        bot.edit_message_text(text, message.chat.id, msg.message_id, reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def download_logic(call):
    url = user_data.get(call.data.split('_')[1])
    lang = get_lang(call.from_user.id)

    bot.edit_message_text(
        MESSAGES[lang]['downloading'],
        call.message.chat.id,
        call.message.message_id
    )

    try:
        fpath, title = download_music(url)
        with open(fpath, 'rb') as f:
            bot.send_audio(call.message.chat.id, f, caption=f"✅ <b>{title}</b>")

        os.remove(fpath)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Ошибка файла: {e}")

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def on_msg(m):
    handle_search(m, m.text)

# --- WEBHOOK ---
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([
        telebot.types.Update.de_json(
            request.stream.read().decode("utf-8")
        )
    ])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}", drop_pending_updates=True)
    return "Статус: Ок", 200

if __name__ == "__main__":
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
