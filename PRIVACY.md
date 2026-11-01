# Privacy Policy / سیاست حریم خصوصی

Last updated: 2026-11-01

jobinja-employer-mcp (including the `jobinja-employer` Claude plugin) is open-source software that runs entirely on your own computer. The author does not operate any server for it and receives no data from it.

## Data collection

The software collects no analytics, telemetry or usage data, and sends nothing to the author.

## What it accesses and how it is used

- It opens the Jobinja employer panel (panel.jobinja.ir and Jobinja's file servers) in a browser profile on your computer, using the session you create by signing in yourself. It never asks for, sees or stores your password.
- It reads job ads, applicant profiles, team notes and resume files from your panel, and, when you ask, writes stars, team notes, folders and rejections there.
- The information it reads is returned to the AI client you connected it to (for example Claude, ChatGPT or Codex). That client's provider processes it under its own privacy policy and terms. Choose a provider and settings appropriate for applicants' personal data.

## Storage and retention

- Your Jobinja sign-in session is stored in the browser profile at `~/.jobinja-mcp` on your computer until you delete that folder or the session expires.
- Downloaded resumes are saved to the folder you configure (default `~/Downloads/jobinja-resumes`) and stay there until you delete them.
- In HTTP mode, a random access secret is stored at `~/.jobinja-mcp/http_token`.
- Nothing else is kept.

## Third-party sharing

No data is shared with anyone by this software, other than the communication with Jobinja that the tools perform and the results returned to the AI client you chose.

## Your responsibilities

Applicant data is personal data. Use it only for recruiting, follow Jobinja's terms and the data-protection laws that apply to you, and delete downloaded resumes when you no longer need them.

## Contact

Questions or concerns: open an issue at https://github.com/saeedsepehr/jobinja-employer-mcp/issues

---

این نرم‌افزار کاملاً روی رایانه خود شما اجرا می‌شود و هیچ داده‌ای برای سازنده ارسال نمی‌کند. نشست ورود جابینجا در پوشه `~/.jobinja-mcp` و رزومه‌های دانلودشده در پوشه‌ای که تعیین می‌کنید روی رایانه شما می‌مانند. اطلاعاتی که ابزار از پنل می‌خواند فقط به دستیار هوش مصنوعی‌ای داده می‌شود که خودتان وصل کرده‌اید و طبق سیاست همان سرویس پردازش می‌شود. برای پرسش‌ها در بخش Issues مخزن پیام بگذارید.
