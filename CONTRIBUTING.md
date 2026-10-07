# راهنمای توسعه (Contributing)

## شاخه‌ها
- `main` همیشه پایدار است. مستقیم روی آن کار نکنید.
- هر تغییر روی یک شاخهٔ جدا: `feat/اسم-کوتاه`، `fix/اسم-کوتاه`، `docs/...`
- بعد از اتمام، Pull Request بسازید، CI سبز شود، و Merge کنید.

## پیام commit (Conventional Commits)
قالب: `type: توضیح کوتاه` (انگلیسی)

| type | کاربرد | اثر روی نسخه |
|---|---|---|
| `feat` | قابلیت جدید | MINOR (0.1.0 → 0.2.0) |
| `fix` | رفع باگ | PATCH (0.1.0 → 0.1.1) |
| `docs`, `chore`, `test`, `refactor`, `ci` | بقیه | معمولاً بدون تغییر نسخه |
| `feat!` یا `BREAKING CHANGE:` | تغییر ناسازگار | MAJOR |

## انتشار نسخهٔ جدید
1. فایل `VERSION` و `src/watchcats/_version.py` را به نسخهٔ جدید تغییر دهید.
2. در `CHANGELOG.md` بخش `[Unreleased]` را به `## [x.y.z] - تاریخ` تبدیل کنید.
3. `python scripts/check_version.py` و `python -m unittest discover -s tests` را اجرا کنید.
4. Commit و Merge به `main`.
5. `git tag -a vX.Y.Z -m "vX.Y.Z"` و `git push origin vX.Y.Z`.
6. در GitHub بخش Releases یک Release از همان tag بسازید و متن CHANGELOG را در آن بگذارید.
