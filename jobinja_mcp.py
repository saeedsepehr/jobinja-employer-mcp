"""Jobinja employer-panel MCP server.

Drives the Jobinja employer panel (panel.jobinja.ir) through a dedicated
Chrome profile (Playwright persistent context), so the login session survives
between runs. No password is ever handled by this code: run `server.py login`
once and sign in by hand in the window that opens.

Every action goes through the panel's own UI (page loads and button clicks),
so it behaves exactly like a recruiter using the site.

Environment variables:
  JOBINJA_HOME          state folder (default ~/.jobinja-mcp)
  JOBINJA_COMPANY       company slug in the panel URL (auto-detected if unset)
  JOBINJA_DOWNLOAD_DIR  where resumes are saved (default ~/Downloads/jobinja-resumes)
  JOBINJA_READ_ONLY     set to 1 to disable the tools that change data
  JOBINJA_BROWSER       "chrome" (default, uses installed Google Chrome), "msedge", or
                        "chromium" (Playwright's bundled browser: run `playwright install chromium`)
  JOBINJA_HTTP_TOKEN    secret path segment for `jobinja-employer-mcp http` (generated if unset)

Commands:
  jobinja-employer-mcp  run as a stdio MCP server (Claude Code, Claude Desktop, Codex CLI, ...)
  jobinja-employer-mcp login     open a browser window once to sign in
  jobinja-employer-mcp http      serve over Streamable HTTP for remote clients such as ChatGPT connectors
"""

import asyncio
import os
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

PANEL = "https://panel.jobinja.ir"
HOME = Path(os.environ.get("JOBINJA_HOME", Path.home() / ".jobinja-mcp"))
PROFILE_DIR = HOME / "profile"
DOWNLOAD_DIR = Path(os.environ.get("JOBINJA_DOWNLOAD_DIR", Path.home() / "Downloads" / "jobinja-resumes")).expanduser()
READ_ONLY = os.environ.get("JOBINJA_READ_ONLY", "") not in ("", "0", "false")
BROWSER = os.environ.get("JOBINJA_BROWSER", "chrome")
CHROME_ARGS = ["--disable-save-password-bubble", "--disable-features=PasswordManagerOnboarding"]
PAGE_SIZE = 25

POST_STATUSES = {"all", "active", "rejected", "draft", "closed", "archived"}
# Applicant status filter -> query param, as used by the panel's filter sidebar.
APPLICANT_STATUSES = {
    "pending": ("statuses[pending]", "3"),       # بررسی نشده (not yet opened)
    "read": ("statuses[read]", "4"),             # در انتظار تعیین وضعیت (awaiting decision)
    "interview": ("statuses[interview]", "2"),   # تایید برای مصاحبه
    "hired": ("statuses[hired]", "1"),           # استخدام شده
    "dismissed": ("statuses[dismissed]", "15"),  # رد شده
    "expired": ("statuses[expired]", "18"),
    "canceled": ("statuses[applicant_canceled]", "17"),
}
# Rejection reasons offered by the panel. Reasons based on gender (10) or age (11)
# are deliberately not offered by this server.
REJECTION_REASONS = {
    5: "ناقص بودن اطلاعات رزومه",
    6: "کافی نبودن دانش فنی",
    7: "فراتر بودن از حد انتظار (Over Qualified)",
    8: "پرشدن موقعیت شغلی",
    9: "عدم تطابق محل سکونت با محل‌کار",
    12: "نامرتبط‌بودن تجربیات",
    13: "نداشتن کارت پایان‌خدمت یا معافیت‌دائم",
    14: "نامرتبط‌بودن حقوق درخواستی با موقعیت‌شغلی",
    15: "دلایل دیگر",
    16: "نداشتن سابقه‌کار مرتبط کافی",
}

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def latin(s: str) -> str:
    return (s or "").translate(_FA_DIGITS)


def to_int(s: str):
    s = re.sub(r"[^\d]", "", latin(s))
    return int(s) if s else None


async def _launch(pw, headless: bool):
    """Open the persistent profile in the configured browser."""
    kwargs = dict(headless=headless, args=CHROME_ARGS, viewport={"width": 1440, "height": 900}, locale="fa-IR")
    if BROWSER != "chromium":
        kwargs["channel"] = BROWSER
    try:
        return await pw.chromium.launch_persistent_context(str(PROFILE_DIR), **kwargs)
    except Exception as e:
        hint = ("Install Google Chrome, or set JOBINJA_BROWSER=chromium and run `playwright install chromium`."
                if BROWSER != "chromium" else "Run `playwright install chromium`.")
        raise RuntimeError(f"Could not start the browser ({BROWSER}): {e}\n{hint}") from e


