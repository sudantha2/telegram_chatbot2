import os
os.makedirs("downloads", exist_ok=True)
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from keep_alive import keep_alive

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Store search queries, page info, and message IDs for each user
user_searches = {}

keep_alive()  # Start Flask keep-alive server

@bot.message_handler(commands=['song'])
def song_search(message):
    query = message.text[6:].strip()
    if not query:
        bot.reply_to(message, "❗ Please type a song name after /song.")
        return

    user_id = message.from_user.id
    user_searches[user_id] = {'query': query, 'page': 0, 'search_message_id': None}
    
    search_and_display(message, query, 0)

def search_and_display(message, query, page, chat_id=None, user_id=None):
    target_chat_id = chat_id if chat_id else message.chat.id
    target_user_id = user_id if user_id else message.from_user.id
    
    search_message_id = user_searches.get(target_user_id, {}).get('search_message_id')
    
    if search_message_id:
        try:
            bot.edit_message_text(f"🔍 Searching for `{query}` (Page {page + 1})...", 
                                target_chat_id, search_message_id, parse_mode='Markdown')
        except:
            search_msg = bot.send_message(target_chat_id, f"🔍 Searching for `{query}` (Page {page + 1})...", parse_mode='Markdown')
            user_searches[target_user_id]['search_message_id'] = search_msg.message_id
    else:
        search_msg = bot.send_message(target_chat_id, f"🔍 Searching for `{query}` (Page {page + 1})...", parse_mode='Markdown')
        if target_user_id in user_searches:
            user_searches[target_user_id]['search_message_id'] = search_msg.message_id

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            results = ydl.extract_info(f"ytsearch20:{query}", download=False)['entries']
    except Exception as e:
        error_msg = f"❌ Search failed: {str(e)}"
        search_message_id = user_searches.get(target_user_id, {}).get('search_message_id')
        if search_message_id:
            try:
                bot.edit_message_text(error_msg, target_chat_id, search_message_id)
            except:
                bot.send_message(target_chat_id, error_msg)
        else:
            bot.send_message(target_chat_id, error_msg)
        return

    results_per_page = 5
    start_idx = page * results_per_page
    end_idx = start_idx + results_per_page
    page_results = results[start_idx:end_idx]
    
    if not page_results:
        error_msg = "❌ No more results found."
        search_message_id = user_searches.get(target_user_id, {}).get('search_message_id')
        if search_message_id:
            try:
                bot.edit_message_text(error_msg, target_chat_id, search_message_id)
            except:
                bot.send_message(target_chat_id, error_msg)
        else:
            bot.send_message(target_chat_id, error_msg)
        return

    markup = InlineKeyboardMarkup()
    for video in page_results:
        title = video.get("title", "No Title")
        video_id = video.get("id")
        markup.add(InlineKeyboardButton(title, callback_data=f"dl_{video_id}"))

    if len(results) > end_idx and page < 3:
        markup.add(InlineKeyboardButton("➡️ Next", callback_data=f"next_{page + 1}"))
    
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{target_user_id}"))

    search_message_id = user_searches.get(target_user_id, {}).get('search_message_id')
    if search_message_id:
        try:
            bot.edit_message_text(f"🎧 Choose a song to download (Page {page + 1}):", 
                                target_chat_id, search_message_id, reply_markup=markup)
        except:
            results_msg = bot.send_message(target_chat_id, f"🎧 Choose a song to download (Page {page + 1}):", reply_markup=markup)
            user_searches[target_user_id]['search_message_id'] = results_msg.message_id
    else:
        results_msg = bot.send_message(target_chat_id, f"🎧 Choose a song to download (Page {page + 1}):", reply_markup=markup)
        if target_user_id in user_searches:
            user_searches[target_user_id]['search_message_id'] = results_msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("next_"))
def handle_next_page(call):
    user_id = call.from_user.id
    page = int(call.data[5:])
    
    if user_id not in user_searches:
        bot.answer_callback_query(call.id, "❌ Search session expired. Please start a new search.")
        return
    
    query = user_searches[user_id]['query']
    user_searches[user_id]['page'] = page
    
    search_and_display(None, query, page, call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def handle_cancel(call):
    user_id = call.from_user.id
    
    if user_id in user_searches:
        search_message_id = user_searches[user_id].get('search_message_id')
        if search_message_id:
            try:
                bot.delete_message(call.message.chat.id, search_message_id)
            except:
                pass
        del user_searches[user_id]
    
    user_link = f"[{call.from_user.first_name}](tg://user?id={user_id})"
    bot.send_message(call.message.chat.id, f"{user_link} cancelled the search results.", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_"))
def handle_download(call):
    user_id = call.from_user.id
    video_id = call.data[3:]
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    if user_id in user_searches:
        search_message_id = user_searches[user_id].get('search_message_id')
        if search_message_id:
            try:
                bot.edit_message_text("🎵 Your song will be ready soon! Please wait while we prepare it for you...", 
                                    call.message.chat.id, search_message_id)
            except:
                pass
        del user_searches[user_id]
    
    msg = bot.send_message(call.message.chat.id, "⬇️ Downloading... Please wait.")

    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'cookies': 'cookies.txt'  # ✅ uses cookies.txt to bypass age/login blocks
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        with open(file_path, 'rb') as f:
            bot.send_audio(call.message.chat.id, f, title=info['title'])

        os.remove(file_path)
        bot.delete_message(call.message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)}", call.message.chat.id, msg.message_id)

bot.infinity_polling()
