# -*- coding: utf-8 -*-
"""
فایل مرکزی ترجمه‌ها.
این فایل باید هم داخل مخزن گیت‌هاب (کنار main.py)، هم داخل پوشه‌ی
mysite روی PythonAnywhere (کنار telegram_server.py) آپلود بشه، چون هر
دو سرویس ازش استفاده می‌کنن.
"""

SUPPORTED_LANGUAGES = ["fa", "en", "tr", "es", "ar", "fr"]

LANGUAGE_NAMES = {
    "fa": {"fa": "فارسی", "en": "انگلیسی", "tr": "ترکی استانبولی", "es": "اسپانیایی", "ar": "عربی", "fr": "فرانسوی"},
    "en": {"fa": "Persian", "en": "English", "tr": "Turkish", "es": "Spanish", "ar": "Arabic", "fr": "French"},
    "tr": {"fa": "Farsça", "en": "İngilizce", "tr": "Türkçe", "es": "İspanyolca", "ar": "Arapça", "fr": "Fransızca"},
    "es": {"fa": "Persa", "en": "Inglés", "tr": "Turco", "es": "Español", "ar": "Árabe", "fr": "Francés"},
    "ar": {"fa": "الفارسية", "en": "الإنجليزية", "tr": "التركية", "es": "الإسبانية", "ar": "العربية", "fr": "الفرنسية"},
    "fr": {"fa": "Persan", "en": "Anglais", "tr": "Turc", "es": "Espagnol", "ar": "Arabe", "fr": "Français"},
}

