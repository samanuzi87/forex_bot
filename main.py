"""
ربات تحلیل‌گر فارکس - مرحله ۱۱: پشتیبانی چندزبانه + حذف تغییر نماد از ایمیل
این اسکریپت:
1) تنظیمات (نمادها، روز هفتگی، زبان) رو از سرور تلگرام (PythonAnywhere) می‌گیره.
2) قیمت لحظه‌ای نمادها رو می‌گیره، تحلیل می‌کنه، نمودار (به زبان انتخابی) می‌سازه.
3) گزارش رو با ایمیل (فقط متن + عکس، بدون قابلیت پاسخ‌دهی) و تلگرام می‌فرسته.
4) توی تلگرام: پیام قبلی رو پاک می‌کنه، برای هر نماد یه دکمه‌ی نمودار جدا می‌ذاره.
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from translations import t, weekday_name, RTL_LANGUAGES, LANGUAGE_NAMES, SUPPORTED_LANGUAGES

ALERT_THRESHOLD_PERCENT = 0.5
HISTORY_FILE = "price_history.json"
SERIES_FILE = "price_series.json"
MAX_HISTORY_POINTS = 30
CHARTS_DIR = "charts"
SYMBOLS_FILE = "config.json"
DEFAULT_WEEKLY_WEEKDAY = 3
DEFAULT_LANGUAGE = "fa"


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
# هماهنگی تنظیمات با سرور تلگرام (PythonAnywhere)
# ---------------------------------------------------------------

def fetch_remote_config(url, token, fallback):
    try:
        response = requests.get(f"{url}/config", params={"token": token}, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"⚠️ سرور تنظیمات پاسخ غیرمنتظره داد (کد {response.status_code})، از نسخه‌ی محلی استفاده می‌شود.")
    except Exception as e:
        print(f"⚠️ اتصال به سرور تنظیمات ناموفق بود: {e} — از نسخه‌ی محلی استفاده می‌شود.")
    return fallback


def push_remote_config(url, token, config):
    try:
        requests.post(f"{url}/config", params={"token": token}, json=config, timeout=15)
    except Exception as e:
        print(f"⚠️ ارسال تنظیمات به سرور PythonAnywhere ناموفق بود: {e}")


# ---------------------------------------------------------------
# گرفتن قیمت، تحلیل
# ---------------------------------------------------------------

def get_price(symbol, api_key):
    url = "https://api.twelvedata.com/price"
    params = {"symbol": symbol, "apikey": api_key}
    response = requests.get(url, params=params)
    data = response.json()

    if "price" not in data:
        return None, data.get("message", "خطای نامشخص")

    return float(data["price"]), None


def analyze_price(symbol, current_price, history, lang):
    previous_price = history.get(symbol)

    if previous_price is None:
        return t(lang, "first_time_note"), False

    change_percent = ((current_price - previous_price) / previous_price) * 100
    sign = "+" if change_percent >= 0 else ""
    change_text = f'{t(lang, "changed_from_last")}: {sign}{change_percent:.2f}%'

    is_alert = abs(change_percent) >= ALERT_THRESHOLD_PERCENT
    if is_alert:
        change_text += " — " + t(lang, "significant_change")

    return change_text, is_alert


def update_series(series, symbol, price):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    points = series.get(symbol, [])
    points.append({"time": today, "price": price})
    points = points[-MAX_HISTORY_POINTS:]
    series[symbol] = points
    return series


# ---------------------------------------------------------------
# ساخت نمودار (با پشتیبانی از راست‌به‌چپ برای فارسی/عربی)
# ---------------------------------------------------------------

def prepare_chart_text(text, lang):
    """
    برای فارسی و عربی، حروف باید به‌هم بچسبن (Shape) و ترتیبشون درست بشه (Bidi)،
    وگرنه matplotlib نمی‌تونه درست نشونشون بده. برای بقیه‌ی زبان‌ها نیازی به این کار نیست.
    """
    if lang not in RTL_LANGUAGES:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        print(f"⚠️ آماده‌سازی متن راست‌به‌چپ ناموفق بود ({e})، متن اصلی استفاده می‌شود.")
        return text


def get_chart_font():
    """اگه فونت مخصوص فارسی/عربی (Noto) نصب باشه، همون رو برمی‌گردونه، وگرنه فونت پیش‌فرض."""
    for font_name in ["Noto Naskh Arabic", "Noto Sans Arabic", "Noto Sans"]:
        matches = [f for f in fm.fontManager.ttflist if font_name.lower() in f.name.lower()]
        if matches:
            return font_name
    return None


def build_chart(symbol, series, lang):
    points = series.get(symbol, [])

    if len(points) < 2:
        return None

    times = [p["time"] for p in points]
    prices = [p["price"] for p in points]

    os.makedirs(CHARTS_DIR, exist_ok=True)
    safe_name = symbol.replace("/", "_")
    chart_path = os.path.join(CHARTS_DIR, f"{safe_name}.png")

    title_text = prepare_chart_text(t(lang, "chart_title", symbol=symbol), lang)

    rtl_font = get_chart_font() if lang in RTL_LANGUAGES else None
    if rtl_font:
        plt.rcParams["font.family"] = rtl_font

    plt.figure(figsize=(7, 3.2))
    plt.plot(times, prices, marker="o", linewidth=2, color="#2b4a6f")
    plt.title(title_text)
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.yticks(fontsize=8)
    plt.tight_layout()
    plt.savefig(chart_path, dpi=120)
    plt.close()

    plt.rcParams["font.family"] = "DejaVu Sans"  # برگردوندن فونت پیش‌فرض برای نمودارهای بعدی
    return chart_path


def build_report_text(symbols, api_key, history, series, lang):
    lines = []
    lines.append(f'{t(lang, "report_title")} - {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append("=" * 50)

    new_history = dict(history)
    chart_paths = {}

    for symbol in symbols:
        price, error = get_price(symbol, api_key)

        if error:
            lines.append(f"❌ {symbol}: {error}")
            continue

        change_text, is_alert = analyze_price(symbol, price, history, lang)
        icon = "⚠️ " if is_alert else "✅"
        lines.append(f"{icon} {symbol}: {price}  ({change_text})")

        new_history[symbol] = price
        update_series(series, symbol, price)

        chart_path = build_chart(symbol, series, lang)
        if chart_path:
            chart_paths[symbol] = chart_path

    return "\n".join(lines), new_history, series, chart_paths


def is_weekly_report_day(config):
    target_day = config.get("weekly_report_weekday", DEFAULT_WEEKLY_WEEKDAY)
    return datetime.now().weekday() == target_day


def build_weekly_summary(symbols, series, lang):
    lines = []
    lines.append(f'📅 {t(lang, "weekly_title")} - {datetime.now().strftime("%Y-%m-%d")}')
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
            lines.append(f'   {t(lang, "weekly_no_data")}')
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

        lines.append(f'   {t(lang, "weekly_min")}: {min_price}')
        lines.append(f'   {t(lang, "weekly_max")}: {max_price}')
        lines.append(f'   {t(lang, "weekly_avg")}: {avg_price:.5f}')
        lines.append(f'   {t(lang, "weekly_change")}: {sign}{change_percent:.2f}%')
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------
# ارسال ایمیل (فقط متن + عکس، بدون قابلیت پاسخ‌دهی)
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
# ارتباط با تلگرام
# ---------------------------------------------------------------

def tg_request(token, method, payload=None, files=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.post(url, data=payload or {}, files=files, timeout=20)
    return response.json()


def delete_telegram_message(token, chat_id, message_id):
    if not message_id:
        return
    try:
        tg_request(token, "deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception as e:
        print(f"⚠️ حذف پیام قبلی ناموفق بود (شاید قبلاً پاک شده): {e}")


def upload_chart_and_get_file_id(token, chat_id, photo_path):
    """
    عکس رو یه‌بار می‌فرسته تا شناسه‌ی داخلی تلگرامش (file_id) رو بگیره،
    بعد فوراً همون پیام رو پاک می‌کنه تا چت شلوغ نشه.
    """
    try:
        with open(photo_path, "rb") as f:
            result = tg_request(token, "sendPhoto", {"chat_id": chat_id}, files={"photo": f})
        if not result.get("ok"):
            return None, str(result)
        message_id = result["result"]["message_id"]
        file_id = result["result"]["photo"][-1]["file_id"]
        delete_telegram_message(token, chat_id, message_id)
        return file_id, None
    except Exception as e:
        return None, str(e)


def build_chart_picker_keyboard(symbols, lang):
    rows, row = [], []
    for symbol in symbols:
        safe_symbol = symbol.replace("/", "_")
        row.append({"text": t(lang, "chart_button", symbol=symbol), "callback_data": f"show_chart:{safe_symbol}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def send_telegram_text(token, chat_id, text, keyboard=None):
    text = text[:4000]
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    try:
        result = tg_request(token, "sendMessage", payload)
        if result.get("ok"):
            return True, result["result"]["message_id"], None
        return False, None, str(result)
    except Exception as e:
        return False, None, str(e)


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

    # همیشه اول آخرین تنظیمات (نماد، روز هفتگی، زبان) رو از سرور تلگرام می‌گیریم
    config = fetch_remote_config(pa_url, pa_secret, fallback=config)
    save_symbols_config(config)

    if not config.get("symbols"):
        config["symbols"] = ["EUR/USD", "XAU/USD"]

    lang = config.get("language", DEFAULT_LANGUAGE)
    symbols = config["symbols"]
    history = load_json_file(HISTORY_FILE)
    series = load_json_file(SERIES_FILE)

    report_text, new_history, new_series, chart_paths = build_report_text(
        symbols, api_key, history, series, lang
    )

    print(report_text)

    save_json_file(new_history, HISTORY_FILE)
    save_json_file(new_series, SERIES_FILE)

    # --- ایمیل: فقط متن + عکس، بدون قابلیت پاسخ‌دهی ---
    print("\n📧 در حال ارسال گزارش روزانه با ایمیل...")
    email_success, email_error = send_email(
        subject=f'📊 {t(lang, "report_title")}',
        body=report_text,
        sender=sender_email,
        password=app_password,
        receiver=receiver_email,
        image_paths=list(chart_paths.values())
    )
    if email_success:
        print(f"✅ ایمیل روزانه با موفقیت به {receiver_email} ارسال شد!")
    else:
        print(f"❌ ارسال ایمیل روزانه ناموفق بود. خطا: {email_error}")

    # --- تلگرام: پاک کردن پیام قبلی، آپلود موقت نمودارها برای گرفتن file_id، ارسال پیام با دکمه‌ی هر نماد ---
    print("\n📲 در حال آماده‌سازی گزارش تلگرام...")
    delete_telegram_message(telegram_token, telegram_chat_id, config.get("last_daily_message_id"))

    chart_file_ids = {}
    for symbol, path in chart_paths.items():
        file_id, err = upload_chart_and_get_file_id(telegram_token, telegram_chat_id, path)
        if file_id:
            chart_file_ids[symbol.replace("/", "_")] = file_id
        else:
            print(f"⚠️ گرفتن file_id برای {symbol} ناموفق بود: {err}")

    keyboard = build_chart_picker_keyboard(symbols, lang)
    tg_ok, new_message_id, tg_error = send_telegram_text(
        telegram_token, telegram_chat_id, report_text, keyboard=keyboard
    )
    if tg_ok:
        print("✅ گزارش روزانه (همراه با دکمه‌ی هر نماد) با موفقیت به تلگرام ارسال شد!")
    else:
        print(f"❌ ارسال گزارش تلگرام ناموفق بود. خطا: {tg_error}")

    config["last_daily_message_id"] = new_message_id
    config["chart_file_ids"] = chart_file_ids

    # --- گزارش هفتگی (روز قابل‌تنظیم) ---
    if is_weekly_report_day(config):
        day_name = weekday_name(lang, config.get("weekly_report_weekday", DEFAULT_WEEKLY_WEEKDAY))
        print(f"\n📅 امروز {day_name} است، در حال ساخت گزارش هفتگی...")
        weekly_text = build_weekly_summary(symbols, new_series, lang)
        print(weekly_text)

        weekly_email_success, weekly_email_error = send_email(
            subject=f'📅 {t(lang, "weekly_title")}',
            body=weekly_text,
            sender=sender_email,
            password=app_password,
            receiver=receiver_email
        )
        if weekly_email_success:
            print("✅ ایمیل خلاصه‌ی هفتگی هم با موفقیت ارسال شد!")
        else:
            print(f"❌ ارسال ایمیل هفتگی ناموفق بود. خطا: {weekly_email_error}")

        delete_telegram_message(telegram_token, telegram_chat_id, config.get("last_weekly_message_id"))
        weekly_tg_ok, weekly_message_id, weekly_tg_error = send_telegram_text(
            telegram_token, telegram_chat_id, weekly_text
        )
        if weekly_tg_ok:
            print("✅ خلاصه‌ی هفتگی هم با موفقیت به تلگرام ارسال شد!")
            config["last_weekly_message_id"] = weekly_message_id
        else:
            print(f"❌ ارسال خلاصه‌ی هفتگی به تلگرام ناموفق بود. خطا: {weekly_tg_error}")

    # --- هماهنگ‌سازی نهایی تنظیمات (شناسه‌ی پیام‌ها، file_idها) با سرور تلگرام ---
    push_remote_config(pa_url, pa_secret, config)
    save_symbols_config(config)


if __name__ == "__main__":
    main()