class Panel:
    def __init__(self):
        self._pw = None
        self._ctx = None
        self.lock = asyncio.Lock()
        self.company = os.environ.get("JOBINJA_COMPANY")

    async def ctx(self):
        if self._ctx is None:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._pw = await async_playwright().start()
            self._ctx = await _launch(self._pw, headless=True)
        return self._ctx

    async def page(self, url: str):
        ctx = await self.ctx()
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        if "/auth/" in page.url:
            await page.close()
            raise RuntimeError(
                "Not logged in to Jobinja (session missing or expired). Run: "
                "jobinja-employer-mcp login"
            )
        return page

    async def company_slug(self) -> str:
        if self.company:
            return self.company
        page = await self.page(PANEL + "/dashboard")
        try:
            hrefs = [page.url] + await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        finally:
            await page.close()
        for h in hrefs:
            m = re.match(r"https://panel\.jobinja\.ir/([^/?#]+)/dashboard", h)
            if m:
                self.company = m.group(1)
                return self.company
        raise RuntimeError("Could not detect the company slug; set JOBINJA_COMPANY.")


panel = Panel()
mcp = FastMCP("jobinja")


def write_tool(fn):
    """Register a tool that changes data, unless the server runs read-only."""
    return fn if READ_ONLY else mcp.tool()(fn)


@mcp.tool()
async def jobinja_status() -> dict:
    """Check whether the saved Jobinja session is still logged in and which company panel it uses."""
    async with panel.lock:
        try:
            slug = await panel.company_slug()
            return {"logged_in": True, "company": slug, "download_dir": str(DOWNLOAD_DIR), "read_only": READ_ONLY}
        except RuntimeError as e:
            return {"logged_in": False, "error": str(e)}


@mcp.tool()
async def list_posts(status: str = "all") -> list[dict]:
    """List the company's job ads with applicant counts.

    status: all | active | rejected | draft | closed | archived.
    Each item has `post` (short id such as "tMEO", used by the other tools),
    numeric `post_numeric_id`, title, publish state and per-stage counts.
    """
    if status not in POST_STATUSES:
        raise ValueError(f"status must be one of {sorted(POST_STATUSES)}")
    async with panel.lock:
        slug = await panel.company_slug()
        url = f"{PANEL}/{slug}/dashboard" + ("" if status == "all" else f"?status={status}")
        page = await panel.page(url)
        try:
            cards = await page.evaluate(
                """() => [...document.querySelectorAll('div.card')].filter(c => c.querySelector('.stage-counter')).map(c => {
                    const links = [...c.querySelectorAll('a[href]')].map(a => a.href);
                    const main = links.find(h => /\\/posts\\/[A-Za-z0-9]+$/.test(h));
                    const edit = links.find(h => /\\/posts\\/\\d+\\/edit/.test(h));
                    const stages = [...c.querySelectorAll('.stage-counter')].map(s => [s.nextElementSibling?.innerText.trim(), s.innerText.trim()]);
                    const views = [...c.querySelectorAll('span.count')].map(s => [s.nextElementSibling?.innerText.trim(), s.innerText.trim()]);
                    const title = main ? [...c.querySelectorAll('a')].find(a => a.href === main && a.innerText.trim())?.innerText.trim() : null;
                    return {main, edit, title, state: c.querySelector('.badge-outline')?.innerText.trim(), stages, views};
                })"""
            )
        finally:
            await page.close()
    out = []
    for c in cards:
        if not c["main"]:
            continue
        item = {
            "post": c["main"].rsplit("/", 1)[-1],
            "post_numeric_id": int(re.search(r"/posts/(\d+)/", c["edit"]).group(1)) if c["edit"] else None,
            "title": c["title"],
            "state": c["state"],
            "url": c["main"],
        }
        for label, val in c["stages"] + c["views"]:
            item[label or "?"] = to_int(val)
        out.append(item)
    return out


