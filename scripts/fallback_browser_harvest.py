#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
JOB_DIR = ROOT / "job-agent"
LOG_PATH = JOB_DIR / "rejected-leads.log.jsonl"
SNAP_PATH = JOB_DIR / "rejected-leads.json"
PROFILE_PATH = JOB_DIR / "candidate-profile.json"
QUEUE_PATH = JOB_DIR / "send-queue.json"

ALLOWED_KEYWORDS = ["machine learning", "ai engineer", "llm developer"]
DISALLOWED_TITLE = ["senior", "principal", "lead", "manager", "head", "director", "architect", "project manager"]
INTEREST_KEYWORDS = [
    "llm",
    "large language model",
    "vla",
    "vision language action",
    "machine learning",
    "artificial intelligence",
    " ai ",
    "nlp",
    "deep learning",
]


def run_browser(*args: str) -> str:
    cmd = [
        "bash",
        "-lc",
        'export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && openclaw browser '
        + " ".join(sh_quote(a) for a in args),
    ]
    p = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"openclaw browser {' '.join(args)} failed: {p.stderr or p.stdout}")
    return p.stdout.strip()


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def parse_json(text: str):
    return json.loads(text)


def normalize_url(url: str) -> str:
    u = url.split("#", 1)[0]
    return u


def extract_salary_hkd(text: str):
    m = re.search(r"HK\$?\s*([0-9][0-9,]{3,})", text, flags=re.I)
    if m:
        return int(m.group(1).replace(",", ""))
    m2 = re.search(r"\$\s*([0-9][0-9,]{3,})", text)
    if m2:
        return int(m2.group(1).replace(",", ""))
    return None


def extract_exp_years(text: str):
    m = re.search(r"(\d+)\s*\+?\s*(?:years?|yrs?)", text, flags=re.I)
    if m:
        return int(m.group(1))
    return None


def skill_overlap(text: str, skills):
    lo = text.lower()
    return sorted({s for s in skills if s.lower() in lo})


def load_existing():
    rows = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except Exception:
                continue
    return rows


def save(rows):
    LOG_PATH.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    SNAP_PATH.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def load_queue():
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_queue(rows):
    QUEUE_PATH.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def interest_match(text: str) -> bool:
    lo = f" {text.lower()} "
    return any(k in lo for k in INTEREST_KEYWORDS)


def main():
    ap = argparse.ArgumentParser(description="Fallback jobsdb harvester via openclaw browser CLI")
    ap.add_argument("--target", type=int, default=200, help="minimum records to append this run")
    ap.add_argument("--max-pages", type=int, default=40, help="max pages per keyword")
    args = ap.parse_args()

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    skills = profile.get("skills", [])

    # Ensure browser is reachable
    run_browser("status")

    existing = load_existing()
    queue = load_queue()
    seen_urls = {r.get("url", "") for r in existing}
    seen_urls.update({r.get("url", "") for r in queue if isinstance(r, dict)})
    start_rejected_count = len(existing)
    start_queue_count = len(queue)
    evaluated = 0
    appended_rejected = 0
    appended_queue = 0

    eval_fn = r"""() => {
  const cards = Array.from(document.querySelectorAll('a'))
    .filter(a => (a.href || '').includes('/job/') && (a.href || '').includes('origin=cardTitle'))
    .map(a => {
      const article = a.closest('article') || a.parentElement;
      const txt = ((article && article.innerText) ? article.innerText : '').replace(/\s+/g, ' ').trim();
      return { title: (a.textContent || '').trim(), url: (a.href || ''), snippet: txt.slice(0, 1500) };
    });
  return { url: location.href, cards };
}"""

    for kw in ALLOWED_KEYWORDS:
        if evaluated >= args.target:
            break
        slug = urllib.parse.quote(kw.replace(" ", "-"))
        for page in range(1, args.max_pages + 1):
            if evaluated >= args.target:
                break
            url = f"https://hk.jobsdb.com/{slug}-jobs?page={page}"
            try:
                run_browser("navigate", url)
                run_browser("wait", "--time", "1200")
                out = run_browser("evaluate", "--fn", eval_fn)
                data = parse_json(out)
                cards = data.get("cards", [])
            except Exception as e:
                cards = []
            if not cards:
                continue

            for c in cards:
                if evaluated >= args.target:
                    break
                title = (c.get("title") or "").strip()
                jurl = normalize_url(c.get("url") or "")
                if not jurl or jurl in seen_urls:
                    continue
                snippet = c.get("snippet") or ""
                tlo = title.lower()
                salary = extract_salary_hkd(snippet)
                exp = extract_exp_years(snippet)
                combined_text = title + " " + snippet
                overlap = skill_overlap(combined_text, skills)
                has_interest = interest_match(combined_text)

                evaluated += 1
                if any(w in tlo for w in DISALLOWED_TITLE):
                    reason = "title_too_senior_preview"
                elif exp is not None and exp > 3:
                    reason = "experience_exceeds_preview"
                elif not has_interest and len(overlap) < 1:
                    reason = "skill_overlap_low_preview"
                else:
                    reason = "preview_candidate_needs_detail_validation"

                if reason == "preview_candidate_needs_detail_validation":
                    queue.append({
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "title": title,
                        "company": "",
                        "url": jurl,
                        "salaryMinHkd": salary,
                        "requiredExperienceYears": exp,
                        "skillOverlap": overlap,
                        "interestMatched": has_interest,
                        "keyword": kw,
                        "page": page,
                        "platform": "jobsdb",
                        "mode": "fallback_browser_cli",
                    })
                    appended_queue += 1
                else:
                    rec = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "title": title,
                        "company": "",
                        "url": jurl,
                        "reason": reason,
                        "salaryMinHkd": salary,
                        "requiredExperienceYears": exp,
                        "skillOverlapCount": len(overlap),
                        "interestMatched": has_interest,
                        "detailTextExtracted": False,
                        "detailTitle": "",
                        "keyword": kw,
                        "page": page,
                        "platform": "jobsdb",
                        "mode": "fallback_browser_cli",
                    }
                    existing.append(rec)
                    appended_rejected += 1
                seen_urls.add(jurl)

    save(existing)
    save_queue(queue)
    print(json.dumps({
        "status": "ok",
        "target": args.target,
        "evaluated": evaluated,
        "start_rejected_count": start_rejected_count,
        "start_queue_count": start_queue_count,
        "appended_rejected": appended_rejected,
        "appended_queue": appended_queue,
        "end_rejected_count": len(existing),
        "end_queue_count": len(queue)
    }, ensure_ascii=False))

    if evaluated < args.target:
        sys.exit(2)


if __name__ == "__main__":
    main()

