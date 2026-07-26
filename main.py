"""
ربات تحلیل‌گر فارکس - مرحله ۱۱: پاک کردن پیام قبلی + دکمه‌ی جدا برای هر نمودار
تغییرات نسبت به نسخه‌ی قبل:
1) دیگه دکمه‌های «تغییر نماد» و «تغییر روز هفتگی» زیر گزارش نیستن (این دو از طریق
   دستورات همیشگی /symbols و /weekday در خود تلگرام در دسترسن - در telegram_server.py).
2) قبل از فرستادن گزارش جدید (روزانه یا هفتگی)، پیام قبلی همون نوع پاک می‌شه.
3) عکس نمودارها دیگه خودکار همه با هم فرستاده نمی‌شن؛ به‌جاش یک پیام با یک دکمه‌ی
   جدا برای هر نماد فرستاده می‌شه؛ با زدن دکمه، همون لحظه نمودار همون نماد میاد.
"""

import json
import os
import re
import imaplib
import email as email_lib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ALERT_THRESHOLD_PERCENT = 0.5
HISTORY_FILE = "price_history.json"
SERIES_FILE = "price_series.json"
MAX_HISTORY_POINTS = 30
CHARTS_DIR = "charts"
SYMBOLS_FILE = "config.json"
DEFAULT_WEEKLY_WEEKDAY = 3

SYMBOL_CATALOG = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP",
    "EUR/JPY", "XAU/USD", "XAG/USD", "USD/TRY",
]

WEEKDAY_NAMES_FA = {
    5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه",
    2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه",
}


def safe_name(symbol):
    return symbol.replace("/", "_")