def _applicants_url(slug, post, status=None, page=1, sort=None, starred=False, has_notes=False):
    params = []
    if status:
        if status not in APPLICANT_STATUSES:
            raise ValueError(f"status must be one of {sorted(APPLICANT_STATUSES)}")
        k, v = APPLICANT_STATUSES[status]
        params.append(f"{k}={v}")
    if starred:
        params.append("is_favorite=1")
    if has_notes:
        params.append("has_comment=1")
    if sort:
        params.append(f"sort_by={sort}")
    if page and page > 1:
        params.append(f"page={page}")
    return f"{PANEL}/{slug}/posts/{post}" + ("?" + "&".join(params) if params else "")


_ROWS_JS = """() => {
    const tip = (r, icon) => r.querySelector(`.fa-${icon}`)?.closest('[data-original-title]')?.getAttribute('data-original-title')?.trim() || '';
    const rows = [...document.querySelectorAll('tr[data-candidate-box-url]')].map(r => {
        const t = r.querySelector('a[name=title]')?.innerText.trim().split('\\n').map(s => s.trim()).filter(Boolean) || [];
        const star = tip(r, 'star'), note = tip(r, 'comment'), folder = tip(r, 'folder');
        return {
            applicant_id: r.dataset.candidateBoxUrl.split('/').pop(),
            application_record: r.dataset.jobApplicationRecord,
            name: t[0] || null, headline: t[1] || null,
            status: r.querySelector('a[name=status]')?.innerText.trim(),
            applied: r.querySelector('a[name=date]')?.innerText.trim(),
            starred: !!star && !star.startsWith('بدون'),
            notes: note.startsWith('بدون') ? '' : note,
            folders: folder.startsWith('بدون') ? '' : folder,
        };
    });
    const m = document.body.innerText.match(/([۰-۹\\d,]+)\\s*-\\s*([۰-۹\\d,]+)\\s*از\\s*([۰-۹\\d,]+)\\s*متقاضی/);
    return {rows, range: m ? [m[1], m[2], m[3]] : null};
}"""


