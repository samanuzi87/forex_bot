"""
هندلر تعاملی تلگرام - مدیریت دکمه‌های شیشه‌ای
این اسکریپت جدا از main.py هست و طبق زمان‌بندی خودش (هر ۱۰ دقیقه) اجرا می‌شه.
کارش اینه:
1) پیام‌ها و کلیک‌های جدید روی دکمه‌های تلگرام رو می‌خونه (getUpdates)
2) بسته به این‌که کاربر کدوم دکمه رو زده، منوی بعدی رو نشون می‌ده یا تنظیمات رو ذخیره می‌کنه
3) نمادها و روز گزارش هفتگی رو داخل config.json به‌روزرسانی می‌کنه
"""

import json
import os
import requests

CONFIG_FILE = "config.json"
STATE_FILE = "telegram_state.json"

SYMBOL_CATALOG = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP",
    "EUR/JPY", "XAU/USD", "XAG/USD", "USD/TRY",
]

# ترتیب هفته‌ی ایرانی (شنبه اول هفته)، عدد جلوش همون weekday() پایتونه
WEEKDAYS = [
    ("شنبه", 5), ("یکشنبه", 6), ("دوشنبه", 0), ("سه‌شنبه", 1),
    ("چهارشنبه", 2), ("پنجشنبه", 3), ("جمعه", 4),
]


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def tg_call(token, method, payload=None, files=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.post(url, data=payload or {}, files=files, timeout=20)
    return response.json()


def get_updates(token, offset):
    result = tg_call(token, "getUpdates", {"offset": offset, "timeout": 0})
    if result.get("ok"):
        return result.get("result", [])
    return []


def answer_callback(token, callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    tg_call(token, "answerCallbackQuery", payload)


def edit_message(token, chat_id, message_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    tg_call(token, "editMessageText", payload)


def build_symbols_keyboard(pending_symbols):
    """هر نماد یه دکمه، دو تا دو تا توی هر ردیف، با علامت تیک برای انتخاب‌شده‌ها."""
    rows = []
    row = []
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
    rows = []
    row = []
    for name, num in WEEKDAYS:
        row.append({"text": name, "callback_data": f"setday:{num}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def weekday_name(num):
    for name, n in WEEKDAYS:
        if n == num:
            return name
    return "نامشخص"


def handle_callback(token, config, state, callback_query):
    data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    callback_id = callback_query["id"]

    answer_callback(token, callback_id)

    if data == "menu_symbols":
        state["pending_symbols"] = list(config.get("symbols", []))
        state["pending_message_id"] = message_id
        state["pending_chat_id"] = chat_id
        keyboard = build_symbols_keyboard(state["pending_symbols"])
        edit_message(token, chat_id, message_id, "نمادهای مورد نظرت رو انتخاب کن:", keyboard)

    elif data == "menu_weekday":
        keyboard = build_weekday_keyboard()
        current = weekday_name(config.get("weekly_report_weekday", 3))
        edit_message(
            token, chat_id, message_id,
            f"روز فعلی گزارش هفتگی: {current}\nروز جدید رو انتخاب کن:",
            keyboard
        )

    elif data.startswith("toggle:"):
        idx = int(data.split(":")[1])
        symbol = SYMBOL_CATALOG[idx]
        pending = state.get("pending_symbols", [])
        if symbol in pending:
            pending.remove(symbol)
        else:
            pending.append(symbol)
        state["pending_symbols"] = pending
        keyboard = build_symbols_keyboard(pending)
        edit_message(token, chat_id, message_id, "نمادهای مورد نظرت رو انتخاب کن:", keyboard)

    elif data == "confirm_symbols":
        pending = state.get("pending_symbols", [])
        if pending:
            config["symbols"] = pending
            config["symbols_confirmed"] = True
            save_json(config, CONFIG_FILE)
            edit_message(token, chat_id, message_id, "✅ نمادها ذخیره شدن:\n" + "\n".join(pending))
        else:
            edit_message(token, chat_id, message_id, "⚠️ هیچ نمادی انتخاب نشده بود، چیزی تغییر نکرد.")
        state["pending_symbols"] = []
        state["pending_message_id"] = None

    elif data == "cancel":
        edit_message(token, chat_id, message_id, "لغو شد، چیزی تغییر نکرد.")
        state["pending_symbols"] = []
        state["pending_message_id"] = None

    elif data.startswith("setday:"):
        day_num = int(data.split(":")[1])
        config["weekly_report_weekday"] = day_num
        save_json(config, CONFIG_FILE)
        edit_message(token, chat_id, message_id, f"✅ روز گزارش هفتگی تغییر کرد به: {weekday_name(day_num)}")

    return config, state


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("⚠️  TELEGRAM_BOT_TOKEN تنظیم نشده، از این قابلیت صرف‌نظر می‌شود.")
        return

    config = load_json(CONFIG_FILE, {"symbols": ["EUR/USD", "XAU/USD"]})
    state = load_json(STATE_FILE, {"offset": 0, "pending_symbols": [], "pending_message_id": None})

    try:
        updates = get_updates(token, state.get("offset", 0))
    except Exception as e:
        print(f"⚠️  خطا در ارتباط با تلگرام (احتمالا موقتی است): {e}")
        return

    if not updates:
        print("پیام یا کلیک جدیدی برای پردازش وجود نداشت.")
        save_json(state, STATE_FILE)  # فایل رو حتی بدون تغییر هم می‌سازیم/ذخیره می‌کنیم
        return

    for update in updates:
        state["offset"] = update["update_id"] + 1

        if "callback_query" in update:
            config, state = handle_callback(token, config, state, update["callback_query"])
            print(f"✅ یک کلیک دکمه پردازش شد: {update['callback_query']['data']}")

    save_json(config, CONFIG_FILE)
    save_json(state, STATE_FILE)


if __name__ == "__main__":
    main()
