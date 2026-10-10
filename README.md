# Watch Cats 🐈

داشبورد مانیتورینگ زندهٔ [LanCache](https://lancache.net/):
نشان می‌دهد چه سرویسی (Steam، Epic، PlayStation، Xbox، …) در حال **ذخیره** در کش است،
چه سیستم‌هایی در حال **دریافت از کش** هستند، حجم کش هر سرویس، منابع سرور و خطاها.

> *Watch Cats is an independent companion dashboard for LanCache. It is not affiliated with the LanCache project or with any game store. Brand names belong to their owners.*

## وضعیت
نسخهٔ `0.3.0` — API زنده با بروزرسانی ۱ ثانیه‌ای آماده است (بدون رابط گرافیکی). رابط در مرحلهٔ ۴ می‌آید.

## نقشهٔ راه
1. اسکلت پروژه ✅
2. خواندن لاگ‌ها، تشخیص سرویس و دستگاه، ذخیره در SQLite ✅
3. API زنده (بروزرسانی ۱ ثانیه‌ای) و آمار CPU / RAM / شبکه / دیسک ✅
4. رابط گرافیکی (طبق `design/`)
5. هشدارها: درون صفحه، مرورگر، تلگرام (+ اعلان وقتی ترافیک Epic روی HTTPS می‌رود و کش نمی‌شود)
6. بستهٔ Docker و compose (سه کانتینر: DNS، monolithic، داشبورد)
7. نصب با یک خط، بروزرسانی و حذف
8. انتشار image در GHCR با GitHub Actions، نسخهٔ `1.0.0`

## امتحان روی سرور (نسخهٔ ۰.۲.۰)
فقط به Python 3.10 یا جدیدتر نیاز دارد (روی Linux Mint هست):
```bash
docker cp lancache-dns-1:/opt/cache-domains ./cache-domains
PYTHONPATH=src python3 -m watchcats ingest --log-dir ~/lancache/lancache/logs \
  --domains ./cache-domains --db watchcats.db --tz +03:30 --once
PYTHONPATH=src python3 -m watchcats report --db watchcats.db
```

## اجرای API زنده (نسخهٔ ۰.۳.۰)
```bash
PYTHONPATH=src python3 -m watchcats serve --log-dir ~/lancache/lancache/logs \
  --domains ~/lancache/cache-domains --cache-dir ~/lancache/lancache/cache \
  --db watchcats.db --tz +03:30
```
بعد از اجرا: `http://<آی‌پی-سرور>:8088/api/live` (داده‌های زنده) و `/api/summary?hours=24` (خلاصه).
به‌صورت پیش‌فرض فقط آی‌پی‌های شبکهٔ خصوصی (مثل `192.168.x.x`) پذیرفته می‌شن و ورود با رمز هنوز وجود ندارد. پورت 8088 رو از اینترنت باز نکنید (port-forward نکنید).

## ابزار کمکی ویندوز
`tools/windows/epic-http-fix.ps1` — برای هر کامپیوتر ویندوزی یک‌بار اجرا شود تا Epic از HTTP دانلود کند و LanCache بتواند کشش کند.
```powershell
powershell -ExecutionPolicy Bypass -File .\epic-http-fix.ps1
```

## نسخه‌بندی و توسعه
[Semantic Versioning](https://semver.org/) — جزئیات در [CONTRIBUTING.md](CONTRIBUTING.md) و [CHANGELOG.md](CHANGELOG.md).

## لایسنس
[MIT](LICENSE)
