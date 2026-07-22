"""
ربات تحلیل‌گر فارکس - مرحله ۹: افزودن ارسال گزارش به تلگرام (علاوه‌بر ایمیل)
این اسکریپت:
1) صندوق ورودی رو برای درخواست تغییر نماد (SELECT SYMBOLS) چک می‌کنه.
2) قیمت لحظه‌ای نمادها رو می‌گیره، تحلیل می‌کنه، نمودار می‌سازه.
3) گزارش روزانه رو هم با ایمیل، هم با تلگرام می‌فرسته.
4) پنجشنبه‌ها، گزارش هفتگی رو هم از هر دو مسیر (ایمیل + تلگرام) می‌فرسته.
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

SYMBOL_CATALOG = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP",
    "EUR/JPY", "XAU/USD", "XAG/USD", "USD/TRY",
]


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
# انتخاب نماد از طریق پاسخ ایمیل
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
    lines.append("لیست نمادهای قابل انتخاب:")
    lines.append("")
    for i, symbol in enumerate(SYMBOL_CATALOG, start=1):
        marker = "  ✅ (انتخاب شده)" if symbol in current_symbols else ""
        lines.append(f"{i}. {symbol}{marker}")
    lines.append("")
    lines.append("برای تغییر نمادهای مورد نظرت:")
    lines.append("یک ایمیل جدید با موضوع دقیق SELECT SYMBOLS بفرست")
    lines.append("و در متنش شماره‌ی نمادهای دلخواه رو با ویرگول جدا کن، مثلا: 1, 4, 10")
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
    safe_name = symbol.replace("/", "_")
    chart_path = os.path.join(CHARTS_DIR, f"{safe_name}.png")

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
    chart_paths = []

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
            chart_paths.append(chart_path)

    lines.append(build_symbol_catalog_text(symbols))

    return "\n".join(lines), new_history, series, chart_paths


# ---------------------------------------------------------------
# گزارش هفتگی (پنجشنبه‌ها)
# ---------------------------------------------------------------

def is_thursday():
    return datetime.now().weekday() == 3


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
# ارسال ایمیل
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
# بخش جدید: ارسال پیام و عکس به تلگرام
# ---------------------------------------------------------------

def send_telegram_message(token, chat_id, text):
    """
    یک پیام متنی به چت تلگرام می‌فرسته.
    چون تلگرام محدودیت طول پیام داره (۴۰۹۶ کاراکتر)، اگه متن خیلی طولانی بود، قطعش می‌کنیم.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    text = text[:4000]  # ایمنی در برابر پیام‌های خیلی طولانی
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
        if response.status_code == 200:
            return True, None
        return False, f"کد وضعیت: {response.status_code} - {response.text}"
    except Exception as e:
        return False, str(e)


def send_telegram_photo(token, chat_id, photo_path, caption=""):
    """یک تصویر (مثلا نمودار) رو به چت تلگرام می‌فرسته."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption[:1024]}
            response = requests.post(url, data=data, files=files, timeout=20)
        if response.status_code == 200:
            return True, None
        return False, f"کد وضعیت: {response.status_code} - {response.text}"
    except Exception as e:
        return False, str(e)


def send_telegram_report(token, chat_id, text, image_paths=None):
    """
    گزارش رو به تلگرام می‌فرسته: اول متن، بعد هر کدوم از نمودارها به‌عنوان عکس جدا.
    """
    image_paths = image_paths or []

    text_ok, text_error = send_telegram_message(token, chat_id, text)

    photo_errors = []
    for img_path in image_paths:
        symbol_name = os.path.splitext(os.path.basename(img_path))[0].replace("_", "/")
        photo_ok, photo_error = send_telegram_photo(token, chat_id, img_path, caption=symbol_name)
        if not photo_ok:
            photo_errors.append(f"{symbol_name}: {photo_error}")

    if not text_ok:
        return False, f"ارسال متن ناموفق: {text_error}"
    if photo_errors:
        return False, "خطا در ارسال بعضی عکس‌ها: " + " | ".join(photo_errors)
    return True, None


def main():
    config = load_symbols_config()
    api_key = get_required_env("TWELVE_DATA_API_KEY")
    sender_email = get_required_env("GMAIL_SENDER_EMAIL")
    app_password = get_required_env("GMAIL_APP_PASSWORD")
    receiver_email = get_required_env("GMAIL_RECEIVER_EMAIL")
    telegram_token = get_required_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = get_required_env("TELEGRAM_CHAT_ID")

    config, updated_symbols = check_symbol_selection_email(config, sender_email, app_password)

    if updated_symbols:
        print(f"✅ نمادها طبق درخواست ایمیلی به‌روزرسانی شدن: {', '.join(updated_symbols)}")
        confirm_text = f"نمادهای جدید ثبت شد:\n\n{chr(10).join(updated_symbols)}\n\nاز فردا گزارش‌ها بر همین اساس ارسال می‌شن."
        send_email(
            subject="✅ نمادهای شما به‌روزرسانی شد",
            body=confirm_text,
            sender=sender_email,
            password=app_password,
            receiver=receiver_email
        )
        send_telegram_message(telegram_token, telegram_chat_id, "✅ " + confirm_text)

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

    print("\n📧 در حال ارسال گزارش روزانه با ایمیل...")
    email_success, email_error = send_email(
        subject="📊 گزارش روزانه ربات فارکس",
        body=report_text,
        sender=sender_email,
        password=app_password,
        receiver=receiver_email,
        image_paths=chart_paths
    )
    if email_success:
        print(f"✅ ایمیل روزانه با موفقیت به {receiver_email} ارسال شد!")
    else:
        print(f"❌ ارسال ایمیل روزانه ناموفق بود. خطا: {email_error}")

    print("\n📲 در حال ارسال گزارش روزانه به تلگرام...")
    tg_success, tg_error = send_telegram_report(telegram_token, telegram_chat_id, report_text, chart_paths)
    if tg_success:
        print("✅ گزارش روزانه با موفقیت به تلگرام ارسال شد!")
    else:
        print(f"❌ ارسال گزارش تلگرام ناموفق بود. خطا: {tg_error}")

    if is_thursday():
        print("\n📅 امروز پنجشنبه است، در حال ساخت گزارش هفتگی...")
        weekly_text = build_weekly_summary(symbols, new_series)
        print(weekly_text)

        weekly_email_success, weekly_email_error = send_email(
            subject="📅 خلاصه‌ی هفتگی ربات فارکس",
            body=weekly_text,
            sender=sender_email,
            password=app_password,
            receiver=receiver_email
        )
        if weekly_email_success:
            print("✅ ایمیل خلاصه‌ی هفتگی هم با موفقیت ارسال شد!")
        else:
            print(f"❌ ارسال ایمیل هفتگی ناموفق بود. خطا: {weekly_email_error}")

        weekly_tg_success, weekly_tg_error = send_telegram_message(
            telegram_token, telegram_chat_id, weekly_text
        )
        if weekly_tg_success:
            print("✅ خلاصه‌ی هفتگی هم با موفقیت به تلگرام ارسال شد!")
        else:
            print(f"❌ ارسال خلاصه‌ی هفتگی به تلگرام ناموفق بود. خطا: {weekly_tg_error}")


if __name__ == "__main__":
    main()
