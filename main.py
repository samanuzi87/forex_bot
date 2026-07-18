"""
ربات تحلیل‌گر فارکس - مرحله ۷: انتخاب نماد از طریق پاسخ ایمیل
این اسکریپت:
1) قبل از هر گزارش، صندوق ورودی جیمیل رو چک می‌کنه ببینه ایمیلی با موضوع
   "SELECT SYMBOLS" اومده یا نه؛ اگه اومده، نمادها رو طبق شماره‌های داخلش تغییر می‌ده.
2) قیمت لحظه‌ای نمادهای انتخاب‌شده رو از Twelve Data می‌گیره.
3) قیمت امروز رو با روز قبل مقایسه و در صورت تغییر زیاد هشدار می‌ده.
4) یک نمودار روند قیمت برای هر نماد می‌سازد.
5) گزارش کامل (متن + نمودارها + لیست نمادهای قابل‌انتخاب) رو با ایمیل می‌فرسته.
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
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ALERT_THRESHOLD_PERCENT = 0.5
HISTORY_FILE = "price_history.json"
SERIES_FILE = "price_series.json"
MAX_HISTORY_POINTS = 30
CHARTS_DIR = "charts"
SYMBOLS_FILE = "config.json"

# لیست نمادهایی که کاربر می‌تونه از بینشون انتخاب کنه (می‌تونی بعداً بیشترش کنی)
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
# بخش جدید: خوندن ایمیل درخواست تغییر نماد از صندوق ورودی
# ---------------------------------------------------------------

def check_symbol_selection_email(config, sender_email, app_password):
    """
    صندوق ورودی جیمیل رو برای ایمیل خوانده‌نشده با موضوع "SELECT SYMBOLS" می‌گرده.
    اگه پیدا کرد، شماره‌های داخل متن ایمیل رو استخراج می‌کنه، به نماد تبدیل می‌کنه،
    و config رو به‌روزرسانی می‌کنه.
    خروجی: (config به‌روزشده, لیست نمادهای جدید یا None اگه چیزی تغییر نکرد)
    """
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(sender_email, app_password)
        imap.select("INBOX")

        status, data = imap.search(None, '(UNSEEN SUBJECT "SELECT SYMBOLS")')
        if status != "OK" or not data[0]:
            imap.logout()
            return config, None

        email_ids = data[0].split()
        latest_id = email_ids[-1]  # فقط جدیدترین درخواست رو در نظر می‌گیریم

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

        # همه‌ی عددهای داخل متن ایمیل رو استخراج می‌کنیم (مثلا از "1, 4, 10")
        numbers = [int(n) for n in re.findall(r"\d+", body)]
        selected_symbols = [
            SYMBOL_CATALOG[n - 1] for n in numbers
            if 1 <= n <= len(SYMBOL_CATALOG)
        ]
        # حذف تکراری‌ها با حفظ ترتیب
        selected_symbols = list(dict.fromkeys(selected_symbols))

        # این ایمیل رو خونده‌شده علامت می‌زنیم تا دوباره پردازش نشه
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
    """
    متن لیست نمادهای قابل‌انتخاب رو می‌سازه، تا در پایین هر گزارش نشون داده بشه.
    """
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
# بخش‌های قبلی: گرفتن قیمت، تحلیل، نمودار، ارسال ایمیل
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


def main():
    config = load_symbols_config()
    api_key = get_required_env("TWELVE_DATA_API_KEY")
    sender_email = get_required_env("GMAIL_SENDER_EMAIL")
    app_password = get_required_env("GMAIL_APP_PASSWORD")
    receiver_email = get_required_env("GMAIL_RECEIVER_EMAIL")

    # قدم ۱: بررسی این‌که آیا کاربر ایمیلی برای تغییر نماد فرستاده
    config, updated_symbols = check_symbol_selection_email(config, sender_email, app_password)

    if updated_symbols:
        print(f"✅ نمادها طبق درخواست ایمیلی به‌روزرسانی شدن: {', '.join(updated_symbols)}")
        send_email(
            subject="✅ نمادهای شما به‌روزرسانی شد",
            body=f"نمادهای جدید ثبت شد:\n\n{chr(10).join(updated_symbols)}\n\nاز فردا گزارش‌ها بر همین اساس ارسال می‌شن.",
            sender=sender_email,
            password=app_password,
            receiver=receiver_email
        )

    # اگه هنوز هیچ نمادی (نه از قبل، نه از ایمیل) مشخص نشده، از نمادهای پیش‌فرض استفاده می‌کنیم
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

    print("\n📧 در حال ارسال گزارش با ایمیل...")
    success, error = send_email(
        subject="📊 گزارش روزانه ربات فارکس",
        body=report_text,
        sender=sender_email,
        password=app_password,
        receiver=receiver_email,
        image_paths=chart_paths
    )

    if success:
        print(f"✅ ایمیل با موفقیت به {receiver_email} ارسال شد!")
    else:
        print(f"❌ ارسال ایمیل ناموفق بود. خطا: {error}")


if __name__ == "__main__":
    main()
