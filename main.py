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


# --- টাইমার অ্যাড অপশন চেক করার ফাংশন ---
def is_ad_required(user_id):
  last_time = user_last_ad_time.get(user_id, 0)
  current_time = time.time()
  return (current_time - last_time) >= COOLDOWN_SECONDS


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


# --- ওয়েব এক্সট্র্যাক্টর এপিআই (Engine 1) ---
def download_via_api(url, output_path):
  try:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
    }
    payload = {"url": url, "vQuality": "720"}

    # পাবলিক ভিডিও এপিআই অ্যান্ডপয়েন্ট
    response = requests.post(
        "https://api.cobalt.tools/",
        json=payload,
        headers=headers,
        timeout=15,
    )
    data = response.json()

    if data.get("status") in ["tunnel", "redirect"]:
      video_url = data.get("url")
      v_resp = requests.get(video_url, stream=True, timeout=30)
      with open(output_path, "wb") as f:
        for chunk in v_resp.iter_content(chunk_size=1024 * 1024):
          if chunk:
            f.write(chunk)
      return True
  except Exception as e:
    print(f"API Engine Error: {e}")
  return False


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

  # ২. ডাউনলোডিং স্ট্যাটাস
  status_msg = bot.reply_to(
      message,
      "🔄 **Extracting & Processing video... Please wait.**",
      parse_mode="Markdown",
  )

  try:
    if not os.path.exists("downloads"):
      os.makedirs("downloads")

    output_file = f"downloads/{user_id}_{int(time.time())}.mp4"
    download_success = False

    # ৩. প্রথমে Web API Engine দিয়ে চেষ্টা
    download_success = download_via_api(video_url, output_file)

    # ৪. এপিআই কাজ না করলে Backup yt-dlp Engine (Android/iOS Client Bypass)
    if not download_success:
      ydl_opts = {
          "format": "best[ext=mp4]/bestvideo+bestaudio/best",
          "outtmpl": output_file,
          "quiet": True,
          "no_warnings": True,
          "nocheckcertificate": True,
          "geo_bypass": True,
          "extractor_args": {
              "youtube": {"player_client": ["android", "ios", "mweb"]}
          },
          "http_headers": {
              "User-Agent": (
                  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)"
                  " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6"
                  " Mobile/15E148 Safari/604.1"
              )
          },
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
        download_success = True

    # ৫. ভিডিও টেলিগ্রামে পাঠানো
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
      raise Exception("Failed to fetch file.")

  except Exception as e:
    bot.edit_message_text(
        "❌ **Failed to download video.** Please check the link or try another"
        " video.",
        chat_id=chat_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
    )
    print(f"Download Error: {e}")


# --- Web Server (Render Active রাখার জন্য) ---
routes = web.RouteTableDef()


@routes.get("/")
async def home(request):
  return web.Response(
      text="SaveMedia Pro Bot Engine Active!", content_type="text/plain"
  )


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
