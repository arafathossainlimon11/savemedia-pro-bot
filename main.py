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
user_last_ad_time = {}


def is_ad_required(user_id):
  last_time = user_last_ad_time.get(user_id, 0)
  return (time.time() - last_time) >= COOLDOWN_SECONDS


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


# --- ফুল ইউআরএল ট্রেসার (Short Links Resolver) ---
def get_full_url(short_url):
  session = requests.Session()
  session.headers.update({
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
      )
  })
  try:
    response = session.get(short_url, allow_redirects=True, timeout=10)
    return response.url
  except Exception:
    return short_url


# --- ১. টিকটকের জন্য ডেডিকেটেড এক্সট্র্যাক্টর ---
def download_tiktok_video(url, output_path):
  try:
    full_url = get_full_url(url)
    api_endpoint = f"https://www.tikwm.com/api/?url={full_url}"
    res = requests.get(api_endpoint, timeout=12).json()

    if res.get("code") == 0:
      video_url = res["data"].get("play") or res["data"].get("wmplay")
      if video_url:
        v_stream = requests.get(video_url, timeout=30)
        with open(output_path, "wb") as f:
          f.write(v_stream.content)
        return True
  except Exception as e:
    print(f"TikTok Download Exception: {e}")
  return False


# --- ২. গ্লোবাল কোবাল্ট এপিআই (YouTube Shorts, FB & Insta) ---
def download_via_cobalt_engine(url, output_path):
  clean_url = get_full_url(url)

  # ইউটিউব শর্টসকে স্ট্যান্ডার্ড ওয়াচ ইউআরএলে কনভার্ট করা
  yt_match = re.search(
      r"(?:youtube\.com\/shorts\/|youtu\.be\/|v=)([a-zA-Z0-9_-]{11})", clean_url
  )
  if yt_match:
    video_id = yt_match.group(1)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

  cobalt_nodes = [
      "https://api.cobalt.tools/",
      "https://cobalt-api.kwippy.com/",
      "https://cobalt.qtf.rs/",
      "https://co.wuk.sh/",
  ]

  headers = {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      ),
  }

  for node in cobalt_nodes:
    try:
      payload = {"url": clean_url, "videoQuality": "720"}
      resp = requests.post(node, json=payload, headers=headers, timeout=10)
      if resp.status_code == 200:
        data = resp.json()
        stream_url = None
        if data.get("status") in ["tunnel", "redirect"]:
          stream_url = data.get("url")
        elif data.get("status") == "picker":
          picker = data.get("picker", [])
          if picker:
            stream_url = picker[0].get("url")

        if stream_url:
          v_resp = requests.get(stream_url, stream=True, timeout=35)
          if v_resp.status_code == 200:
            with open(output_path, "wb") as f:
              for chunk in v_resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                  f.write(chunk)
            if (
                os.path.exists(output_path)
                and os.path.getsize(output_path) > 1000
            ):
              return True
    except Exception as e:
      print(f"Node fail ({node}): {e}")
      continue

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
      message,
      "🔄 **Extracting HD Video Stream... Please wait.**",
      parse_mode="Markdown",
  )

  try:
    if not os.path.exists("downloads"):
      os.makedirs("downloads")

    output_file = f"downloads/{user_id}_{int(time.time())}.mp4"
    download_success = False

    # ২. টিকটক প্রসেসিং
    if "tiktok.com" in raw_url:
      download_success = download_tiktok_video(raw_url, output_file)

    # ৩. টিকটক ছাড়া অন্যান্য সোশ্যাল মিডিয়া (YouTube, Facebook, Insta)
    if not download_success:
      download_success = download_via_cobalt_engine(raw_url, output_file)

    # ৪. ব্যাকআপ ইঞ্জিনে চূড়ান্ত চেষ্টা (yt-dlp Engine)
    if not download_success:
      real_url = get_full_url(raw_url)
      ydl_opts = {
          "format": "best[ext=mp4]/best",
          "outtmpl": output_file,
          "quiet": True,
          "no_warnings": True,
          "nocheckcertificate": True,
          "geo_bypass": True,
          "extractor_args": {
              "youtube": {
                  "player_client": [
                      "android",
                      "ios",
                      "mweb",
                      "tv_embedded",
                  ]
              }
          },
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([real_url])
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
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
      raise Exception("Video extraction stream failed.")

  except Exception as e:
    bot.edit_message_text(
        "❌ **Failed to download video.** Please check the link or try another"
        " video.",
        chat_id=chat_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
    )
    print(f"Error Log: {e}")


# --- Web Server (Render Active রাখার জন্য) ---
routes = web.RouteTableDef()


@routes.get("/")
async def home(request):
  return web.Response(
      text="SaveMedia Pro Bot Active!", content_type="text/plain"
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
