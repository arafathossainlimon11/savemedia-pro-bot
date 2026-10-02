import asyncio
import os
import re
import time
from aiohttp import web
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import yt_dlp

# --- কনফিগারেশন ---
BOT_TOKEN = "8565435437:AAEBFehjaVaS_9sV89cv26K0GXJFJ0II6ak"
MONETAG_AD_LINK = "https://omg10.com/4/11200499"

# ২ ঘণ্টা টাইমার (৭২০০ সেকেন্ড)
COOLDOWN_SECONDS = 7200

bot = telebot.TeleBot(BOT_TOKEN)

# ইউজারের লাস্ট অ্যাড দেখার সময় ট্র্যাক করার জন্য ডাটাবেজ
user_last_ad_time = {}


def is_ad_required(user_id):
  last_time = user_last_ad_time.get(user_id, 0)
  current_time = time.time()
  return (current_time - last_time) >= COOLDOWN_SECONDS


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  welcome_text = (
      "🚀 **Welcome to SaveMedia Pro Bot!**\n\n"
      "Send me any video link from **TikTok, Instagram Reels, Facebook, or"
      " YouTube Shorts** to download HD videos without watermark!\n\n"
      "⚡ *Fast, Free & High Quality Downloads.*"
  )
  bot.reply_to(message, welcome_text, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("unlock_"))
def handle_unlock(call):
  user_id = call.from_user.id
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


# --- শর্ট লিংক বা শেয়ার লিংক অরিজিনাল লিংকে রূপান্তর করার ফাংশন ---
def unshorten_url(url):
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    res = requests.head(
        url, allow_redirects=True, headers=headers, timeout=10
    )
    return res.url
  except Exception:
    return url


# --- টিকটকের জন্য ডেডিকেটেড এপিআই ---
def download_tiktok(url, output_path):
  try:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    res = requests.get(api_url, timeout=10).json()
    if res.get("code") == 0:
      video_url = res["data"]["play"]
      v_data = requests.get(video_url, timeout=30).content
      with open(output_path, "wb") as f:
        f.write(v_data)
      return True
  except Exception as e:
    print(f"TikTok API Error: {e}")
  return False


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

  raw_url = urls[0]

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

  status_msg = bot.reply_to(
      message, "🔄 **Processing video... Please wait.**", parse_mode="Markdown"
  )

  try:
    if not os.path.exists("downloads"):
      os.makedirs("downloads")

    output_file = f"downloads/{user_id}_{int(time.time())}.mp4"
    download_success = False

    # ২. শর্ট লিংক আনরোল করা (বিশেষ করে ফেসবুক শেয়ার লিংকের জন্য)
    real_url = unshorten_url(raw_url)

    # ৩. টিকটক আলাদা এপিআই দিয়ে চেক
    if "tiktok.com" in real_url:
      download_success = download_tiktok(real_url, output_file)

    # ৪. ইউটিউব, ফেসবুক ও ইনস্টাগ্রামের জন্য অ্যাডভান্সড ডাউনলোডার
    if not download_success:
      ydl_opts = {
          "format": "best[ext=mp4]/best",
          "outtmpl": output_file,
          "quiet": True,
          "no_warnings": True,
          "nocheckcertificate": True,
          "geo_bypass": True,
          "extractor_args": {
              "youtube": {"player_client": ["ios", "mweb", "android"]}
          },
          "http_headers": {
              "User-Agent": (
                  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)"
                  " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6"
                  " Mobile/15E148 Safari/604.1"
              ),
              "Accept-Language": "en-US,en;q=0.9",
          },
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([real_url])
        download_success = True

    # ৫. ভিডিও সেন্ড করা
    if download_success and os.path.exists(output_file):
      markup = InlineKeyboardMarkup()
      btn_sponsor = InlineKeyboardButton(
          "⚡ Bonus Offer / Sponsor", url=MONETAG_AD_LINK
      )
      markup.row(btn_sponsor)

      caption_text = (
          f"📥 **Downloaded via @savemediapro_getbot**\n\n"
          f"🔥 **Earn Money Online:** [Click Here]({MONETAG_AD_LINK})"
      )

      with open(output_file, "rb") as video_file:
        bot.send_video(
            chat_id,
            video_file,
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=markup,
        )

      bot.delete_message(chat_id, status_msg.message_id)
      if os.path.exists(output_file):
        os.remove(output_file)
    else:
      raise Exception("File extraction failed")

  except Exception as e:
    bot.edit_message_text(
        "❌ **Failed to download video.** Please ensure the video is public and"
        " try again.",
        chat_id=chat_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
    )
    print(f"Error: {e}")


# --- Web Server ---
routes = web.RouteTableDef()


@routes.get("/")
async def home(request):
  return web.Response(text="SaveMedia Pro Bot Active!", content_type="text/plain")


def run_bot():
  print(">>> SaveMedia Pro Bot Active <<<")
  bot.remove_webhook()
  bot.infinity_polling()


async def start_background_tasks(app):
  asyncio.create_task(asyncio.to_thread(run_bot))


app = web.Application()
app.add_routes(routes)
app.on_startup.append(start_background_tasks)

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  web.run_app(app, host="0.0.0.0", port=port)
