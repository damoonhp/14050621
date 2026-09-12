# CodexBot — Telegram Signal-Only Edition

این نسخه فقط **سیگنال** می‌دهد. هیچ API key صرافی لازم نیست و هیچ endpoint معاملاتی فراخوانی نمی‌شود.

## امکانات
- Telegram private access + manual admin approval.
- Referral URL/code configurable. توجه: کد رفرال به‌تنهایی اثبات فنی عضویت نیست؛ تأیید نهایی توسط Admin انجام می‌شود مگر اینکه دسترسی Affiliate معتبر Toobit برای راستی‌آزمایی اضافه شود.
- Spot / Futures / Both.
- انتخاب نمادها، timeframe و حداقل score.
- استراتژی `Ensemble` مستقل؛ استراتژی‌های موجود CodexBot برای Futures حذف نشده‌اند و می‌توانند جداگانه یا همراه Ensemble اجرا شوند.
- Entry / SL / TP1 / TP2 / R:R / Confidence.
- Win Rate از سیگنال‌های حل‌شده محاسبه می‌شود؛ تا 10 نتیجه حل‌شده، N/A نمایش داده می‌شود.
- SQLite persistence.
- اجرای 24/7 مناسب VPS.
- هیچ معامله‌ای انجام نمی‌شود.

## نصب Windows
PowerShell را داخل پوشه پروژه باز کنید:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

فایل `.env` را از روی `.env.example` بسازید و مقدارها را وارد کنید:

```powershell
Copy-Item .env.example .env
notepad .env
```

سپس:

```powershell
python telegram_signal_bot.py
```

## Telegram Bot
در Telegram، `@BotFather`:
1. `/newbot`
2. نام Bot
3. username که به bot ختم شود
4. Token را فقط در `.env` قرار دهید.

`TELEGRAM_ADMIN_IDS` شناسه عددی تلگرام خودتان است. برای پیدا کردن آن می‌توانید موقتاً از یک bot شناسه‌گیر معتبر استفاده کنید؛ Token خودتان را هرگز برای دیگران ارسال نکنید.

نمونه `.env`:

```env
TELEGRAM_BOT_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
TELEGRAM_ADMIN_IDS=123456789
REFERRAL_URL=https://YOUR-TOOBIT-REFERRAL-LINK
REFERRAL_CODE=YOUR_REFERRAL_CODE
POLL_SECONDS=45
MIN_SCORE=70
MIN_RR=2
```

## تأیید کاربر
کاربر `/start` می‌زند و در صورت تنظیم Referral URL لینک دریافت می‌کند. بعد از ثبت‌نام، دوباره `/start` می‌زند. Admin با:

```text
/admin
```

لیست Pending را می‌بیند و با:

```text
/approve CHAT_ID
```

کاربر را تأیید می‌کند.

رد:

```text
/reject CHAT_ID
```

## تنظیمات کاربر
```text
/setmarket spot
/setmarket futures
/setmarket both

/setsymbols BTCUSDT,ETHUSDT,SOLUSDT
/settf 5m
/setscore 70
/settings
/status
/stop
```

برای Futures می‌توانید BTCUSDT بنویسید؛ برنامه آن را به فرمت Toobit یعنی `BTC-SWAP-USDT` تبدیل می‌کند.

## قالب سیگنال
Admin می‌تواند قالب را با `/template` تنظیم کند. متغیرها:

`{market}` `{direction}` `{symbol}` `{timeframe}` `{entry}` `{sl}` `{tp1}` `{tp2}` `{rr}` `{score}` `{winrate}` `{strategy}`

مثال:

```text
/template 🚨 {market} SIGNAL

{direction} {symbol}
⏱ {timeframe}
💰 Entry: {entry}
🛑 SL: {sl}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
⚖️ R:R: {rr}
📊 Score: {score}%
📈 Win Rate: {winrate}
🧠 {strategy}

⚠️ SIGNAL ONLY
```

## اجرای 24/7
کامپیوتر شخصی لازم نیست همیشه روشن باشد. روی VPS ویندوز یا لینوکس اجرا کنید.

### Linux systemd
فایل:

`/etc/systemd/system/codexbot-signal.service`

```ini
[Unit]
Description=CodexBot Telegram Signal Bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/CodexBot-main
ExecStart=/opt/CodexBot-main/.venv/bin/python /opt/CodexBot-main/telegram_signal_bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

سپس:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now codexbot-signal
sudo systemctl status codexbot-signal
journalctl -u codexbot-signal -f
```

## محدودیت مهم Referral
این نسخه عمداً بدون API احراز هویت‌شده Toobit کار می‌کند. بنابراین Referral به‌صورت «درخواست + تأیید دستی Admin» مدیریت می‌شود و ادعای راستی‌آزمایی خودکار عضویت نمی‌کند. اگر حساب Affiliate شما دسترسی API لازم را داشته باشد، می‌توان بعداً ماژول تأیید Affiliate را جداگانه اضافه کرد.

## ایمنی
- هیچ API key/secret صرافی در این برنامه لازم نیست.
- هیچ order endpoint استفاده نمی‌شود.
- این سیستم ابزار پژوهشی/اطلاع‌رسانی است، نه تضمین سود.
