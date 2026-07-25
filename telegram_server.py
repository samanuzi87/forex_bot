"""
سرور همیشه‌روشن مدیریت دکمه‌های شیشه‌ای تلگرام (برای اجرا روی Render)
برخلاف نسخه‌ی قبلی (telegram_handler.py که هر ۱۰ دقیقه اجرا می‌شد)، این سرور
همیشه روشنه و همون لحظه که دکمه زده می‌شه، تلگرام مستقیم بهش خبر می‌ده (Webhook).

این سرور فایلی روی خودش ذخیره نمی‌کنه؛ به‌جاش مستقیم از طریق GitHub API
فایل config.json رو داخل خود مخزن گیت‌هاب می‌خونه و به‌روزرسانی می‌کنه.
"""

import os
import json
import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GITHUB_TOKEN = os.environ["GH_TOKEN"]
GITHUB_REPO = os.environ["GH_REPO"]  # مثلا: "samanuzi87/forex_bot"
CONFIG_PATH = "config.json"

SYMBOL_CATALOG = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP",
    "EUR/JPY", "XAU/USD", "XAG/USD", "USD/TRY",
]

WEEKDAYS = [
    ("شنبه", 5), ("یکشنبه", 6), ("دوشنبه", 0), ("سه‌شنبه", 1),
    ("چهارشنبه", 2), ("پنجشنبه", 3), ("جمعه", 4),
]

# حافظه‌ی موقت انتخاب‌های در حال انجام (فقط تا وقتی سرور روشنه لازمه)
pending_state = {}


def weekday_name(num):
    for name, n in WEEKDAYS:
        if n == num:
            return name
    return "نامشخص"


def build_symbols_keyboard(pending_symbols):
    rows, row = [], []
    for i, symbol in enumerate(SYMBOL_CATALOG):
        mark = "✅ " if symbol in pending_symbols else "⬜ "
        row.append({"text": f"{mark}{symbol}", "callback_data": f"toggle:{i}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        {"text": "✅ تایید نهایی", "callback_data": "confirm_symbols"},
        {"text": "❌ لغو", "callback_data": "cancel"},
    ])
    return rows


def build_weekday_keyboard():
    rows, row = [], []
    for name, num in WEEKDAYS:
        row.append({"text": name, "callback_data": f"setday:{num}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


# ---------------------------------------------------------------
# ارتباط با تلگرام
# ---------------------------------------------------------------

def tg_call(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    return requests.post(url, json=payload, timeout=15).json()


def answer_callback(callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    tg_call("answerCallbackQuery", payload)


def edit_message(chat_id, message_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg_call("editMessageText", payload)


# ---------------------------------------------------------------
# ارتباط با گیت‌هاب (خوندن/نوشتن مستقیم config.json داخل مخزن)
# ---------------------------------------------------------------

def gh_get_config():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]


def gh_update_config(new_config, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content_str = json.dumps(new_config, ensure_ascii=False, indent=2)
    b64_content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {
        "message": "به‌روزرسانی تنظیمات از طریق دکمه‌های تلگرام",
        "content": b64_content,
        "sha": sha,
    }
    r = requests.put(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    return True


# ---------------------------------------------------------------
# پردازش کلیک روی دکمه‌ها
# ---------------------------------------------------------------

def handle_callback(cq):
    data = cq["data"]
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    callback_id = cq["id"]

    answer_callback(callback_id)

    config, sha = gh_get_config()

    if data == "menu_symbols":
        pending_state[chat_id] = {"pending_symbols": list(config.get("symbols", []))}
        keyboard = build_symbols_keyboard(pending_state[chat_id]["pending_symbols"])
        edit_message(chat_id, message_id, "نمادهای مورد نظرت رو انتخاب کن:", keyboard)

    elif data == "menu_weekday":
        keyboard = build_weekday_keyboard()
        current = weekday_name(config.get("weekly_report_weekday", 3))
        edit_message(chat_id, message_id, f"روز فعلی گزارش هفتگی: {current}\nروز جدید رو انتخاب کن:", keyboard)

    elif data.startswith("toggle:"):
        idx = int(data.split(":")[1])
        symbol = SYMBOL_CATALOG[idx]
        state = pending_state.setdefault(chat_id, {"pending_symbols": list(config.get("symbols", []))})
        pending = state["pending_symbols"]
        if symbol in pending:
            pending.remove(symbol)
        else:
            pending.append(symbol)
        keyboard = build_symbols_keyboard(pending)
        edit_message(chat_id, message_id, "نمادهای مورد نظرت رو انتخاب کن:", keyboard)

    elif data == "confirm_symbols":
        state = pending_state.get(chat_id, {})
        pending = state.get("pending_symbols", [])
        if pending:
            config["symbols"] = pending
            config["symbols_confirmed"] = True
            gh_update_config(config, sha)
            edit_message(chat_id, message_id, "✅ نمادها ذخیره شدن:\n" + "\n".join(pending))
        else:
            edit_message(chat_id, message_id, "⚠️ هیچ نمادی انتخاب نشده بود، چیزی تغییر نکرد.")
        pending_state.pop(chat_id, None)

    elif data == "cancel":
        edit_message(chat_id, message_id, "لغو شد، چیزی تغییر نکرد.")
        pending_state.pop(chat_id, None)

    elif data.startswith("setday:"):
        day_num = int(data.split(":")[1])
        config["weekly_report_weekday"] = day_num
        gh_update_config(config, sha)
        edit_message(chat_id, message_id, f"✅ روز گزارش هفتگی تغییر کرد به: {weekday_name(day_num)}")


# ---------------------------------------------------------------
# مسیرهای وب (Webhook)
# ---------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    if "callback_query" in update:
        try:
            handle_callback(update["callback_query"])
        except Exception as e:
            print(f"⚠️ خطا در پردازش کلیک: {e}")
    return jsonify({"ok": True})


@app.route("/")
def home():
    return "ربات فارکس - سرور دکمه‌های تلگرام روشن و آماده است ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
