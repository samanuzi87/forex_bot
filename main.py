"""
ربات تحلیل‌گر فارکس - مرحله ۵: آماده‌سازی برای GitHub Actions
این نسخه به‌جای خوندن کلید API و رمز ایمیل از config.json،
اون‌ها رو از "متغیرهای محیطی" (Environment Variables) می‌خونه.
این‌کار باعث می‌شه بتونیم کد رو امن روی GitHub آپلود کنیم،
بدون این‌که هیچ رمزی داخل خود فایل‌ها نوشته شده باشه.

متغیرهای محیطی مورد نیاز (که بعداً به‌عنوان GitHub Secrets تنظیم می‌کنیم):
- TWELVE_DATA_API_KEY
- GMAIL_SENDER_EMAIL
- GMAIL_APP_PASSWORD
- GMAIL_RECEIVER_EMAIL
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
import requests
from datetime import datetime

ALERT_THRESHOLD_PERCENT = 0.5
HISTORY_FILE = "price_history.json"
SYMBOLS_FILE = "config.json"


def load_symbols_config(path=SYMBOLS_FILE):
    """
    فقط اطلاعات غیرحساس (لیست نمادها) رو از config.json می‌خونه.
    دیگه هیچ رمز یا کلیدی اینجا نیست.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_symbols_config(config, path=SYMBOLS_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_history(path=HISTORY_FILE):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history, path=HISTORY_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_required_env(name):
    """
    یه متغیر محیطی رو می‌خونه. اگه وجود نداشت، پیام خطای واضح می‌ده
    (به‌جای این‌که برنامه بدون توضیح کرش کنه).
    """
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"متغیر محیطی '{name}' تنظیم نشده. "
            f"روی گیت‌هاب باید توی Settings > Secrets and variables > Actions اضافه بشه، "
            f"یا برای تست روی سیستم خودت، قبل از اجرا با دستور 'set {name}=مقدار' (ویندوز) تنظیمش کنی."
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


def build_report_text(symbols, api_key, history):
    lines = []
    lines.append(f"گزارش قیمت نمادها - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    new_history = dict(history)

    for symbol in symbols:
        price, error = get_price(symbol, api_key)

        if error:
            lines.append(f"❌ {symbol}: خطا -> {error}")
            continue

        change_text, is_alert = analyze_price(symbol, price, history)
        icon = "⚠️ " if is_alert else "✅"
        lines.append(f"{icon} {symbol}: {price}  ({change_text})")

        new_history[symbol] = price

    return "\n".join(lines), new_history


def send_email(subject, body, sender, password, receiver):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    # روش اول: اتصال امن مستقیم (SSL) روی پورت 465
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        return True, None
    except Exception as first_error:
        # روش دوم: STARTTLS روی پورت 587
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, receiver, msg.as_string())
            return True, None
        except Exception as second_error:
            return False, f"روش اول (پورت 465): {first_error}\nروش دوم (پورت 587): {second_error}"


def main():
    # --- خوندن نمادها از config.json (غیرحساس) ---
    config = load_symbols_config()

    if not config.get("symbols_confirmed", False):
        config = ask_preferred_symbols(config)

    symbols = config["symbols"]

    # --- خوندن اطلاعات حساس از Environment Variables ---
    api_key = get_required_env("TWELVE_DATA_API_KEY")
    sender_email = get_required_env("GMAIL_SENDER_EMAIL")
    app_password = get_required_env("GMAIL_APP_PASSWORD")
    receiver_email = get_required_env("GMAIL_RECEIVER_EMAIL")

    history = load_history()
    report_text, new_history = build_report_text(symbols, api_key, history)

    print(report_text)
    save_history(new_history)

    print("\n📧 در حال ارسال گزارش با ایمیل...")
    success, error = send_email(
        subject="📊 گزارش روزانه ربات فارکس",
        body=report_text,
        sender=sender_email,
        password=app_password,
        receiver=receiver_email
    )

    if success:
        print(f"✅ ایمیل با موفقیت به {receiver_email} ارسال شد!")
    else:
        print(f"❌ ارسال ایمیل ناموفق بود. خطا: {error}")


if __name__ == "__main__":
    main()