@mcp.tool()
async def list_applicants(
    post: str,
    status: str | None = None,
    starred: bool = False,
    has_notes: bool = False,
    page: int = 1,
    sort: str = "id",
) -> dict:
    """List applicants of a job ad, 25 per page (newest first by default).

    post: short id from list_posts (e.g. "tMEO").
    status: pending (unreviewed) | read (awaiting decision) | interview | hired | dismissed | expired | canceled.
    starred / has_notes: only starred applicants / only those with team notes.
    sort: id (newest) | id_asc (oldest) | relevance.
    Each row has `applicant_id` (for the other tools), status, starred flag, note count and folders.
    """
    async with panel.lock:
        slug = await panel.company_slug()
        p = await panel.page(_applicants_url(slug, post, status, page, sort, starred, has_notes))
        try:
            data = await p.evaluate(_ROWS_JS)
        finally:
            await p.close()
    total = to_int(data["range"][2]) if data["range"] else len(data["rows"])
    for r in data["rows"]:
        r["notes"] = latin(r["notes"])
    return {
        "post": post, "page": page, "total": total,
        "pages": max(1, -(-total // PAGE_SIZE)), "applicants": data["rows"],
    }


_DETAIL_JS = """(slug) => {
    const mc = document.querySelector(`.modal-content[data-endpoint$="/applicants/${slug}"]`);
    const cv = mc.querySelector('.candidate-box-cv');
    const side = mc.querySelector('.candidate-box-side');
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
    const fields = {};
    for (const l of cv.querySelectorAll('label')) {
        const v = l.nextElementSibling;
        const k = clean(l.innerText).replace(/:$/, '');
        if (v && v.tagName !== 'LABEL' && k && v.innerText.trim() && !(k in fields)) fields[k] = clean(v.innerText);
    }
    const links = [...cv.querySelectorAll('a[href]')];
    const resume = links.find(a => /jobinjacdn|mstorage/.test(a.href) && /دانلود/.test(a.innerText));
    const spans = [...cv.querySelectorAll('span')].filter(s => !s.children.length).map(s => s.innerText.trim()).filter(Boolean);
    const prof = cv.querySelector('#jobinjaProfile');
    const fav = side.querySelector('[data-job-application-favorite]');
    const active = [...side.querySelectorAll('[name^=status-].active')].map(b => clean(b.innerText));
    const notice = side.innerText.match(/این درخواست[^\\n]*/);
    const notes = [...side.querySelectorAll('.comments-container label')].map(l => {
        const box = l.parentElement;
        return {author: clean(l.innerText), text: (box.querySelector('p')?.innerText || '').trim(),
                when: clean(box.querySelector('span')?.innerText)};
    });
    return {
        name: spans[0] || null,
        email: (cv.innerText.match(/[\\w.+-]+@[\\w-]+\\.[\\w.]+/) || [null])[0],
        phone: spans.find(s => /^[۰-۹0-9+\\s-]{10,}$/.test(s)) || null,
        applied_at: spans.find(s => /^\\(.*\\)$/.test(s))?.replace(/[()]/g, '') || null,
        starred: fav ? fav.dataset.filled === '1' : null,
        decision: active[0] || null,
        decision_note: notice ? clean(notice[0]) : null,
        notes,
        fields,
        resume_url: resume?.href || null,
        jobinja_profile: prof ? prof.innerText.split('\\n').map(l => l.trim()).filter(Boolean).join('\\n').slice(0, 8000) : null,
    };
}"""


async def _open_applicant(post: str, applicant_id: str, page_hint: int | None, max_pages: int = 40):
    """Open the applicant's box the same way the panel UI does (click its row)."""
    slug = await panel.company_slug()
    pages = [page_hint] if page_hint else []
    pages += [n for n in range(1, max_pages + 1) if n != page_hint]
    for n in pages:
        p = await panel.page(_applicants_url(slug, post, page=n))
        row = await p.query_selector(f'tr[data-candidate-box-url$="/applicants/{applicant_id}"] a[name=title]')
        if row:
            await row.click()
            await p.wait_for_selector(
                f'.modal-content[data-endpoint$="/applicants/{applicant_id}"] .candidate-box-side', timeout=20000
            )
            return p
        has_rows = await p.query_selector("tr[data-candidate-box-url]")
        await p.close()
        if not has_rows:
            break
    raise ValueError(f"Applicant {applicant_id} not found in post {post}")


def _box(applicant_id: str) -> str:
    return f'.modal-content[data-endpoint$="/applicants/{applicant_id}"]'


async def _details(p, applicant_id):
    d = await p.evaluate(_DETAIL_JS, applicant_id)
    d["phone"] = latin(d["phone"] or "") or None
    d["applied_at"] = latin(d["applied_at"] or "") or None
    return d


@mcp.tool()
async def get_applicant(post: str, applicant_id: str, page_hint: int | None = None) -> dict:
    """Get one applicant: contact info, profile fields, Jobinja profile text, star, team notes, current decision and rejection reason.

    applicant_id comes from list_applicants; page_hint (the list page it was on) makes lookup faster.
    Like opening it in the panel, viewing an unreviewed (pending) applicant marks it as seen.
    """
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            d = await _details(p, applicant_id)
        finally:
            await p.close()
    d["has_resume_file"] = bool(d.pop("resume_url"))
    d.update(post=post, applicant_id=applicant_id)
    return d


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s or "", flags=re.UNICODE).strip("_")[:60]


async def _download(post, applicant_id, page_hint, dest: Path):
    p = await _open_applicant(post, applicant_id, page_hint)
    try:
        d = await _details(p, applicant_id)
        if not d["resume_url"]:
            return {"applicant_id": applicant_id, "name": d["name"], "path": None, "note": "no attached resume file"}
        resp = await p.context.request.get(d["resume_url"])
        if not resp.ok:
            raise RuntimeError(f"download failed: HTTP {resp.status}")
        body = await resp.body()
    finally:
        await p.close()
    ext = Path(d["resume_url"].split("?")[0]).suffix or ".pdf"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{post}_{applicant_id}_{_safe(d['name'])}{ext}"
    path.write_bytes(body)
    return {"applicant_id": applicant_id, "name": d["name"], "path": str(path), "bytes": len(body)}


@mcp.tool()
async def download_resume(post: str, applicant_id: str, page_hint: int | None = None, dest_dir: str | None = None) -> dict:
    """Download an applicant's attached resume file (usually PDF) and return its local path, ready to be read.

    Default folder: JOBINJA_DOWNLOAD_DIR/<post>/.
    """
    dest = (Path(dest_dir).expanduser() if dest_dir else DOWNLOAD_DIR / post)
    async with panel.lock:
        return await _download(post, applicant_id, page_hint, dest)


@mcp.tool()
async def download_resumes(
    post: str, status: str | None = None, starred: bool = False, limit: int = 25, dest_dir: str | None = None
) -> dict:
    """Bulk-download resumes for a job ad, newest first, optionally filtered by status / starred (see list_applicants).

    Downloads at most `limit` files into JOBINJA_DOWNLOAD_DIR/<post>/ (or dest_dir).
    Viewing pending applicants marks them as seen, as in the panel.
    """
    dest = Path(dest_dir).expanduser() if dest_dir else DOWNLOAD_DIR / post
    results, errors, page = [], [], 1
    while len(results) + len(errors) < limit:
        lst = await list_applicants(post, status=status, starred=starred, page=page)
        if not lst["applicants"]:
            break
        for a in lst["applicants"]:
            if len(results) + len(errors) >= limit:
                break
            try:
                async with panel.lock:
                    hint = page if not (status or starred) else None
                    results.append(await _download(post, a["applicant_id"], hint, dest))
            except Exception as e:  # keep going on single failures
                errors.append({"applicant_id": a["applicant_id"], "error": str(e)})
        if page >= lst["pages"]:
            break
        page += 1
    return {"dest_dir": str(dest), "downloaded": results, "errors": errors}


# Fields left out of screening digests: personal data that must not drive a hiring decision, plus contact details.
_DIGEST_SKIP = {"جنسیت", "سال تولد", "وضعیت تاهل", "آدرس ایمیل", "آدرس محل سکونت"}


def _strip_contacts(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "", text)
    # phone numbers: runs of digits/spaces/dashes/brackets holding at least 10 digits
    phone = re.compile(r"\(?\+?[\d۰-۹][\d۰-۹ ()+-]{8,}[\d۰-۹]")
    return phone.sub(lambda m: "" if len(re.findall(r"[\d۰-۹]", m.group())) >= 10 else m.group(), text).strip()


def _pdf_text(body: bytes, max_pages: int = 4) -> str:
    """Plain text of a PDF resume (first pages), with Arabic/Persian presentation forms normalised."""
    import io
    import unicodedata
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages[:max_pages])
    except Exception as e:
        return f"[could not read PDF: {e}]"
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", unicodedata.normalize("NFKC", text))).strip()