def load_symbols_config(path=SYMBOLS_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_symbols_config(config, path=SYMBOLS_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_json_file(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"متغیر محیطی '{name}' تنظیم نشده. "
            f"روی گیت‌هاب باید توی Settings > Secrets and variables > Actions اضافه بشه."
        )
    return value


# ---------------------------------------------------------------
# انتخاب نماد از طریق پاسخ ایمیل (همچنان فعال، جدا از دکمه‌های تلگرام)
# ---------------------------------------------------------------

def check_symbol_selection_email(config, sender_email, app_password):
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(sender_email, app_password)
        imap.select("INBOX")

        status, data = imap.search(None, '(UNSEEN SUBJECT "SELECT SYMBOLS")')
        if status != "OK" or not data[0]:
            imap.logout()
            return config, None

        email_ids = data[0].split()
        latest_id = email_ids[-1]

        status, msg_data = imap.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw_email)

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(errors="ignore")

        numbers = [int(n) for n in re.findall(r"\d+", body)]
        selected_symbols = [
            SYMBOL_CATALOG[n - 1] for n in numbers
            if 1 <= n <= len(SYMBOL_CATALOG)
        ]
        selected_symbols = list(dict.fromkeys(selected_symbols))

        imap.store(latest_id, "+FLAGS", "\\Seen")
        imap.logout()

        if selected_symbols:
            config["symbols"] = selected_symbols
            config["symbols_confirmed"] = True
            save_symbols_config(config)
            return config, selected_symbols

        return config, None

    except Exception as e:
        print(f"⚠️  خطا در بررسی ایمیل درخواست تغییر نماد: {e}")
        return config, None


def build_symbol_catalog_text(current_symbols):
    lines = []
    lines.append("")
    lines.append("-" * 50)
    lines.append("لیست نمادهای قابل انتخاب (یا از دستور /symbols توی تلگرام استفاده کن):")
    lines.append("")
    for i, symbol in enumerate(SYMBOL_CATALOG, start=1):
        marker = "  ✅ (انتخاب شده)" if symbol in current_symbols else ""
        lines.append(f"{i}. {symbol}{marker}")
    lines.append("")
    lines.append("برای تغییر از طریق ایمیل: یک ایمیل با موضوع SELECT SYMBOLS بفرست")
    lines.append("و شماره‌ی نمادهای دلخواه رو با ویرگول جدا کن، مثلا: 1, 4, 10")
    return "\n".join(lines)


# ---------------------------------------------------------------
# گرفتن قیمت، تحلیل، نمودار
# ---------------------------------------------------------------

def get_price(symbol, api_key):
    url = "https://api.twelvedata.com/price"
    params = {"symbol": symbol, "apikey": api_key}
    response = requests.get(url, params=params)
    data = response.json()

    if "price" not in data:
        return None, data.get("message", "خطای نامشخص")

    return float(data["price"]), None


def analyze_price(symbol, current_price, history):
    previous_price = history.get(symbol)

    if previous_price is None:
        return "(اولین بار ثبت می‌شه، فردا مقایسه‌ش می‌کنیم)", False

    change_percent = ((current_price - previous_price) / previous_price) * 100
    sign = "+" if change_percent >= 0 else ""
    change_text = f"تغییر نسبت به دفعه قبل: {sign}{change_percent:.2f}%"

    is_alert = abs(change_percent) >= ALERT_THRESHOLD_PERCENT
    if is_alert:
        change_text += " — تغییر قابل توجه!"

    return change_text, is_alert


def update_series(series, symbol, price):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    points = series.get(symbol, [])
    points.append({"time": today, "price": price})
    points = points[-MAX_HISTORY_POINTS:]
    series[symbol] = points
    return series


def build_chart(symbol, series):
    points = series.get(symbol, [])

    if len(points) < 2:
        return None

    times = [p["time"] for p in points]
    prices = [p["price"] for p in points]

    os.makedirs(CHARTS_DIR, exist_ok=True)
    chart_path = os.path.join(CHARTS_DIR, f"{safe_name(symbol)}.png")

    plt.figure(figsize=(7, 3.2))
    plt.plot(times, prices, marker="o", linewidth=2, color="#2b4a6f")
    plt.title(f"روند قیمت {symbol}")
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    plt.savefig(chart_path, dpi=120)
    plt.close()

    return chart_path


def build_report_text(symbols, api_key, history, series):
    lines = []
    lines.append(f"گزارش قیمت نمادها - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    new_history = dict(history)
    chart_paths = {}  # symbol -> path

    for symbol in symbols:
        price, error = get_price(symbol, api_key)

        if error:
            lines.append(f"❌ {symbol}: خطا -> {error}")
            continue

        change_text, is_alert = analyze_price(symbol, price, history)
        icon = "⚠️ " if is_alert else "✅"
        lines.append(f"{icon} {symbol}: {price}  ({change_text})")

        new_history[symbol] = price
        update_series(series, symbol, price)

        chart_path = build_chart(symbol, series)
        if chart_path:
            chart_paths[symbol] = chart_path

    lines.append(build_symbol_catalog_text(symbols))

    return "\n".join(lines), new_history, series, chart_paths


# ---------------------------------------------------------------
# گزارش هفتگی
# ---------------------------------------------------------------

def is_weekly_report_day(config):
    target_day = config.get("weekly_report_weekday", DEFAULT_WEEKLY_WEEKDAY)
    return datetime.now().weekday() == target_day


def build_weekly_summary(symbols, series):
    lines = []
    lines.append(f"📅 خلاصه‌ی هفتگی ربات فارکس - {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 50)
    lines.append("")

    week_ago = datetime.now() - timedelta(days=7)

    for symbol in symbols:
        points = series.get(symbol, [])
        week_points = []
        for p in points:
            try:
                p_time = datetime.strptime(p["time"], "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if p_time >= week_ago:
                week_points.append(p)

        lines.append(f"🔹 {symbol}")

        if len(week_points) < 2:
            lines.append("   داده‌ی کافی برای این هفته هنوز جمع نشده.")
            lines.append("")
            continue

        prices = [p["price"] for p in week_points]
        first_price = prices[0]
        last_price = prices[-1]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        change_percent = ((last_price - first_price) / first_price) * 100
        sign = "+" if change_percent >= 0 else ""

        lines.append(f"   کمترین قیمت هفته: {min_price}")
        lines.append(f"   بیشترین قیمت هفته: {max_price}")
        lines.append(f"   میانگین قیمت هفته: {avg_price:.5f}")
        lines.append(f"   تغییر از اول تا امروز: {sign}{change_percent:.2f}%")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------
# ارسال ایمیل (بدون تغییر - همچنان همه نمودارها رو پیوست می‌کنه)
# ---------------------------------------------------------------

def send_email(subject, body, sender, password, receiver, image_paths=None):
    image_paths = image_paths or []

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for img_path in image_paths:
        with open(img_path, "rb") as f:
            img_data = f.read()
        image = MIMEImage(img_data, name=os.path.basename(img_path))
        msg.attach(image)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        return True, None
    except Exception as first_error:
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, receiver, msg.as_string())
            return True, None
        except Exception as second_error:
            return False, f"روش اول (پورت 465): {first_error}\nروش دوم (پورت 587): {second_error}"


# ---------------------------------------------------------------
# ارتباط با تلگرام (نسخه‌ی جدید: حذف پیام قبلی + آپلود نمودار برای گرفتن file_id)
# ---------------------------------------------------------------

def tg_request(token, method, payload=None, files=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        response = requests.post(url, data=payload or {}, files=files, timeout=20)
        return response.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def delete_telegram_message(token, chat_id, message_id):
    if not message_id:
        return
    tg_request(token, "deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def send_telegram_text(token, chat_id, text, keyboard=None):
    text = text[:4000]
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    result = tg_request(token, "sendMessage", payload)
    if result.get("ok"):
        return True, result["result"]["message_id"], None
    return False, None, result.get("description", "خطای نامشخص")


def upload_chart_and_get_file_id(token, chat_id, chart_path):
    """
    نمودار رو یک‌بار می‌فرسته (فقط برای گرفتن شناسه‌ی داخلی تلگرام، file_id)،
    و فوراً همون پیام رو پاک می‌کنه تا کاربر چیزی اضافه نبینه.
    این file_id بعداً برای نمایش لحظه‌ای نمودار (با زدن دکمه) استفاده می‌شه.
    """
    with open(chart_path, "rb") as f:
        files = {"photo": f}
        result = tg_request(token, "sendPhoto", {"chat_id": chat_id}, files=files)

    if not result.get("ok"):
        return None, result.get("description", "خطای نامشخص")

    message_id = result["result"]["message_id"]
    photo_sizes = result["result"].get("photo", [])
    file_id = photo_sizes[-1]["file_id"] if photo_sizes else None

    delete_telegram_message(token, chat_id, message_id)

    return file_id, None


def build_chart_picker_keyboard(symbols):
    """یک دکمه‌ی جدا برای هر نماد، دو تا دو تا توی هر ردیف."""
    rows, row = [], []
    for symbol in symbols:
        row.append({"text": f"📈 {symbol}", "callback_data": f"show_chart:{safe_name(symbol)}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def main():
    config = load_symbols_config()
    api_key = get_required_env("TWELVE_DATA_API_KEY")
    sender_email = get_required_env("GMAIL_SENDER_EMAIL")
    app_password = get_required_env("GMAIL_APP_PASSWORD")
    receiver_email = get_required_env("GMAIL_RECEIVER_EMAIL")
    telegram_token = get_required_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = get_required_env("TELEGRAM_CHAT_ID")
    pa_url = get_required_env("PA_CONFIG_URL")
    pa_secret = get_required_env("PA_API_SECRET")

    # گرفتن آخرین تنظیمات (نمادها، روز هفتگی، شناسه‌ی آخرین پیام‌ها، file_id نمودارها)
    try:
        response = requests.get(f"{pa_url}/config", params={"token": pa_secret}, timeout=15)
        if response.status_code == 200:
            config = response.json()
    except Exception as e:
        print(f"⚠️ اتصال به سرور تنظیمات ناموفق بود: {e} — از نسخه‌ی محلی استفاده می‌شود.")

    save_symbols_config(config)

    config, updated_symbols = check_symbol_selection_email(config, sender_email, app_password)

    if not config.get("symbols"):
        config["symbols"] = ["EUR/USD", "XAU/USD"]
        save_symbols_config(config)

    symbols = config["symbols"]
    history = load_json_file(HISTORY_FILE)
    series = load_json_file(SERIES_FILE)

    report_text, new_history, new_series, chart_paths = build_report_text(
        symbols, api_key, history, series
    )

    print(report_text)

    save_json_file(new_history, HISTORY_FILE)
    save_json_file(new_series, SERIES_FILE)

    # --- ایمیل: بدون تغییر، مثل قبل همه‌ی نمودارها پیوست می‌شن ---
    print("\n📧 در حال ارسال گزارش روزانه با ایمیل...")
    email_success, email_error = send_email(
        subject="📊 گزارش روزانه ربات فارکس",
        body=report_text,
        sender=sender_email,
        password=app_password,
        receiver=receiver_email,
        image_paths=list(chart_paths.values())
    )
    print("✅ ایمیل ارسال شد" if email_success else f"❌ خطا در ایمیل: {email_error}")
    if updated_symbols:
        confirm_text = f"نمادهای جدید ثبت شد:\n\n{chr(10).join(updated_symbols)}"
        send_email("✅ نمادهای شما به‌روزرسانی شد", confirm_text, sender_email, app_password, receiver_email)

    # --- تلگرام: پاک کردن پیام قبلی، آپلود نمودارها برای گرفتن file_id، فرستادن پیام جدید ---
    print("\n📲 در حال آماده‌سازی گزارش تلگرام...")

    old_daily_message_id = config.get("last_daily_message_id")
    delete_telegram_message(telegram_token, telegram_chat_id, old_daily_message_id)

    chart_file_ids = config.get("chart_file_ids", {})
    for symbol, path in chart_paths.items():
        file_id, upload_error = upload_chart_and_get_file_id(telegram_token, telegram_chat_id, path)
        if file_id:
            chart_file_ids[safe_name(symbol)] = file_id
        else:
            print(f"⚠️ آپلود نمودار {symbol} برای تلگرام ناموفق بود: {upload_error}")
    config["chart_file_ids"] = chart_file_ids

    keyboard = build_chart_picker_keyboard(symbols)
    tg_success, new_message_id, tg_error = send_telegram_text(
        telegram_token, telegram_chat_id, report_text, keyboard=keyboard
    )
    if tg_success:
        print("✅ گزارش روزانه با موفقیت به تلگرام ارسال شد!")
        config["last_daily_message_id"] = new_message_id
    else:
        print(f"❌ ارسال گزارش تلگرام ناموفق بود. خطا: {tg_error}")

    # --- گزارش هفتگی (در صورت رسیدن روزش) ---
    if is_weekly_report_day(config):
        target_day_name = WEEKDAY_NAMES_FA.get(config.get("weekly_report_weekday", DEFAULT_WEEKLY_WEEKDAY), "")
        print(f"\n📅 امروز {target_day_name} است، در حال ساخت گزارش هفتگی...")
        weekly_text = build_weekly_summary(symbols, new_series)
        print(weekly_text)

        send_email("📅 خلاصه‌ی هفتگی ربات فارکس", weekly_text, sender_email, app_password, receiver_email)

        old_weekly_message_id = config.get("last_weekly_message_id")
        delete_telegram_message(telegram_token, telegram_chat_id, old_weekly_message_id)

        weekly_success, weekly_message_id, weekly_error = send_telegram_text(
            telegram_token, telegram_chat_id, weekly_text
        )
        if weekly_success:
            print("✅ خلاصه‌ی هفتگی هم با موفقیت به تلگرام ارسال شد!")
            config["last_weekly_message_id"] = weekly_message_id
        else:
            print(f"❌ ارسال خلاصه‌ی هفتگی به تلگرام ناموفق بود. خطا: {weekly_error}")

    # --- در آخر، تنظیمات به‌روزشده (شناسه‌ی پیام‌ها + file_id نمودارها) رو به PythonAnywhere می‌فرستیم ---
    try:
        requests.post(f"{pa_url}/config", params={"token": pa_secret}, json=config, timeout=15)
    except Exception as e:
        print(f"⚠️ ارسال تنظیمات به سرور PythonAnywhere ناموفق بود: {e}")

    save_symbols_config(config)


if __name__ == "__main__":
    main()