# نام روزهای هفته برای هرکدوم از زبان‌ها (کلید = شماره‌ی weekday() پایتون)
WEEKDAY_NAMES = {
    "fa": {5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه"},
    "en": {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"},
    "tr": {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"},
    "es": {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"},
    "ar": {0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس", 4: "الجمعة", 5: "السبت", 6: "الأحد"},
    "fr": {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"},
}

# ترتیب نمایش دکمه‌های روز هفته (فارسی از شنبه شروع می‌شه، بقیه از دوشنبه)
WEEKDAY_ORDER = {
    "fa": [5, 6, 0, 1, 2, 3, 4],
    "en": [0, 1, 2, 3, 4, 5, 6],
    "tr": [0, 1, 2, 3, 4, 5, 6],
    "es": [0, 1, 2, 3, 4, 5, 6],
    "ar": [0, 1, 2, 3, 4, 5, 6],
    "fr": [0, 1, 2, 3, 4, 5, 6],
}

# زبان‌هایی که راست‌به‌چپ هستن و نیاز به آماده‌سازی مخصوص متن (reshape) دارن
RTL_LANGUAGES = {"fa", "ar"}

TEXTS = {
    "fa": {
        "report_title": "گزارش قیمت نمادها",
        "changed_from_last": "تغییر نسبت به دفعه قبل",
        "first_time_note": "اولین بار ثبت می‌شه، فردا مقایسه‌ش می‌کنیم",
        "significant_change": "تغییر قابل توجه!",
        "weekly_title": "خلاصه‌ی هفتگی ربات فارکس",
        "weekly_min": "کمترین قیمت هفته",
        "weekly_max": "بیشترین قیمت هفته",
        "weekly_avg": "میانگین قیمت هفته",
        "weekly_change": "تغییر از اول تا امروز",
        "weekly_no_data": "داده‌ی کافی برای این هفته هنوز جمع نشده.",
        "chart_title": "روند قیمت {symbol}",
        "symbols_prompt": "نمادهای مورد نظرت رو انتخاب کن:",
        "weekday_prompt": "روز فعلی گزارش هفتگی: {day}\nروز جدید رو انتخاب کن:",
        "language_prompt": "زبان مورد نظرت رو انتخاب کن:",
        "confirm_ok": "✅ نمادها ذخیره شدن:",
        "confirm_none": "⚠️ هیچ نمادی انتخاب نشده بود، چیزی تغییر نکرد.",
        "cancel_msg": "لغو شد، چیزی تغییر نکرد.",
        "weekday_set": "✅ روز گزارش هفتگی تغییر کرد به: {day}",
        "language_set": "✅ زبان ربات تغییر کرد به: {lang_name}",
        "start_message": "سلام! ربات فارکس آماده‌ست 🤖\n\nدستورات همیشگی:\n/symbols — تغییر نمادهای مورد علاقه\n/weekday — تغییر روز گزارش هفتگی\n/language — تغییر زبان ربات",
        "chart_missing": "⚠️ نموداری برای این نماد هنوز موجود نیست.",
        "confirm_button": "✅ تایید نهایی",
        "cancel_button": "❌ لغو",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (انتخاب شده)",
    },
    "en": {
        "report_title": "Symbol Price Report",
        "changed_from_last": "Change vs last time",
        "first_time_note": "First time recorded, we'll compare tomorrow",
        "significant_change": "Significant change!",
        "weekly_title": "Forex Bot Weekly Summary",
        "weekly_min": "Weekly low",
        "weekly_max": "Weekly high",
        "weekly_avg": "Weekly average",
        "weekly_change": "Change since start of week",
        "weekly_no_data": "Not enough data for this week yet.",
        "chart_title": "{symbol} Price Trend",
        "symbols_prompt": "Choose your preferred symbols:",
        "weekday_prompt": "Current weekly report day: {day}\nChoose a new day:",
        "language_prompt": "Choose your preferred language:",
        "confirm_ok": "✅ Symbols saved:",
        "confirm_none": "⚠️ No symbol was selected, nothing changed.",
        "cancel_msg": "Cancelled, nothing changed.",
        "weekday_set": "✅ Weekly report day changed to: {day}",
        "language_set": "✅ Bot language changed to: {lang_name}",
        "start_message": "Hi! The Forex bot is ready 🤖\n\nAlways-available commands:\n/symbols — change your favorite symbols\n/weekday — change weekly report day\n/language — change bot language",
        "chart_missing": "⚠️ No chart available for this symbol yet.",
        "confirm_button": "✅ Confirm",
        "cancel_button": "❌ Cancel",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (selected)",
    },
    "tr": {
        "report_title": "Sembol Fiyat Raporu",
        "changed_from_last": "Bir önceki ile karşılaştırma",
        "first_time_note": "İlk kez kaydedildi, yarın karşılaştırılacak",
        "significant_change": "Önemli değişiklik!",
        "weekly_title": "Forex Bot Haftalık Özet",
        "weekly_min": "Haftalık en düşük",
        "weekly_max": "Haftalık en yüksek",
        "weekly_avg": "Haftalık ortalama",
        "weekly_change": "Hafta başından bu yana değişim",
        "weekly_no_data": "Bu hafta için henüz yeterli veri yok.",
        "chart_title": "{symbol} Fiyat Trendi",
        "symbols_prompt": "Tercih ettiğin sembolleri seç:",
        "weekday_prompt": "Mevcut haftalık rapor günü: {day}\nYeni bir gün seç:",
        "language_prompt": "Tercih ettiğin dili seç:",
        "confirm_ok": "✅ Semboller kaydedildi:",
        "confirm_none": "⚠️ Hiçbir sembol seçilmedi, bir şey değişmedi.",
        "cancel_msg": "İptal edildi, bir şey değişmedi.",
        "weekday_set": "✅ Haftalık rapor günü şuna değiştirildi: {day}",
        "language_set": "✅ Bot dili şuna değiştirildi: {lang_name}",
        "start_message": "Merhaba! Forex bot hazır 🤖\n\nHer zaman kullanılabilir komutlar:\n/symbols — favori sembollerini değiştir\n/weekday — haftalık rapor gününü değiştir\n/language — bot dilini değiştir",
        "chart_missing": "⚠️ Bu sembol için henüz grafik yok.",
        "confirm_button": "✅ Onayla",
        "cancel_button": "❌ İptal",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (seçildi)",
    },
    "es": {
        "report_title": "Informe de Precios de Símbolos",
        "changed_from_last": "Cambio respecto a la última vez",
        "first_time_note": "Registrado por primera vez, compararemos mañana",
        "significant_change": "¡Cambio significativo!",
        "weekly_title": "Resumen Semanal del Bot Forex",
        "weekly_min": "Mínimo semanal",
        "weekly_max": "Máximo semanal",
        "weekly_avg": "Promedio semanal",
        "weekly_change": "Cambio desde el inicio de la semana",
        "weekly_no_data": "Aún no hay suficientes datos para esta semana.",
        "chart_title": "Tendencia de precio de {symbol}",
        "symbols_prompt": "Elige tus símbolos preferidos:",
        "weekday_prompt": "Día actual del informe semanal: {day}\nElige un nuevo día:",
        "language_prompt": "Elige tu idioma preferido:",
        "confirm_ok": "✅ Símbolos guardados:",
        "confirm_none": "⚠️ No se seleccionó ningún símbolo, nada cambió.",
        "cancel_msg": "Cancelado, nada cambió.",
        "weekday_set": "✅ Día del informe semanal cambiado a: {day}",
        "language_set": "✅ Idioma del bot cambiado a: {lang_name}",
        "start_message": "¡Hola! El bot de Forex está listo 🤖\n\nComandos siempre disponibles:\n/symbols — cambiar tus símbolos favoritos\n/weekday — cambiar el día del informe semanal\n/language — cambiar el idioma del bot",
        "chart_missing": "⚠️ Todavía no hay gráfico para este símbolo.",
        "confirm_button": "✅ Confirmar",
        "cancel_button": "❌ Cancelar",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (seleccionado)",
    },
    "ar": {
        "report_title": "تقرير أسعار الرموز",
        "changed_from_last": "التغيير عن المرة السابقة",
        "first_time_note": "تم التسجيل لأول مرة، سنقارن غدًا",
        "significant_change": "تغيير ملحوظ!",
        "weekly_title": "الملخص الأسبوعي لبوت الفوركس",
        "weekly_min": "أدنى سعر هذا الأسبوع",
        "weekly_max": "أعلى سعر هذا الأسبوع",
        "weekly_avg": "متوسط السعر هذا الأسبوع",
        "weekly_change": "التغيير منذ بداية الأسبوع",
        "weekly_no_data": "لا توجد بيانات كافية لهذا الأسبوع بعد.",
        "chart_title": "اتجاه سعر {symbol}",
        "symbols_prompt": "اختر الرموز التي تفضلها:",
        "weekday_prompt": "يوم التقرير الأسبوعي الحالي: {day}\nاختر يومًا جديدًا:",
        "language_prompt": "اختر لغتك المفضلة:",
        "confirm_ok": "✅ تم حفظ الرموز:",
        "confirm_none": "⚠️ لم يتم اختيار أي رمز، لم يتغير شيء.",
        "cancel_msg": "تم الإلغاء، لم يتغير شيء.",
        "weekday_set": "✅ تم تغيير يوم التقرير الأسبوعي إلى: {day}",
        "language_set": "✅ تم تغيير لغة البوت إلى: {lang_name}",
        "start_message": "مرحبًا! بوت الفوركس جاهز 🤖\n\nالأوامر المتاحة دائمًا:\n/symbols — تغيير الرموز المفضلة لديك\n/weekday — تغيير يوم التقرير الأسبوعي\n/language — تغيير لغة البوت",
        "chart_missing": "⚠️ لا يوجد رسم بياني لهذا الرمز بعد.",
        "confirm_button": "✅ تأكيد",
        "cancel_button": "❌ إلغاء",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (مختار)",
    },
    "fr": {
        "report_title": "Rapport des Prix des Symboles",
        "changed_from_last": "Variation par rapport à la dernière fois",
        "first_time_note": "Enregistré pour la première fois, comparaison demain",
        "significant_change": "Changement significatif !",
        "weekly_title": "Résumé Hebdomadaire du Bot Forex",
        "weekly_min": "Plus bas de la semaine",
        "weekly_max": "Plus haut de la semaine",
        "weekly_avg": "Moyenne de la semaine",
        "weekly_change": "Variation depuis le début de la semaine",
        "weekly_no_data": "Pas encore assez de données pour cette semaine.",
        "chart_title": "Tendance du prix de {symbol}",
        "symbols_prompt": "Choisissez vos symboles préférés :",
        "weekday_prompt": "Jour actuel du rapport hebdomadaire : {day}\nChoisissez un nouveau jour :",
        "language_prompt": "Choisissez votre langue préférée :",
        "confirm_ok": "✅ Symboles enregistrés :",
        "confirm_none": "⚠️ Aucun symbole sélectionné, rien n'a changé.",
        "cancel_msg": "Annulé, rien n'a changé.",
        "weekday_set": "✅ Jour du rapport hebdomadaire changé en : {day}",
        "language_set": "✅ Langue du bot changée en : {lang_name}",
        "start_message": "Salut ! Le bot Forex est prêt 🤖\n\nCommandes toujours disponibles :\n/symbols — changer vos symboles préférés\n/weekday — changer le jour du rapport hebdomadaire\n/language — changer la langue du bot",
        "chart_missing": "⚠️ Aucun graphique disponible pour ce symbole pour l'instant.",
        "confirm_button": "✅ Confirmer",
        "cancel_button": "❌ Annuler",
        "chart_button": "📈 {symbol}",
        "selected_mark": "✅ (sélectionné)",
    },
}


def t(lang, key, **kwargs):
    """یک متن ترجمه‌شده رو برمی‌گردونه. اگه زبان یا کلید پیدا نشد، از فارسی استفاده می‌کنه."""
    lang = lang if lang in TEXTS else "fa"
    text = TEXTS[lang].get(key, TEXTS["fa"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text


def weekday_name(lang, day_num):
    lang = lang if lang in WEEKDAY_NAMES else "fa"
    return WEEKDAY_NAMES[lang].get(day_num, "?")
