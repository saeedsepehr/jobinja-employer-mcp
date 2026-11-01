---
name: screen-resumes
description: Screen and shortlist the resumes a Jobinja job ad has received, using the jobinja MCP tools with low token use. Use when an employer asks to review, filter, rank, star, shortlist or note applicants of a Jobinja job ad (مرور، غربالگری یا شورت‌لیست رزومه‌های جابینجا).
---

# Screening Jobinja applicants

Work from the employer panel through the `jobinja` MCP tools. Keep token use low: read compact digests first and open full details only for promising applicants.

## Steps

1. Call `jobinja_status`. If it is not logged in, call `open_login_window` and ask the user to sign in in the window that opens.
2. Call `list_posts` and confirm which job ad the user means. Screen only the ads the user names.
3. Read the ad's requirements from the user, or ask them to paste the ad text when it matters.
4. Call `screen_applicants` page by page (25 applicants per call). Judge each applicant against the ad from the digest alone.
5. For borderline or promising applicants only, call `get_resume_text` (or `get_applicant` for team notes and the current decision).
6. Report a short ranked shortlist with one line of reasoning per person before changing anything, unless the user already asked you to act.
7. When the user asks you to act: `set_star` for the shortlist, `add_note` with the reason, `set_applicant_folders` to file them, `create_folder` first if needed.

## Rules

- Never use gender, age, marital status, religion or ethnicity to filter, rank or reject anyone. The digests leave those out on purpose; do not look them up.
- Do not call `reject_applicant` unless the user explicitly asks for that applicant to be rejected: Jobinja notifies the candidate. Prefer a note that suggests rejection, and use `dry_run` when the user wants to check first.
- Start notes with a short marker the user chooses (for example "By Claude:") so the team knows who wrote them.
- Opening an unreviewed applicant marks it as seen in the panel, as it does for a human recruiter. Tell the user once before a large screening run.
