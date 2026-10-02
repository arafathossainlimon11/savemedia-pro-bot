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


# --- ১. টিকটক প্রসেসর (TikWM POST Engine) ---
def download_tiktok_stream(url, output_path):
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
    }
    # TikWM-এ POST রিকোয়েস্ট পাস করা
    resp = requests.post(
        "https://www.tikwm.com/api/",
        data={"url": url, "hd": 1},
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 200:
      data = resp.json()
      if data.get("code") == 0:
        v_url = (
            data["data"].get("hdplay")
            or data["data"].get("play")
            or data["data"].get("wmplay")
        )
        if v_url:
          if not v_url.startswith("http"):
            v_url = "https://www.tikwm.com" + v_url
          v_data = requests.get(v_url, headers=headers, timeout=30).content
          with open(output_path, "wb") as f:
            f.write(v_data)
          if (
              os.path.exists(output_path)
              and os.path.getsize(output_path) > 50000
          ):
            return True
  except Exception as e:
    print(f"TikTok Engine Error: {e}")
  return False


# --- ২. কোবাল্ট মাল্টি-নোড এপিআই (YouTube, FB, Insta Engine) ---
def download_cobalt_stream(url, output_path):
  # শর্টস বা শেয়ার লিংক ক্লিন করা
  clean_url = url
  yt_match = re.search(
      r"(?:youtube\.com\/shorts\/|youtu\.be\/|v=)([a-zA-Z0-9_-]{11})", url
  )
  if yt_match:
    clean_url = f"https://www.youtube.com/watch?v={yt_match.group(1)}"

  headers = {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "Origin": "https://cobalt.tools",
      "Referer": "https://cobalt.tools/",
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
      ),
  }

  nodes = [
      "https://api.cobalt.tools/",
      "https://co.wuk.sh/api/json",
      "https://cobalt-api.kwippy.com/",
      "https://api.cobalt.red/",
  ]

  payload = {
      "url": clean_url,
      "videoQuality": "720",
      "youtubeVideoCodec": "h264",
      "isAudioOnly": False,
  }

  for node in nodes:
    try:
      r = requests.post(node, json=payload, headers=headers, timeout=12)
      if r.status_code == 200:
        res_data = r.json()
        s_url = None
        if res_data.get("status") in ["tunnel", "redirect"]:
          s_url = res_data.get("url")
        elif res_data.get("status") == "picker":
          picker = res_data.get("picker", [])
          if picker:
            s_url = picker[0].get("url")

        if s_url:
          v_res = requests.get(s_url, stream=True, timeout=35)
          if v_res.status_code == 200:
            with open(output_path, "wb") as f:
              for chunk in v_res.iter_content(chunk_size=1024 * 1024):
                if chunk:
                  f.write(chunk)
            if (
                os.path.exists(output_path)
                and os.path.getsize(output_path) > 50000
            ):
              return True
    except Exception as e:
      print(f"Cobalt Node Fail ({node}): {e}")
      continue

  return False


# --- ৩. ইউটিউব ইনভিডিয়াস এপিআই (Invidious Engine) ---
def download_invidious_stream(url, output_path):
  yt_match = re.search(
      r"(?:youtube\.com\/shorts\/|youtu\.be\/|v=)([a-zA-Z0-9_-]{11})", url
  )
  if not yt_match:
    return False
  v_id = yt_match.group(1)

  inv_nodes = [
      f"https://inv.tux.pizza/api/v1/videos/{v_id}",
      f"https://invidious.nerdvpn.de/api/v1/videos/{v_id}",
      f"https://vid.puffyan.us/api/v1/videos/{v_id}",
  ]

  for node in inv_nodes:
    try:
      resp = requests.get(node, timeout=10)
      if resp.status_code == 200:
        data = resp.json()
        formats = data.get("formatStreams", [])
        if formats:
          stream_url = formats[0].get("url")
          if stream_url:
            v_data = requests.get(stream_url, timeout=30).content
            with open(output_path, "wb") as f:
              f.write(v_data)
            if (
                os.path.exists(output_path)
                and os.path.getsize(output_path) > 50000
            ):
              return True
    except Exception:
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
      "🔄 **Downloading HD Video Stream... Please wait.**",
      parse_mode="Markdown",
  )

  try:
    if not os.path.exists("downloads"):
      os.makedirs("downloads")

    output_file = f"downloads/{user_id}_{int(time.time())}.mp4"
    download_success = False

    # টিকটক
    if "tiktok.com" in raw_url:
      download_success = download_tiktok_stream(raw_url, output_file)

    # ইউটিউব, ফেসবুক, ইনস্টাগ্রাম
    if not download_success:
      download_success = download_cobalt_stream(raw_url, output_file)

    # ইউটিউব ইনভিডিয়াস ব্যাকআপ
    if not download_success and (
        "youtube.com" in raw_url or "youtu.be" in raw_url
    ):
      download_success = download_invidious_stream(raw_url, output_file)

    # ব্যাকআপ yt-dlp
    if not download_success:
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
                      "ios",
                      "android",
                      "mweb",
                  ]
              }
          },
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([raw_url])
        if os.path.exists(output_file) and os.path.getsize(output_file) > 50000:
          download_success = True

    # টেলিগ্রামে সেন্ড করা
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
      raise Exception("All extraction engines failed.")

  except Exception as e:
    bot.edit_message_text(
        "❌ **Failed to download video.** Please check the link and try again.",
        chat_id=chat_id,
        message_id=status_msg.message_id,
        parse_mode="Markdown",
    )
    print(f"Error Log: {e}")


# --- Web Server ---
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
