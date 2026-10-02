import os
import re
import time
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import ytdlp

# --- কনফিগারেশন ---
BOT_TOKEN = "8565435437:AAEBFehjaVaS_9sV89cv26K0GXJFJ0II6ak"
MONETAG_AD_LINK = "https://omg10.com/4/11200499"

# ২ ঘণ্টা টাইマー (৭২০০ সেকেন্ড)
COOLDOWN_SECONDS = 7200

bot = telebot.TeleBot(BOT_TOKEN)

# ইউজারের লাস্ট অ্যাড দেখার সময় ট্র্যাক করার জন্য ডাটাবেজ
user_last_ad_time = {}


# --- টাইমার অ্যাড অপশন চেক করার ফাংশন ---
def is_ad_required(user_id):
  last_time = user_last_ad_time.get(user_id, 0)
  current_time = time.time()
  if current_time - last_time >= COOLDOWN_SECONDS:
    return True
  return False


# --- স্টার্ট ও মেনু ---
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  welcome_text = (
      "🚀 **Welcome to SaveMedia Pro Bot!**\n\n"
      "Send me any video link from **TikTok, Instagram Reels, Facebook, or"
      " YouTube Shorts** to download HD videos without watermark!\n\n"
      "⚡ *Fast, Free & High Quality Downloads.*"
  )
  bot.reply_to(message, welcome_text, parse_mode="Markdown")


# --- আনলক অ্যাড বাটন হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("unlock_"))
def handle_unlock(call):
  user_id = call.from_user.id
  # ইউজার বাটন চাপলে তার আগামী ২ ঘণ্টার জন্য ডাউনলোডার আনলক হয়ে যাবে
  user_last_ad_time[user_id] = time.time()

  bot.answer_callback_query(
      call.id,
      "✅ Unlimited Downloads Unlocked for 2 Hours!",
      show_alert=True,
  )
  bot.edit_message_text(
      "🎉 **Access Granted!**\n\nNow send your video URL again to download"
      " immediately.",
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      parse_mode="Markdown",
  )


# --- ভিডিও লিংক প্রসেসিং ---
@bot.message_handler(func=lambda message: True)
def process_video_link(message):
  user_id = message.from_user.id
  chat_id = message.chat.id
  text = message.text.strip()

  urls = re.findall(r"https?://[^\s]+", text)
  if not urls:
    bot.reply_to(
        message,
        "❌ **Invalid Link!** Please send a valid TikTok, Instagram, Facebook, or"
        " YouTube video URL.",
        parse_mode="Markdown",
    )
    return

  video_url = urls[0]

  # ১. ২ ঘণ্টার টাইমার অ্যাড চেক
  if is_ad_required(user_id):
    markup = InlineKeyboardMarkup()
    btn_ad = InlineKeyboardButton(
        "🚀 Watch Ad & Unlock (2 Hours)", url=MONETAG_AD_LINK
    )
    btn_verify = InlineKeyboardButton(
        "✅ I Have Watched (Unlock)", callback_data=f"unlock_{user_id}"
    )
    markup.row(btn_ad)
    markup.row(btn_verify)

    ad_msg = (
        "🔒 **Download Access Locked!**\n\n"
        "Please click the button below once to unlock **2 Hours of Unlimited No-Watermark Downloads**!"
    )
    bot.send_message(
        chat_id, ad_msg, parse_mode="Markdown", reply_markup=markup
    )
    return

  # ২. ভিডিও ডাউনলোডিং নোটিফিকেশন
  status_msg = bot.reply_to(
      message, "🔄 **Processing your video... Please wait.**", parse_mode="Markdown"
  )

  # ৩. ভিডিও ডাউনলোড ও সেন্ড করা
  try:
    ydl_opts = {
        "format": "best",
        "outtmpl": f"downloads/{user_id}_%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    if not os.path.exists("downloads"):
      os.makedirs("downloads")

    with ytdlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(video_url, download=True)
      filename = ydl.prepare_filename(info)

    # ইনলাইন বাটন ও ক্যাপশন এড
    markup = InlineKeyboardMarkup()
    btn_sponsor = InlineKeyboardButton(
        "⚡ Bonus Offer / Sponsor", url=MONETAG_AD_LINK
    )
    markup.row(btn_sponsor)

    caption_text = (
        f"📥 **Downloaded via @savemediapro_getbot**\n\n"
        f"🔥 **Earn Money Online:** [Click Here]({MONETAG_AD_LINK})"
    )

    with open(filename, "rb") as video_file:
      bot.send_video(
          chat_id,
          video_file,
          caption=caption_text,
          parse_mode="Markdown",
          reply_markup=markup,
      )

    # কাজ শেষ হলে ফাইল ডিলেট করা
    bot.delete_message(chat_id, status_msg.message_id)
    if os.path.exists(filename):
      os.remove(filename)

  except Exception as e:
    bot.edit_message_text(
        "❌ **Failed to download video.** Please check the link and try again.",
        chat_id=chat_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
    )
    print(f"Error: {e}")


if __name__ == "__main__":
  print(">>> SaveMedia Pro Bot Active <<<")
  bot.infinity_polling()
