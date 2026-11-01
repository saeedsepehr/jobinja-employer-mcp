# jobinja-mcp — راهنمای فارسی

یک سرور MCP غیررسمی برای پنل کارفرمایی جابینجا. با اون، دستیار هوش مصنوعی (Claude، ChatGPT، Codex و…) می‌تونه مثل یک کارشناس جذب با پنل کار کنه: آگهی‌ها و متقاضی‌ها رو ببینه، پروفایل و یادداشت‌ها و رزومه‌ها رو بخونه، ستاره بزنه، یادداشت بذاره، پوشه بسازه، متقاضی رو به پوشه اضافه یا ازش حذف کنه و درخواست رو رد کنه.

سرور با Playwright و یک پروفایل مرورگر جداگانه کار می‌کنه و پسورد شما رو هیچ‌وقت نمی‌بینه یا ذخیره نمی‌کنه. فقط یک بار دستی لاگین می‌کنید و سشن در همون پروفایل روی کامپیوتر خودتون می‌مونه.

## نصب (ویندوز، مک، لینوکس)

پیش‌نیازها: پایتون ۳.۱۰ یا جدیدتر، و Google Chrome. اگه Chrome ندارید، Edge هم کار می‌کنه (`JOBINJA_BROWSER=msedge`) یا مرورگر داخلی Playwright (`JOBINJA_BROWSER=chromium` و بعد `playwright install chromium`).

۱. نصب pipx (فقط یک بار):
   - ویندوز: `py -m pip install --user pipx` و بعد `py -m pipx ensurepath`
   - مک: `brew install pipx` و بعد `pipx ensurepath`
   - لینوکس: `sudo apt install pipx` و بعد `pipx ensurepath`

   بعد از `ensurepath` ترمینال رو ببندید و دوباره باز کنید.

۲. نصب سرور:
```bash
pipx install git+https://github.com/saeedsepehr/jobinja-mcp
```

۳. لاگین یک‌باره: یک پنجره مرورگر باز می‌شه. وارد پنل کارفرمایی بشید و پنجره بعد از لود شدن پنل خودش بسته می‌شه.
```bash
jobinja-mcp login
```

اگه سشن منقضی شد، همین دستور رو دوباره اجرا کنید (قبلش برنامه‌ای که از MCP استفاده می‌کنه رو ببندید).

## اتصال به برنامه‌ها

**Claude Code:**
```bash
claude mcp add -s user jobinja -- jobinja-mcp
```

**Claude Desktop:** این رو به فایل `claude_desktop_config.json` اضافه کنید و برنامه رو دوباره باز کنید. مسیر فایل در مک `~/Library/Application Support/Claude/` و در ویندوز `%APPDATA%\Claude\` است.
```json
{ "mcpServers": { "jobinja": { "command": "jobinja-mcp" } } }
```
اگه برنامه دستور رو پیدا نکرد، مسیر کاملش رو بذارید (با `where jobinja-mcp` در ویندوز یا `which jobinja-mcp` در مک و لینوکس پیداش کنید).

**نسخه GPT، حالت اول: Codex CLI (ساده‌ترین راه)** — به `~/.codex/config.toml` اضافه کنید:
```toml
[mcp_servers.jobinja]
command = "jobinja-mcp"
```

**نسخه GPT، حالت دوم: ChatGPT (کانکتور حالت توسعه‌دهنده)** — ChatGPT فقط به سرورهای راه دور با HTTPS وصل می‌شه:
```bash
jobinja-mcp http --port 8765
cloudflared tunnel --url http://localhost:8765
```
دستور اول یک آدرس با یک بخش مخفی می‌ده (`/<secret>/mcp`) و دستور دوم یک آدرس عمومی `https://….trycloudflare.com`. در ChatGPT به Settings → Apps & Connectors → Advanced برید، Developer mode رو روشن کنید و یک کانکتور با آدرس `https://….trycloudflare.com/<secret>/mcp` و بدون احراز هویت بسازید.

هشدار: هر کسی این آدرس رو داشته باشه به سشن جابینجای شما دسترسی داره. آدرس رو جایی نذارید، بعد از کار تونل رو ببندید، و بهتره در این حالت `JOBINJA_READ_ONLY=1` رو بذارید. برای عوض کردن بخش مخفی، فایل `~/.jobinja-mcp/http_token` رو پاک کنید.

## تنظیمات

| متغیر | پیش‌فرض |
| --- | --- |
| `JOBINJA_HOME` | `~/.jobinja-mcp` (پروفایل مرورگر) |
| `JOBINJA_COMPANY` | خودکار از پنل |
| `JOBINJA_DOWNLOAD_DIR` | `~/Downloads/jobinja-resumes` |
| `JOBINJA_READ_ONLY` | خالی (ابزارهای نوشتنی فعال) |
| `JOBINJA_BROWSER` | `chrome` (یا `msedge` یا `chromium`) |

دلایل رد مبتنی بر جنسیت یا سن عمداً در ابزار نیست. باز کردن متقاضیِ «بررسی‌نشده» اون رو دیده‌شده می‌کنه، دقیقاً مثل خود پنل.

## مشارکت

باگ‌ها و پیشنهادها رو در [Issues](https://github.com/saeedsepehr/jobinja-mcp/issues) ثبت کنید. اگه ساختار پنل جابینجا عوض شد و ابزاری از کار افتاد، Pull Request خیلی کمک می‌کنه.

هیچ‌وقت فایل رزومه، داده متقاضی یا پوشه `~/.jobinja-mcp` (که سشن لاگین شما توشه) رو در issue یا مخزن نذارید.