async def _resume_text(p, resume_url: str | None) -> str | None:
    if not resume_url:
        return None
    resp = await p.context.request.get(resume_url)
    if not resp.ok:
        return f"[download failed: HTTP {resp.status}]"
    if not resume_url.split("?")[0].lower().endswith(".pdf"):
        return "[resume is not a PDF; use download_resume]"
    return _pdf_text(await resp.body())


@mcp.tool()
async def get_resume_text(post: str, applicant_id: str, max_chars: int = 6000, page_hint: int | None = None) -> dict:
    """Extracted plain text of an applicant's PDF resume, truncated to max_chars.

    Much cheaper in tokens than reading the PDF itself. Scanned (image-only) PDFs give little or no text;
    use download_resume for those.
    """
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            d = await _details(p, applicant_id)
            text = await _resume_text(p, d["resume_url"])
        finally:
            await p.close()
    return {"applicant_id": applicant_id, "name": d["name"], "has_resume_file": bool(d["resume_url"]),
            "text": text[:max_chars] if text else None, "truncated": bool(text and len(text) > max_chars)}


@mcp.tool()
async def screen_applicants(
    post: str, status: str | None = None, page: int = 1, resume_chars: int = 800, profile_chars: int = 500,
) -> dict:
    """Compact screening digest of one page (up to 25) of applicants, for fast, low-token shortlisting.

    For each applicant: headline, status, star, notes, folders, key profile fields (work history, education,
    skills) and the first `resume_chars` characters of the PDF resume text. Gender, birth year, marital status
    and contact details are left out on purpose. Read the digests, then use get_resume_text / get_applicant only
    for the promising ones. Takes about a minute per page; opening pending applicants marks them as seen.
    """
    async with panel.lock:
        slug = await panel.company_slug()
        p = await panel.page(_applicants_url(slug, post, status, page))
        out = []
        try:
            data = await p.evaluate(_ROWS_JS)
            for r in data["rows"]:
                aid = r["applicant_id"]
                item = {k: r[k] for k in ("applicant_id", "name", "headline", "status", "applied", "starred", "notes", "folders")}
                item["notes"] = latin(item["notes"])
                try:
                    await p.locator(f'tr[data-candidate-box-url$="/applicants/{aid}"] a[name=title]').click()
                    await p.wait_for_selector(f"{_box(aid)} .candidate-box-side", timeout=25000)
                    d = await _details(p, aid)
                    fields = {k: v for k, v in d["fields"].items() if k not in _DIGEST_SKIP and not k.startswith("زبان")}
                    item["profile"] = " | ".join(f"{k}: {v}" for k, v in fields.items())[:profile_chars]
                    text = await _resume_text(p, d["resume_url"])
                    if text:  # contact details cost tokens and are not needed for screening
                        text = _strip_contacts(text)
                    item["resume"] = text[:resume_chars] if text else None
                except Exception as e:  # keep going on single failures
                    item["error"] = str(e)
                await p.keyboard.press("Escape")
                await p.wait_for_timeout(300)
                out.append(item)
        finally:
            await p.close()
    total = to_int(data["range"][2]) if data["range"] else len(out)
    return {"post": post, "page": page, "total": total, "pages": max(1, -(-total // PAGE_SIZE)), "applicants": out}


@mcp.tool()
async def list_rejection_reasons() -> dict:
    """Rejection reasons accepted by reject_applicant (code -> panel label)."""
    return REJECTION_REASONS


async def _click_and_wait(p, locator, url_part: str):
    async with p.expect_response(
        lambda r: url_part in r.url and r.request.method != "GET" and r.url.startswith(PANEL), timeout=20000
    ) as info:
        await locator.click()
    resp = await info.value
    if not resp.ok:
        raise RuntimeError(f"panel returned HTTP {resp.status}")


async def _confirm_modal(p, url_part: str):
    """Press the confirm button of the panel's confirmation dialog."""
    btn = p.locator(".modal.show .modal-footer button:visible", has_text="تایید").first
    await btn.wait_for(state="visible", timeout=10000)
    await _click_and_wait(p, btn, url_part)


@write_tool
async def set_star(post: str, applicant_id: str, starred: bool = True, page_hint: int | None = None) -> dict:
    """Star (starred=true) or unstar (starred=false) an applicant. Stars are internal to the company."""
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            fav = p.locator(f"{_box(applicant_id)} .candidate-box-side [data-job-application-favorite]")
            current = await fav.get_attribute("data-filled") == "1"
            if current != starred:
                await _click_and_wait(p, fav, "/")
                await p.wait_for_timeout(500)
                if (await fav.get_attribute("data-filled") == "1") != starred:
                    raise RuntimeError("star state did not change")
            return {"applicant_id": applicant_id, "starred": starred, "changed": current != starred}
        finally:
            await p.close()


@write_tool
async def add_note(post: str, applicant_id: str, text: str, page_hint: int | None = None) -> dict:
    """Add a confidential team note to an applicant (visible to company members only, not to the candidate)."""
    if not text.strip():
        raise ValueError("note text is empty")
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            form = p.locator(f"{_box(applicant_id)} form[name=comment-form]").first
            await form.locator("textarea[name=note]").fill(text)
            await _click_and_wait(p, form.locator("button[type=submit]"), "/notes")
            await p.wait_for_timeout(800)
            notes = (await _details(p, applicant_id))["notes"]
            return {"applicant_id": applicant_id, "added": True, "notes": notes}
        finally:
            await p.close()


@write_tool
async def delete_note(post: str, applicant_id: str, text_contains: str, page_hint: int | None = None) -> dict:
    """Delete one team note whose text contains `text_contains` (e.g. to fix a mistaken note). Only notes you can delete in the panel."""
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            item = p.locator(f"{_box(applicant_id)} .comments-container p", has_text=text_contains)
            if await item.count() != 1:
                raise ValueError(f"expected exactly one matching note, found {await item.count()}")
            holder = item.first.locator("xpath=ancestor::*[.//button[normalize-space()='حذف']][1]")
            await holder.locator("button", has_text="حذف").first.click()
            btn = p.locator(".modal.show .modal-footer button:visible", has_text="تایید").first
            await btn.wait_for(state="visible", timeout=10000)
            await _click_and_wait(p, btn, "/notes/")
            return {"applicant_id": applicant_id, "deleted": True}
        finally:
            await p.close()


_FOLDERS_JS = """() => [...document.querySelectorAll('a[href]')].filter(a => /\\/folder\\/\\d+$/.test(a.href) && a.innerText.trim())
    .map(a => {
        const card = a.closest('.card') || a.parentElement;
        const stages = [...card.querySelectorAll('.stage-counter')].map(s => [s.nextElementSibling?.innerText.trim(), s.innerText.trim()]);
        return {id: a.href.split('/').pop(), title: a.innerText.trim(), stages};
    })"""


async def _folders(slug):
    p = await panel.page(f"{PANEL}/{slug}/folder")
    try:
        raw = await p.evaluate(_FOLDERS_JS)
    finally:
        await p.close()
    out, seen = [], set()
    for f in raw:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        item = {"folder_id": f["id"], "title": f["title"]}
        for label, val in f["stages"]:
            item[label or "?"] = to_int(val)
        out.append(item)
    return out


@mcp.tool()
async def list_folders() -> list[dict]:
    """List the company's resume folders (پوشه‌های رزومه) with their ids and per-stage counts."""
    async with panel.lock:
        return await _folders(await panel.company_slug())


@mcp.tool()
async def list_folder_applicants(folder_id: str, page: int = 1) -> dict:
    """List applicants saved in a resume folder, 25 per page. Each row includes the `post` it applied to."""
    async with panel.lock:
        slug = await panel.company_slug()
        p = await panel.page(f"{PANEL}/{slug}/folder/{folder_id}" + (f"?page={page}" if page > 1 else ""))
        try:
            data = await p.evaluate(_ROWS_JS)
            urls = await p.eval_on_selector_all("tr[data-candidate-box-url]", "rs => rs.map(r => r.dataset.candidateBoxUrl)")
        finally:
            await p.close()
    for r, u in zip(data["rows"], urls):
        r["post"] = re.search(r"/posts/([^/]+)/applicants/", u).group(1)
        r["notes"] = latin(r["notes"])
    total = to_int(data["range"][2]) if data["range"] else len(data["rows"])
    return {"folder_id": folder_id, "page": page, "total": total,
            "pages": max(1, -(-total // PAGE_SIZE)), "applicants": data["rows"]}


@write_tool
async def create_folder(title: str) -> dict:
    """Create a new resume folder and return its id. If a folder with this exact title exists, returns it instead."""
    title = title.strip()
    if not title:
        raise ValueError("folder title is empty")
    async with panel.lock:
        slug = await panel.company_slug()
        existing = [f for f in await _folders(slug) if f["title"] == title]
        if existing:
            return {**existing[0], "created": False}
        p = await panel.page(f"{PANEL}/{slug}/folder")
        try:
            await p.locator("[data-controller=folder-upsert-toggle]", has_text="ایجاد پوشه").first.click()
            form = p.locator(".modal.show form").first
            await form.locator("input[name=title]").fill(title)
            await _click_and_wait(p, form.locator("button[type=submit]"), "/folder")
        finally:
            await p.close()
        made = [f for f in await _folders(slug) if f["title"] == title]
    if not made:
        raise RuntimeError("folder was not created")
    return {**made[0], "created": True}


@write_tool
async def set_applicant_folders(
    post: str, applicant_id: str, add: list[str] | None = None, remove: list[str] | None = None,
    page_hint: int | None = None,
) -> dict:
    """Add an applicant to and/or remove it from resume folders. `add` / `remove` take folder ids or exact titles
    (see list_folders; use create_folder first for a new one). Returns the applicant's folders afterwards."""
    add, remove = add or [], remove or []
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            # The dialog loads the folder list (with this applicant's current folders) after opening.
            async with p.expect_response(lambda r: "/folder" in r.url and r.request.method == "GET", timeout=20000):
                await p.locator(f"{_box(applicant_id)} [name=select-folder]").click()
            boxes = p.locator('.modal.show input[type=checkbox][name="folders[]"]')
            await boxes.first.wait_for(state="attached", timeout=15000)
            await p.wait_for_timeout(500)
            state = await boxes.evaluate_all(
                "els => els.map(e => ({id: e.value, title: (e.closest('label') || e.parentElement).innerText.trim(), checked: e.checked}))"
            )
            index = {f["id"]: f for f in state} | {f["title"]: f for f in state}
            missing = [k for k in add + remove if k not in index]
            if missing:
                raise ValueError(f"unknown folders: {missing}")
            want = {f["id"]: f["checked"] for f in state}
            want.update({index[k]["id"]: True for k in add})
            want.update({index[k]["id"]: False for k in remove})
            changed = [i for i, v in want.items() if v != next(f["checked"] for f in state if f["id"] == i)]
            if changed:
                for i in changed:
                    box = p.locator(f'.modal.show input[type=checkbox][name="folders[]"][value="{i}"]')
                    await box.set_checked(want[i], force=True)
                await _click_and_wait(p, p.locator(".modal.show button[type=submit]").last, "sync-folders")
            folders = [f["title"] for f in state if want[f["id"]]]
            return {"applicant_id": applicant_id, "folders": folders, "changed": bool(changed)}
        finally:
            await p.close()


@write_tool
async def reject_applicant(
    post: str, applicant_id: str, reason: int, message: str = "", page_hint: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Mark an applicant as rejected (نامناسب) with a reason code from list_rejection_reasons.

    Jobinja notifies the candidate of the rejection; `message` is optional extra text sent to the
    candidate with it (not an internal note: use add_note for that).
    dry_run=true fills the rejection form without submitting it.
    """
    if reason not in REJECTION_REASONS:
        raise ValueError(f"reason must be one of {sorted(REJECTION_REASONS)}")
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            box = _box(applicant_id)
            await p.locator(f"{box} .candidate-box-side [name=status-no]").click()
            form = p.locator("form[name=reject-application]:visible").first
            await form.wait_for(state="visible", timeout=10000)
            await form.locator("select[name=status]").select_option(str(reason))
            if message:
                await form.locator("textarea[name=message]").fill(message)
            if dry_run:
                return {"applicant_id": applicant_id, "rejected": False, "dry_run": True, "reason": REJECTION_REASONS[reason]}
            await _click_and_wait(p, form.locator("button[name=ok]"), "update-status")
            return {"applicant_id": applicant_id, "rejected": True, "reason": REJECTION_REASONS[reason]}
        finally:
            await p.close()


@write_tool
async def restore_applicant(post: str, applicant_id: str, page_hint: int | None = None) -> dict:
    """Undo a decision: move an applicant back to "awaiting decision" (در انتظار تعیین وضعیت). Jobinja notifies the candidate."""
    async with panel.lock:
        p = await _open_applicant(post, applicant_id, page_hint)
        try:
            link = p.locator(f"{_box(applicant_id)} .candidate-box-side [name=change-status]")
            if not await link.count():
                return {"applicant_id": applicant_id, "changed": False, "note": "already awaiting decision"}
            await link.first.click()
            await _confirm_modal(p, "update-status")
            return {"applicant_id": applicant_id, "changed": True}
        finally:
            await p.close()


async def login():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        ctx = await _launch(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(PANEL + "/dashboard")
        print("Sign in to Jobinja in the opened window. It closes itself once the panel loads.")
        for _ in range(900):
            if page.url.startswith(PANEL) and "/auth/" not in page.url:
                print("Logged in:", page.url)
                break
            await asyncio.sleep(1)
        else:
            print("Timed out waiting for login.")
        await asyncio.sleep(2)
        await ctx.close()


def serve_http(host: str, port: int):
    """Serve over Streamable HTTP at /<token>/mcp. The token is the only protection: keep the URL secret."""
    import secrets
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    token = os.environ.get("JOBINJA_HTTP_TOKEN")
    token_file = HOME / "http_token"
    if not token:
        HOME.mkdir(parents=True, exist_ok=True)
        if not token_file.exists():
            token_file.write_text(secrets.token_urlsafe(24))
        token = token_file.read_text().strip()
    # Requests arrive through a tunnel with its own Host header, so host checks are off; the secret path guards access.
    mcp.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp.settings.streamable_http_path = f"/{token}/mcp"
    print(f"MCP endpoint: http://{host}:{port}/{token}/mcp", file=sys.stderr)
    print("Expose it over HTTPS (for example `cloudflared tunnel --url http://localhost:%d`) and give the "
          "https URL + /%s/mcp to the client." % (port, token), file=sys.stderr)
    uvicorn.run(mcp.streamable_http_app(), host=host, port=port)


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="jobinja-employer-mcp", description="MCP server for the Jobinja employer panel")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("login", help="sign in once in a browser window")
    http = sub.add_parser("http", help="serve over Streamable HTTP (ChatGPT connectors, remote clients)")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.cmd == "login":
        asyncio.run(login())
    elif args.cmd == "http":
        serve_http(args.host, args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
