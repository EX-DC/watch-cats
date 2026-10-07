# Watch Cats 🐈

داشبورد مانیتورینگ زندهٔ [LanCache](https://lancache.net/):
نشان می‌دهد چه سرویسی (Steam، Epic، PlayStation، Xbox، …) در حال **ذخیره** در کش است،
چه سیستم‌هایی در حال **دریافت از کش** هستند، حجم کش هر سرویس، منابع سرور و خطاها.

> *Watch Cats is an independent companion dashboard for LanCache. It is not affiliated with the LanCache project or with any game store. Brand names belong to their owners.*

## وضعیت
نسخهٔ `0.1.0` — فقط اسکلت پروژه. هنوز برنامه‌ای برای اجرا وجود ندارد.

## نقشهٔ راه
1. اسکلت پروژه ✅
2. خواندن لاگ‌ها، تشخیص سرویس و دستگاه، ذخیره در SQLite
3. API زنده (بروزرسانی ۱ ثانیه‌ای) و آمار CPU / RAM / شبکه / دیسک
4. رابط گرافیکی (طبق `design/`)
5. هشدارها: درون صفحه، مرورگر، تلگرام (+ اعلان وقتی ترافیک Epic روی HTTPS می‌رود و کش نمی‌شود)
6. بستهٔ Docker و compose (سه کانتینر: DNS، monolithic، داشبورد)
7. نصب با یک خط، بروزرسانی و حذف
8. انتشار image در GHCR با GitHub Actions، نسخهٔ `1.0.0`

## ابزار کمکی ویندوز
`tools/windows/epic-http-fix.ps1` — برای هر کامپیوتر ویندوزی یک‌بار اجرا شود تا Epic از HTTP دانلود کند و LanCache بتواند کشش کند.
```powershell
powershell -ExecutionPolicy Bypass -File .\epic-http-fix.ps1
```

## نسخه‌بندی و توسعه
[Semantic Versioning](https://semver.org/) — جزئیات در [CONTRIBUTING.md](CONTRIBUTING.md) و [CHANGELOG.md](CHANGELOG.md).

## لایسنس
[MIT](LICENSE)
