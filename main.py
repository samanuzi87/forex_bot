"""
ربات تحلیل‌گر فارکس - مرحله ۶: افزودن نمودار روند قیمت به ایمیل
این اسکریپت:
1) اگه هنوز نمادهای مورد علاقه‌ت مشخص نشده باشه، ازت می‌پرسه.
2) قیمت لحظه‌ای نمادها رو از Twelve Data می‌گیره.
3) قیمت امروز رو با آخرین قیمت ذخیره‌شده (روز قبل) مقایسه می‌کنه و هشدار می‌ده.
4) یک سابقه‌ی چندروزه از قیمت هر نماد نگه می‌داره (برای رسم نمودار).
5) یک نمودار ساده‌ی روند قیمت برای هر نماد می‌سازد.
6) کل گزارش + نمودارها رو با ایمیل برات می‌فرسته.
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # چون سرور بدون صفحه‌نمایشه، از این حالت غیرتعاملی استفاده می‌کنیم
import matplotlib.pyplot as plt

ALERT_THRESHOLD_PERCENT = 0.5
HISTORY_FILE = "price_history.json"      # آخرین قیمت هر نماد (برای مقایسه‌ی روزانه)
SERIES_FILE = "price_series.json"        # سابقه‌ی چندروزه‌ی هر نماد (برای نمودار)
MAX_HISTORY_POINTS = 30                  # حداکثر تعداد روزهایی که برای نمودار نگه می‌داریم
CHARTS_DIR = "charts"                    # پوشه‌ای که تصاویر نمودار موقتاً توش ذخیره می‌شن
SYMBOLS_FILE = "config.json"


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


def ask_preferred_symbols(config):
    print("\n👋 سلام! به نظر می‌رسه اولین باره ربات رو اجرا می‌کنی.")
    print("لطفاً نمادهایی که بیشتر روشون ترید می‌کنی رو با ویرگول (,) از هم جدا کن.")
    print("مثال: EUR/USD, GBP/USD, XAU/USD, USD/JPY\n")

    user_input = input("نمادهای مورد نظرت: ").strip()
    symbols = [s.strip().upper() for s in user_input.split(",") if s.strip()]

    if not symbols:
        print("⚠️  چیزی وارد نکردی، فعلاً از نمادهای پیش‌فرض استفاده می‌کنیم.")
        symbols = config["symbols"]

    config["symbols"] = symbols
    config["symbols_confirmed"] = True
    save_symbols_config(config)

    print(f"\n✅ ذخیره شد! از این به بعد ربات فقط این نمادها رو چک می‌کنه: {', '.join(symbols)}\n")
    return config


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
    """
    یک نقطه‌ی قیمت جدید (امروز) رو به سابقه‌ی اون نماد اضافه می‌کنه.
    فقط آخرین MAX_HISTORY_POINTS روز رو نگه می‌داره تا فایل بی‌نهایت بزرگ نشه.
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    points = series.get(symbol, [])
    points.append({"time": today, "price": price})
    points = points[-MAX_HISTORY_POINTS:]
    series[symbol] = points
    return series


def build_chart(symbol, series):
    """
    یک نمودار خط ساده از روند قیمت یک نماد می‌سازد و به‌عنوان فایل PNG ذخیره می‌کند.
    خروجی: مسیر فایل تصویر، یا None اگه داده‌ی کافی برای رسم نمودار نبود.
    """
    points = series.get(symbol, [])

    if len(points) < 2:
        # با کمتر از ۲ نقطه، رسم نمودار روند معنی نداره
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

    return "\n".join(lines), new_history, series, chart_paths


def send_email(subject, body, sender, password, receiver, image_paths=None):
    """
    یک ایمیل با متن گزارش و (در صورت وجود) نمودارهای پیوست‌شده ارسال می‌کند.
    """
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

    if not config.get("symbols_confirmed", False):
        config = ask_preferred_symbols(config)

    symbols = config["symbols"]
    history = load_json_file(HISTORY_FILE)
    series = load_json_file(SERIES_FILE)

    report_text, new_history, new_series, chart_paths = build_report_text(
        symbols, api_key, history, series
    )

    print(report_text)
    print(f"\n📈 تعداد نمودارهای ساخته‌شده: {len(chart_paths)}")

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
        print(f"✅ ایمیل (همراه با {len(chart_paths)} نمودار) با موفقیت به {receiver_email} ارسال شد!")
    else:
        print(f"❌ ارسال ایمیل ناموفق بود. خطا: {error}")


if __name__ == "__main__":
    main()
