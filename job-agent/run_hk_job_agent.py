#!/usr/bin/env python3
import argparse
import datetime as dt
import email.utils
import json
import os
import re
import smtplib
import ssl
import subprocess
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any

try:
    import requests
except Exception:
    requests = None

try:
    import yaml
except Exception:
    yaml = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


DEFAULT_SKILLS = [
    "python",
    "sql",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "machine learning",
    "ai",
    "artificial intelligence",
    "deep learning",
    "llm",
    "nlp",
    "data analysis",
    "pytorch",
    "tensorflow",
]


@dataclass
class JobLead:
    source: str
    title: str
    company: str
    location: str
    url: str
    posted_date: str
    fit_score: float = 0.0
    snippet: str = ""
    salary_min_hkd: int | None = None
    required_experience_years: int | None = None
    skill_overlap_count: int = 0
    detail_text: str = ""
    detail_title: str = ""
    posted_age_days: int | None = None

    def dedupe_key(self) -> str:
        return "|".join(
            [
                self.company.lower().strip(),
                self.title.lower().strip(),
                self.location.lower().strip(),
                self.posted_date.strip(),
            ]
        )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return []


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_iso_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except Exception:
        return None


def prune_searched_history(
    searched: dict[str, dict[str, Any]],
    retention_days: int,
) -> dict[str, dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=max(1, int(retention_days)))
    out: dict[str, dict[str, Any]] = {}
    for url, rec in searched.items():
        last_seen_raw = str(rec.get("lastSeenAt", "") or rec.get("firstSeenAt", ""))
        last_seen = parse_iso_datetime(last_seen_raw)
        if last_seen is None:
            # Keep malformed legacy records once, then they will be rewritten with proper timestamp.
            out[url] = rec
            continue
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=dt.timezone.utc)
        if last_seen >= cutoff:
            out[url] = rec
    return out


def remember_searched_job(
    searched: dict[str, dict[str, Any]],
    lead: JobLead,
    keyword: str,
    platform: str,
    page: int,
) -> None:
    url = canonicalize_jobsdb_url(lead.url)
    if not url:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rec = searched.get(url)
    if rec is None:
        rec = {
            "url": url,
            "title": lead.title,
            "company": lead.company,
            "firstSeenAt": now,
            "lastSeenAt": now,
            "timesSeen": 1,
            "lastKeyword": keyword,
            "lastPlatform": platform,
            "lastPage": page,
        }
        searched[url] = rec
        return
    rec["lastSeenAt"] = now
    rec["timesSeen"] = int(rec.get("timesSeen", 0)) + 1
    rec["lastKeyword"] = keyword
    rec["lastPlatform"] = platform
    rec["lastPage"] = page
    if lead.title:
        rec["title"] = lead.title
    if lead.company:
        rec["company"] = lead.company


def read_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"CV PDF not found: {pdf_path}")
    if PdfReader is None:
        raise RuntimeError("Missing dependency pypdf. Install with: pip install pypdf")
    reader = PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    raw = "\n".join(chunks).replace("\xa0", " ").strip()
    # Fix OCR-like spaced capitals, e.g. "S K I L L S" -> "SKILLS".
    for _ in range(3):
        raw = re.sub(r"\b(?:[A-Za-z]\s){2,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), raw)
    return raw


def normalize_candidate_profile(cv_text: str, profile: dict[str, Any], cv_path: Path) -> dict[str, Any]:
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cv_text)
    phone_match = re.search(r"(\+?\d[\d\s\-()]{7,}\d)", cv_text)
    lines = []
    for raw_line in cv_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for _ in range(2):
            line = re.sub(r"\b(?:[A-Za-z]\s){2,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), line)
        lines.append(line)

    if not profile.get("fullName"):
        for line in lines[:12]:
            if re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{2,40}", line):
                profile["fullName"] = line
                break

    bad_name_markers = {"skills", "contact", "profile", "summary"}
    full_name = (profile.get("fullName") or "").strip()
    if full_name and full_name.lower().replace(" ", "") in bad_name_markers:
        profile["fullName"] = ""
    if not profile.get("fullName"):
        profile.setdefault("fullName", "Candidate")

    profile["location"] = profile.get("location") or "Hong Kong"
    profile["email"] = profile.get("email") or (email_match.group(0) if email_match else "")
    profile["phone"] = profile.get("phone") or (phone_match.group(1).strip() if phone_match else "")

    lowered = cv_text.lower()
    found_skills = sorted([s for s in DEFAULT_SKILLS if s in lowered])
    if found_skills:
        profile["skills"] = sorted(list(set((profile.get("skills") or []) + found_skills)))

    achievements: list[str] = []
    for line in lines:
        if re.search(r"\b(\d+%|\d+\+|increased|reduced|improved|delivered|achieved)\b", line.lower()):
            achievements.append(line)
    if achievements:
        profile["achievements"] = list(dict.fromkeys(achievements))[:8]

    evidence: list[str] = []
    for line in lines[:120]:
        if len(line) > 30:
            evidence.append(line)
    profile["evidence"] = list(dict.fromkeys(evidence))[:20]

    if not profile.get("headline"):
        profile["headline"] = "Candidate from CV extraction"

    if not profile.get("yearsOfExperience"):
        exp_match = re.search(r"(\d+)\+?\s+years", lowered)
        profile["yearsOfExperience"] = int(exp_match.group(1)) if exp_match else 0

    if not profile.get("industries"):
        profile["industries"] = ["Technology"]

    profile["sourceCv"] = str(cv_path)
    profile["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return profile


def brave_search(query: str, api_key: str, count: int = 5) -> list[dict[str, str]]:
    if requests is None:
        raise RuntimeError("Missing dependency requests. Install with: pip install requests")
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": count}
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    results = payload.get("web", {}).get("results", []) or []
    simplified = []
    for item in results:
        simplified.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
        )
    return simplified


def run_browser_cmd(args: list[str]) -> str:
    cmd = ["openclaw", "browser"] + args
    last_err = ""
    for attempt in range(3):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return proc.stdout.strip()
        last_err = proc.stderr or proc.stdout
        if "ERR_NETWORK_CHANGED" in last_err and attempt < 2:
            time.sleep(1.2)
            continue
        break
    raise RuntimeError(f"Browser command failed: {' '.join(cmd)}\n{last_err}")


def snapshot_has_login_wall(snapshot_text: str) -> bool:
    t = snapshot_text.lower()
    wall_markers = [
        "sign in",
        "log in",
        "create alert",
        "we couldn't find that page",
        "404 page not found",
    ]
    has_markers = sum(1 for m in wall_markers if m in t)
    has_cards = 'article "' in snapshot_text
    return (has_markers >= 2 and not has_cards) or ("404 page not found" in t)


def jobsdb_search_url(
    keyword: str = "machine learning",
    location: str = "Hong Kong SAR",
    page: int = 1,
    daterange_days: int = 7,
) -> str:
    k = keyword.strip().replace(" ", "-")
    loc = location.strip().replace(" ", "-")
    base = f"https://hk.jobsdb.com/{k}-jobs/in-{loc}"
    return f"{base}?page={page}&daterange={max(1, int(daterange_days))}"


def parse_jobsdb_cards_from_snapshot(snapshot_text: str, max_cards: int) -> list[JobLead]:
    lines = snapshot_text.splitlines()
    leads: list[JobLead] = []

    # Split snapshot by article blocks so title/company/url are bound in the same card.
    article_indices = [idx for idx, line in enumerate(lines) if 'article "' in line]
    for pos, start in enumerate(article_indices):
        if len(leads) >= max_cards:
            break
        end = article_indices[pos + 1] if pos + 1 < len(article_indices) else min(len(lines), start + 120)
        block = lines[start:end]
        if not block:
            continue

        m_title = re.search(r'article "([^"]+)"', block[0])
        if not m_title:
            continue
        title = m_title.group(1).strip()
        company = "Unknown Company"
        rel_url = ""
        snippet_parts: list[str] = []

        for s in block:
            if "Jobs at " in s:
                mc = re.search(r'Jobs at ([^"]+)', s)
                if mc:
                    company = mc.group(1).strip()
            # Prefer card-title URL when available; otherwise accept any /job/ URL in same block.
            mu = re.search(r'/url:\s+(/job/[^\s]+)', s)
            if mu and (("origin=cardTitle" in s) or not rel_url):
                rel_url = mu.group(1).split("#")[0]
            if "Salary:" in s or "year" in s.lower() or "experience" in s.lower():
                snippet_parts.append(s.strip())
            if "Listed " in s:
                snippet_parts.append(s.strip())

        if rel_url.startswith("/job/"):
            leads.append(
                JobLead(
                    source="jobsdb_browser",
                    title=title,
                    company=company,
                    location="Hong Kong",
                    url="https://hk.jobsdb.com" + rel_url,
                    posted_date=dt.date.today().isoformat(),
                    snippet=" | ".join(snippet_parts),
                )
            )
    return leads


def extract_detail_title_from_snapshot(snapshot_text: str) -> str:
    if not snapshot_text:
        return ""
    lines = snapshot_text.splitlines()
    # Prefer first page-level heading.
    for line in lines:
        mh = re.search(r'heading "([^"]+)"', line)
        if mh:
            return mh.group(1).strip()
    # Fallback to root web area title.
    mroot = re.search(r'RootWebArea "([^"]+)"', snapshot_text)
    if mroot:
        return mroot.group(1).strip()
    return ""


def normalize_title_for_match(title: str) -> list[str]:
    t = re.sub(r"[^a-z0-9\s+#]", " ", title.lower())
    parts = [x for x in t.split() if x and x not in {"the", "and", "for", "in", "at", "hk", "hong", "kong"}]
    return parts


def title_matches_card(card_title: str, detail_title: str) -> bool:
    if not card_title or not detail_title:
        return False
    a = normalize_title_for_match(card_title)
    b = normalize_title_for_match(detail_title)
    if not a or not b:
        return False
    inter = set(a).intersection(set(b))
    ratio = len(inter) / max(1, min(len(set(a)), len(set(b))))
    return ratio >= 0.45


def analyze_card_preview(lead: JobLead, profile: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    title_l = (lead.title or "").lower()
    disallowed = [x.lower() for x in config.get("disallowedTitleKeywords", [])]
    if any(k in title_l for k in disallowed):
        return False, "title_too_senior_preview"

    preview_text = f"{lead.title} {lead.snippet}".strip()
    if not preview_text:
        return False, "preview_empty"

    lead.posted_age_days = parse_posted_age_days(preview_text)
    max_age = int(config.get("maxJobAgeDays", 7))
    if lead.posted_age_days is not None and lead.posted_age_days > max_age:
        return False, "posting_too_old_preview"

    # If salary is present on card, enforce range early. Missing salary is allowed.
    salary_preview = parse_salary_min_hkd(preview_text)
    if salary_preview is not None:
        if salary_preview < int(config.get("minSalaryHkd", 25000)):
            return False, "salary_too_low_preview"
        max_salary = int(config.get("maxSalaryHkd", 35000))
        if salary_preview > max_salary:
            return False, "salary_too_high_preview"

    exp_preview = parse_required_experience_years(preview_text)
    if exp_preview is not None and exp_preview > int(config.get("maxRequiredExperienceYears", 1)):
        return False, "experience_too_high_preview"

    profile_skills = profile.get("skills", []) or []
    overlap_preview = compute_skill_overlap(profile_skills=profile_skills, text=preview_text)
    min_preview_overlap = int(config.get("minSkillOverlapPreview", 1))
    if overlap_preview < min_preview_overlap:
        return False, "skill_overlap_low_preview"

    return True, "ok"


def collect_jobsdb_leads_via_browser(
    keyword: str,
    page: int,
    max_cards: int,
    profile: dict[str, Any],
    config: dict[str, Any],
) -> tuple[list[JobLead], list[dict[str, Any]]]:
    status_raw = run_browser_cmd(["--json", "status"])
    status = json.loads(status_raw)
    if not status.get("running"):
        raise RuntimeError("OpenClaw browser is not running. Start Chromium CDP first.")

    run_browser_cmd(
        [
            "navigate",
            jobsdb_search_url(
                keyword=keyword,
                page=page,
                daterange_days=int(config.get("maxJobAgeDays", 7)),
            ),
        ]
    )
    snapshot = run_browser_cmd(["snapshot", "--limit", "1600"])
    if snapshot_has_login_wall(snapshot):
        raise RuntimeError("JobsDB appears gated by login/404 for current session. Please login manually first, then rerun.")
    leads = parse_jobsdb_cards_from_snapshot(snapshot_text=snapshot, max_cards=max_cards)
    if not leads:
        raise RuntimeError("Failed to extract JobsDB job cards from browser snapshot.")

    preview_rejected: list[dict[str, Any]] = []
    screened: list[JobLead] = []
    for lead in leads:
        ok, reason = analyze_card_preview(lead=lead, profile=profile, config=config)
        if not ok:
            preview_rejected.append(
                {
                    "title": lead.title,
                    "company": lead.company,
                    "url": lead.url,
                    "reason": reason,
                    "salaryMinHkd": parse_salary_min_hkd(lead.snippet),
                    "requiredExperienceYears": parse_required_experience_years(lead.snippet),
                    "skillOverlapCount": compute_skill_overlap(profile.get("skills", []) or [], f"{lead.title} {lead.snippet}"),
                    "detailTextExtracted": False,
                    "detailTitle": "",
                    "postedAgeDays": lead.posted_age_days,
                }
            )
            continue
        screened.append(lead)

    # Read JD one by one only for pre-screened cards.
    for lead in screened:
        try:
            run_browser_cmd(["navigate", lead.url])
            detail = run_browser_cmd(["snapshot", "--limit", "1400"])
            if snapshot_has_login_wall(detail):
                lead.detail_text = ""
                continue
            lead.detail_text = detail
            lead.detail_title = extract_detail_title_from_snapshot(detail)
        except Exception:
            lead.detail_text = ""
            lead.detail_title = ""
    return screened, preview_rejected


def collect_ctgoodjobs_leads_via_search(
    keyword: str,
    max_cards: int,
    profile: dict[str, Any],
    config: dict[str, Any],
    brave_key: str,
) -> tuple[list[JobLead], list[dict[str, Any]]]:
    query = f'site:jobs.ctgoodjobs.hk/job "{keyword}" "Hong Kong"'
    rows = brave_search(query=query, api_key=brave_key, count=max_cards * 3)
    leads: list[JobLead] = []
    preview_rejected: list[dict[str, Any]] = []

    for row in rows:
        url = row.get("url", "")
        if "/job/" not in url:
            continue
        title = (row.get("title", "") or "").strip()
        description = (row.get("description", "") or "").strip()
        lead = JobLead(
            source="ctgoodjobs_search",
            title=title or "Unknown Role",
            company="Unknown Company",
            location="Hong Kong",
            url=url,
            posted_date=dt.date.today().isoformat(),
            snippet=description,
        )
        ok, reason = analyze_card_preview(lead=lead, profile=profile, config=config)
        if not ok:
            preview_rejected.append(
                {
                    "title": lead.title,
                    "company": lead.company,
                    "url": lead.url,
                    "reason": reason,
                    "salaryMinHkd": parse_salary_min_hkd(lead.snippet),
                    "requiredExperienceYears": parse_required_experience_years(lead.snippet),
                    "skillOverlapCount": compute_skill_overlap(profile.get("skills", []) or [], f"{lead.title} {lead.snippet}"),
                    "detailTextExtracted": False,
                    "detailTitle": "",
                    "postedAgeDays": lead.posted_age_days,
                }
            )
            continue
        leads.append(lead)
        if len(leads) >= max_cards:
            break

    for lead in leads:
        try:
            run_browser_cmd(["navigate", lead.url])
            detail = run_browser_cmd(["snapshot", "--limit", "1400"])
            if snapshot_has_login_wall(detail):
                lead.detail_text = ""
                continue
            lead.detail_text = detail
            lead.detail_title = extract_detail_title_from_snapshot(detail)
        except Exception:
            lead.detail_text = ""
            lead.detail_title = ""
    return leads, preview_rejected


def canonicalize_jobsdb_url(url: str) -> str:
    if not url:
        return url
    return url.split("#")[0].split("?")[0]


def parse_lead_from_search(source_name: str, item: dict[str, str], default_location: str) -> JobLead:
    title_raw = item.get("title", "").strip()
    company = "Unknown Company"
    role = title_raw or "Unknown Role"

    parts = re.split(r"\s[-|]\s", title_raw)
    if len(parts) >= 2:
        role = parts[0].strip()
        company = parts[1].strip()

    return JobLead(
        source=source_name,
        title=role,
        company=company,
        location=default_location,
        url=item.get("url", ""),
        posted_date=dt.date.today().isoformat(),
        snippet=item.get("description", ""),
    )


def is_generic_listing(lead: JobLead) -> bool:
    t = f"{lead.title} {lead.company} {lead.url}".lower()
    generic_markers = [
        "jobs in",
        "search result",
        "all jobs",
        "/jobs/jobs-in-",
        "/jobs/search",
        "job list",
        "ctgoodjobs",
        "-jobs",
    ]
    return any(m in t for m in generic_markers)


def collect_job_leads(sources_yaml: Path, max_per_source: int, brave_key: str | None) -> list[JobLead]:
    if yaml is None:
        raise RuntimeError("Missing dependency pyyaml. Install with: pip install pyyaml")
    cfg = yaml.safe_load(sources_yaml.read_text(encoding="utf-8"))
    region = cfg.get("region", "Hong Kong")
    out: list[JobLead] = []
    fallback_raw: list[JobLead] = []
    for source in cfg.get("sources", []):
        if not source.get("enabled", False):
            continue
        query = source.get("query", "").strip()
        if not query or not brave_key:
            continue
        rows = brave_search(query=query, api_key=brave_key, count=max_per_source)
        for row in rows:
            lead = parse_lead_from_search(source_name=source["name"], item=row, default_location=region)
            fallback_raw.append(lead)
            if not is_generic_listing(lead):
                out.append(lead)
    if not out and fallback_raw:
        preferred = [x for x in fallback_raw if "/job/" in x.url.lower() or re.search(r"/jobs?/[0-9a-z-]+", x.url.lower())]
        out = (preferred or [x for x in fallback_raw if not is_generic_listing(x)])[:1]
    if not out:
        raise RuntimeError("No specific AI/ML job detail page found from current sources.")
    dedup = {}
    for lead in out:
        dedup[lead.dedupe_key()] = lead
    return list(dedup.values())


def rank_job_leads(leads: list[JobLead], profile: dict[str, Any]) -> list[JobLead]:
    skills = [x.lower() for x in profile.get("skills", [])]
    headline = (profile.get("headline") or "").lower()
    for lead in leads:
        text = f"{lead.title} {lead.company} {lead.snippet}".lower()
        score = 0.0
        score += sum(1 for s in skills if s in text)
        if headline and any(tok in text for tok in headline.split()):
            score += 0.5
        lead.fit_score = score
    return sorted(leads, key=lambda x: x.fit_score, reverse=True)


def fetch_job_page_text(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")) or requests is None:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 job-agent/1.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text
        html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""


def parse_salary_min_hkd(text: str) -> int | None:
    if not text:
        return None
    lowered = text.lower()
    if ("hkd" not in lowered) and ("hk$" not in lowered) and ("$" not in lowered):
        return None
    values = []
    for m in re.finditer(r"(?:hk\$|\$|hkd)?\s*([0-9]{2,3}(?:[,][0-9]{3})+|[0-9]{4,6})", lowered):
        raw = m.group(1).replace(",", "")
        try:
            val = int(raw)
            if 5000 <= val <= 200000:
                values.append(val)
        except ValueError:
            pass
    for m in re.finditer(r"([0-9]{2,3})\s*[kK]", text):
        try:
            val = int(m.group(1)) * 1000
            if 5000 <= val <= 200000:
                values.append(val)
        except ValueError:
            pass
    return min(values) if values else None


def parse_required_experience_years(text: str) -> int | None:
    if not text:
        return None
    lowered = text.lower()
    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    range_match = re.search(r"(\d+)\s*[-~to]{1,3}\s*(\d+)\s*(?:years|year)", lowered)
    if range_match:
        return int(range_match.group(2))
    plus_match = re.search(r"(\d+)\+?\s*(?:years|year)\s*(?:of\s*)?experience", lowered)
    if plus_match:
        return int(plus_match.group(1))
    simple_match = re.search(r"(?:minimum|min)\s*(\d+)\s*(?:years|year)", lowered)
    if simple_match:
        return int(simple_match.group(1))
    any_num_year = re.search(r"(\d+)\s*(?:\+?\s*)?(?:years|year)\b", lowered)
    if any_num_year:
        return int(any_num_year.group(1))
    word_year = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:years|year)\b", lowered)
    if word_year:
        return word_to_num.get(word_year.group(1))
    return None


def parse_posted_age_days(text: str) -> int | None:
    if not text:
        return None
    lowered = text.lower()
    if "today" in lowered or "just posted" in lowered or "few hours" in lowered:
        return 0
    if "yesterday" in lowered:
        return 1
    m_day = re.search(r"(\d+)\s*(?:day|days)\s*ago", lowered)
    if m_day:
        return int(m_day.group(1))
    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    m_day_word = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:day|days)\s*ago\b", lowered)
    if m_day_word:
        return word_to_num.get(m_day_word.group(1))
    m_week = re.search(r"(\d+)\s*(?:week|weeks)\s*ago", lowered)
    if m_week:
        return int(m_week.group(1)) * 7
    return None


def compute_skill_overlap(profile_skills: list[str], text: str) -> int:
    hay = text.lower()
    return sum(1 for s in profile_skills if s.lower() in hay)


def analyze_lead_against_requirements(lead: JobLead, profile: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    title_l = lead.title.lower()
    disallowed = [x.lower() for x in config.get("disallowedTitleKeywords", [])]
    if any(k in title_l for k in disallowed):
        return False, "title_too_senior"

    page_text = lead.detail_text
    if not page_text:
        return False, "detail_not_readable"
    if not title_matches_card(lead.title, lead.detail_title):
        return False, "title_url_mismatch"
    combined = f"{lead.title} {lead.company} {lead.snippet} {page_text}".strip()
    if "404 page not found" in combined.lower():
        return False, "detail_page_invalid"
    if lead.url and ("/job/" not in lead.url):
        return False, "non_detail_url"
    age_days = parse_posted_age_days(combined)
    if age_days is None:
        age_days = lead.posted_age_days
    lead.posted_age_days = age_days
    max_age = int(config.get("maxJobAgeDays", 7))
    if age_days is not None and age_days > max_age:
        return False, "posting_too_old"
    lead.salary_min_hkd = parse_salary_min_hkd(combined)
    # Salary may be missing; only reject when salary is explicitly out of range.
    if lead.salary_min_hkd is not None:
        if lead.salary_min_hkd < int(config.get("minSalaryHkd", 25000)):
            return False, "salary_too_low"
        max_salary = int(config.get("maxSalaryHkd", 35000))
        if lead.salary_min_hkd > max_salary:
            return False, "salary_too_high"

    lead.required_experience_years = parse_required_experience_years(combined)
    if lead.required_experience_years is None:
        return False, "experience_missing"
    if lead.required_experience_years > int(config.get("maxRequiredExperienceYears", 1)):
        return False, "experience_too_high"

    profile_skills = profile.get("skills", []) or []
    lead.skill_overlap_count = compute_skill_overlap(profile_skills=profile_skills, text=combined)
    if lead.skill_overlap_count < int(config.get("minSkillOverlap", 1)):
        return False, "skill_overlap_low"

    reqs = extract_requirements(job_text=page_text, fallback_snippet=lead.snippet)
    if not reqs:
        return False, "requirements_missing"
    return True, "ok"


def extract_requirements(job_text: str, fallback_snippet: str) -> list[str]:
    content = f"{job_text}. {fallback_snippet}".strip()
    if not content:
        return []
    parts = re.split(r"(?<=[.!?])\s+", content)
    keys = ("require", "responsib", "experience", "skill", "proficient", "familiar", "knowledge", "python", "ai", "machine learning", "nlp", "llm")
    bad = (
        "better job searching experience",
        "update your profile",
        "daily-updated",
        "browse through all",
        "create alert",
        "incorrect email address",
        "login name",
        "password should contain",
    )
    picked = []
    for p in parts:
        pl = p.lower()
        if len(p) < 40 or len(p) > 220:
            continue
        if any(b in pl for b in bad):
            continue
        if any(x in pl for x in ("[ref=", "listitem", "rootwebarea", "how many years' experience do you have")):
            continue
        p = re.sub(r"\s*\[ref=[^\]]+\]", "", p).strip()
        p = re.sub(r"\s+", " ", p).strip(" -:")
        if any(k in pl for k in keys):
            picked.append(p.strip())
        if len(picked) >= 3:
            break
    noisy_markers = ("matching jobs", "email shortly", "job details: located")
    noisy_count = sum(1 for x in picked if any(m in x.lower() for m in noisy_markers))
    if picked and noisy_count >= max(1, len(picked) // 2):
        return []
    return picked


def infer_requirements_from_title(title: str) -> list[str]:
    t = title.lower()
    reqs = []
    if "engagement manager" in t or "manager" in t:
        reqs.extend(
            [
                "Lead end-to-end delivery of AI initiatives and coordinate business/technical stakeholders.",
                "Translate business goals into executable AI and analytics workstreams with measurable outcomes.",
                "Drive adoption of AI solutions and ensure sustainable operational handover.",
            ]
        )
    if "machine learning" in t or "ai" in t:
        reqs.extend(
            [
                "Hands-on understanding of machine learning workflows, model development, and evaluation.",
                "Ability to communicate AI concepts clearly to non-technical stakeholders.",
            ]
        )
    return reqs[:3]


def extract_keywords(lines: list[str]) -> set[str]:
    stop = {
        "with",
        "from",
        "that",
        "this",
        "have",
        "your",
        "will",
        "role",
        "team",
        "hong",
        "kong",
        "years",
        "experience",
    }
    out: set[str] = set()
    for line in lines:
        for tok in re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{3,}", line.lower()):
            if tok not in stop:
                out.add(tok)
    return out


def select_cv_evidence(profile: dict[str, Any], requirements: list[str]) -> list[str]:
    evidence = profile.get("evidence", []) or []
    achievements = profile.get("achievements", []) or []
    pool = evidence + achievements
    req_kw = extract_keywords(requirements)
    if not pool:
        return []
    scored: list[tuple[int, str]] = []
    for line in pool:
        l = line.strip()
        if len(l) < 30:
            continue
        if re.search(r"(?:\b[a-zA-Z]\b\s+){3,}", l):
            continue
        if "  " in l:
            continue
        score = sum(1 for kw in req_kw if kw in l.lower())
        score += sum(1 for kw in ["project", "experienced", "machine", "learning", "nlp", "database"] if kw in l.lower())
        scored.append((score, l))
    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = [x[1] for x in scored[:3] if x[1]]
    if not chosen:
        chosen = pool[:3]
    return chosen


def render_email(profile: dict[str, Any], lead: JobLead, requirements: list[str], evidence: list[str]) -> tuple[str, str]:
    subject = f"Application for {lead.title} - {profile.get('fullName', 'Candidate')}"
    effective_requirements = requirements or infer_requirements_from_title(lead.title)
    req_focus = "; ".join(effective_requirements[:2]) if effective_requirements else "hands-on AI/ML solution delivery"
    skills = ", ".join(profile.get("skills", [])[:8]) or "machine learning, AI engineering, and data systems"
    clean_evidence = []
    for x in evidence:
        line = re.sub(r"\s+", " ", x).strip(" -:")
        if len(line) < 35:
            continue
        if any(tok in line.lower() for tok in ("[ref=", "listitem", "matched skill overlap", "parsed salary", "parsed experience")):
            continue
        clean_evidence.append(line)
    evidence_line = clean_evidence[0] if clean_evidence else "My recent projects focused on applied machine learning and NLP problem-solving in practical settings."

    body = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to apply for the {lead.title} position at {lead.company}. "
        f"After reviewing the job description ({lead.url}), I believe my background is aligned with your requirements.\n\n"
        f"I am currently based in Hong Kong, with hands-on experience in {skills}. "
        f"My project work has focused on practical machine learning implementation and NLP applications, and I am comfortable translating technical work into clear business outcomes.\n\n"
        f"For this role, I can contribute in areas such as {req_focus}. "
        f"One relevant example from my background is: {evidence_line}\n\n"
        f"I have attached my CV for your review. Thank you for your time and consideration, and I would welcome the opportunity to discuss how I can contribute to your team.\n\n"
        f"Best regards,\n"
        f"{profile.get('fullName', 'Candidate')}\n"
        f"{profile.get('email', '')}\n"
        f"{profile.get('phone', '')}\n\n"
        f"Note: This email is automatically generated and sent by openclaw\n"
    )
    return subject, body


def ensure_formal_email_body(body: str) -> None:
    bad_markers = [
        "matched skill overlap count",
        "parsed salary baseline",
        "parsed experience requirement",
        "[ref=",
        "listitem",
        "rootwebarea",
    ]
    lowered = body.lower()
    if any(x in lowered for x in bad_markers):
        raise RuntimeError("Generated email body contains internal/debug markers; sending aborted.")


def read_smtp_from_openclaw() -> dict[str, str]:
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    if not cfg_path.exists():
        return {}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        env_cfg = cfg.get("skills", {}).get("entries", {}).get("send-email", {}).get("env", {})
        return {
            "server": str(env_cfg.get("EMAIL_SMTP_SERVER", "")),
            "port": str(env_cfg.get("EMAIL_SMTP_PORT", "")),
            "sender": str(env_cfg.get("EMAIL_SENDER", "")),
            "password": str(env_cfg.get("EMAIL_SMTP_PASSWORD", "")),
        }
    except Exception:
        return {}


def send_email(
    smtp_server: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
    attachment: Path,
    retry_count: int,
) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment.exists():
        data = attachment.read_bytes()
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=attachment.name)

    context = ssl.create_default_context()
    last_err = None
    for _ in range(retry_count + 1):
        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as s:
                s.starttls(context=context)
                s.login(sender, password)
                s.send_message(msg)
            return
        except Exception as exc:
            last_err = exc
            time.sleep(1)
    raise RuntimeError(f"Email send failed after retries: {last_err}")


def validate_recipient(recipient: str, allowed: list[str]) -> None:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient):
        raise ValueError(f"Invalid recipient email: {recipient}")
    if allowed and recipient.lower() not in {x.lower() for x in allowed}:
        raise ValueError(f"Recipient not in allowlist: {recipient}")


def build_queue(leads: list[JobLead], recipient: str) -> list[dict[str, Any]]:
    queue = []
    for lead in leads:
        queue.append(
            {
                "recipient": recipient,
                "company": lead.company,
                "role": lead.title,
                "location": lead.location,
                "source": lead.source,
                "url": lead.url,
                "postedDate": lead.posted_date,
                "fitScore": lead.fit_score,
                "snippet": lead.snippet,
                "salaryMinHkd": lead.salary_min_hkd,
                "requiredExperienceYears": lead.required_experience_years,
                "skillOverlapCount": lead.skill_overlap_count,
                "detailTextExtracted": bool(lead.detail_text),
                "detailTitle": lead.detail_title,
                "postedAgeDays": lead.posted_age_days,
            }
        )
    return queue


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HK job agent pipeline")
    parser.add_argument("--config", default="job-agent/config.json")
    parser.add_argument("--cv", default=None, help="Override CV PDF path")
    parser.add_argument("--recipient", default=None, help="Override target recipient")
    parser.add_argument("--send-test-only", action="store_true", help="Send one test email only")
    parser.add_argument("--no-send", action="store_true", help="Build outputs but do not send email")
    parser.add_argument("--job-url", default=None, help="Force a specific job description URL")
    parser.add_argument("--job-title", default="Machine Learning Engineer", help="Title for forced job URL")
    parser.add_argument("--job-company", default="Target Company", help="Company for forced job URL")
    parser.add_argument("--once", action="store_true", help="Run one scan cycle only (debug)")
    args = parser.parse_args()

    root = Path.cwd()
    config_path = root / args.config
    config = load_json(config_path)
    target_email_count = max(1, int(config.get("targetEmailsPerRun", 5)))

    recipient = args.recipient or config["targetRecipient"]
    validate_recipient(recipient, config.get("allowedRecipients", []))

    cv_path = Path(args.cv or config["attachments"]["cvPath"])
    profile_path = root / "job-agent/candidate-profile.json"
    leads_path = root / "job-agent/job-leads.json"
    queue_path = root / "job-agent/send-queue.json"
    log_path = root / "job-agent/logs/applications.log"
    preview_path = root / "job-agent/logs/last_email_preview.txt"
    rejected_path = root / "job-agent/rejected-leads.json"
    rejected_history_path = root / "job-agent/rejected-leads.log.jsonl"
    searched_history_path = root / "job-agent/searched-jobs.json"

    profile = load_json(profile_path)
    cv_text = read_pdf_text(cv_path)
    profile = normalize_candidate_profile(cv_text=cv_text, profile=profile, cv_path=cv_path)
    save_json(profile_path, profile)

    if args.job_url:
        lead = JobLead(
            source="manual_url",
            title=args.job_title,
            company=args.job_company,
            location="Hong Kong",
            url=canonicalize_jobsdb_url(args.job_url),
            posted_date=dt.date.today().isoformat(),
            fit_score=1.0,
            snippet="Manual job URL provided by user",
        )
        try:
            run_browser_cmd(["navigate", lead.url])
            detail = run_browser_cmd(["snapshot", "--limit", "1400"])
            if not snapshot_has_login_wall(detail):
                lead.detail_text = detail
                lead.detail_title = extract_detail_title_from_snapshot(detail)
        except Exception:
            pass
        leads = [lead]
    elif args.send_test_only:
        leads = [
            JobLead(
                source="smoke_test",
                title="Test Application Flow",
                company="Test Inbox",
                location="Hong Kong",
                url="local://smoke-test",
                posted_date=dt.date.today().isoformat(),
                fit_score=1.0,
            )
        ]
    else:
        brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        search_keywords = config.get("searchKeywords", ["machine learning", "ai engineer", "llm developer"])
        platform_order = config.get("platformOrder", ["jobsdb", "ctgoodjobs"])
        skip_previously_searched = bool(config.get("skipPreviouslySearchedJobs", True))
        searched_history_retention_days = int(config.get("searchedHistoryRetentionDays", 7))
        default_keyword_limit = int(config.get("perKeywordLeadLimit", 50))
        keyword_limit_overrides_raw = config.get("keywordLeadLimits", {}) or {}
        keyword_limit_overrides = {
            str(k).strip().lower(): int(v) for k, v in keyword_limit_overrides_raw.items() if str(k).strip()
        }
        keyword_seen_counts: dict[str, int] = {str(k).strip().lower(): 0 for k in search_keywords}
        max_cards = int(config.get("maxLeadsPerRun", 8))
        max_pages_per_keyword = int(config.get("maxPagesPerKeyword", 8))
        max_consecutive_no_candidate_pages = int(config.get("maxConsecutiveNoCandidatePages", 3))
        poll_seconds = int(config.get("pollIntervalSeconds", 30))
        searched_history = load_json_list(searched_history_path)
        searched_map: dict[str, dict[str, Any]] = {
            canonicalize_jobsdb_url(str(x.get("url", ""))): x
            for x in searched_history
            if canonicalize_jobsdb_url(str(x.get("url", "")))
        }
        searched_map = prune_searched_history(
            searched=searched_map,
            retention_days=searched_history_retention_days,
        )
        seen_urls: set[str] = set(searched_map.keys()) if skip_previously_searched else set()
        qualified: list[JobLead] = []
        rejected: list[dict[str, Any]] = []

        def keyword_limit(keyword: str) -> int:
            key = keyword.strip().lower()
            return keyword_limit_overrides.get(key, default_keyword_limit)

        while len(qualified) < target_email_count:
            for platform in platform_order:
                for keyword in search_keywords:
                    key_l = keyword.strip().lower()
                    if key_l not in keyword_seen_counts:
                        keyword_seen_counts[key_l] = 0
                    if keyword_seen_counts[key_l] >= keyword_limit(keyword):
                        continue
                    page = 1
                    no_candidate_pages = 0
                    keyword_limit_reached = False
                    while True:
                        try:
                            if platform == "jobsdb":
                                leads_batch, preview_rejected = collect_jobsdb_leads_via_browser(
                                    keyword=keyword,
                                    page=page,
                                    max_cards=max_cards,
                                    profile=profile,
                                    config=config,
                                )
                                platform_url = jobsdb_search_url(
                                    keyword=keyword,
                                    page=page,
                                    daterange_days=int(config.get("maxJobAgeDays", 7)),
                                )
                            elif platform == "ctgoodjobs":
                                if not brave_key:
                                    raise RuntimeError("BRAVE_SEARCH_API_KEY missing for ctgoodjobs discovery.")
                                leads_batch, preview_rejected = collect_ctgoodjobs_leads_via_search(
                                    keyword=keyword,
                                    max_cards=max_cards,
                                    profile=profile,
                                    config=config,
                                    brave_key=brave_key,
                                )
                                platform_url = f"https://jobs.ctgoodjobs.hk/job?q={keyword.replace(' ', '+')}"
                            else:
                                raise RuntimeError(f"Unsupported platform in config: {platform}")

                            for rec in preview_rejected:
                                rec["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
                                rec["keyword"] = keyword
                                rec["page"] = page
                                rec["platform"] = platform
                                rec["keywordSeenCount"] = keyword_seen_counts.get(key_l, 0)
                                rec["keywordLimit"] = keyword_limit(keyword)
                                rejected.append(rec)
                                append_jsonl(rejected_history_path, rec)
                        except Exception as exc:
                            rec = {
                                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                                "title": "",
                                "company": "",
                                "url": platform_url if "platform_url" in locals() else "",
                                "reason": "browser_navigation_error",
                                "error": str(exc),
                                "salaryMinHkd": None,
                                "requiredExperienceYears": None,
                                "skillOverlapCount": 0,
                                "detailTextExtracted": False,
                                "detailTitle": "",
                                "keyword": keyword,
                                "page": page,
                                "platform": platform,
                                "keywordSeenCount": keyword_seen_counts.get(key_l, 0),
                                "keywordLimit": keyword_limit(keyword),
                            }
                            rejected.append(rec)
                            append_jsonl(rejected_history_path, rec)
                            break

                        if not leads_batch:
                            no_candidate_pages += 1
                            if platform == "ctgoodjobs":
                                break
                            if no_candidate_pages >= max_consecutive_no_candidate_pages:
                                break
                            page += 1
                            if page > max_pages_per_keyword:
                                break
                            continue

                        no_candidate_pages = 0
                        for lead in leads_batch:
                            lead.url = canonicalize_jobsdb_url(lead.url)
                            if lead.url in seen_urls:
                                continue
                            seen_urls.add(lead.url)
                            remember_searched_job(
                                searched=searched_map,
                                lead=lead,
                                keyword=keyword,
                                platform=platform,
                                page=page,
                            )
                            keyword_seen_counts[key_l] = keyword_seen_counts.get(key_l, 0) + 1
                            if keyword_seen_counts[key_l] > keyword_limit(keyword):
                                keyword_limit_reached = True
                                break
                            ok, reason = analyze_lead_against_requirements(lead=lead, profile=profile, config=config)
                            if ok:
                                qualified.append(lead)
                                if len(qualified) >= target_email_count:
                                    break
                                continue
                            rec = {
                                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                                "title": lead.title,
                                "company": lead.company,
                                "url": lead.url,
                                "reason": reason,
                                "salaryMinHkd": lead.salary_min_hkd,
                                "requiredExperienceYears": lead.required_experience_years,
                                "skillOverlapCount": lead.skill_overlap_count,
                                "detailTextExtracted": bool(lead.detail_text),
                                "detailTitle": lead.detail_title,
                                "postedAgeDays": lead.posted_age_days,
                                "keyword": keyword,
                                "page": page,
                                "platform": platform,
                                "keywordSeenCount": keyword_seen_counts.get(key_l, 0),
                                "keywordLimit": keyword_limit(keyword),
                            }
                            rejected.append(rec)
                            append_jsonl(rejected_history_path, rec)
                        if len(qualified) >= target_email_count:
                            break
                        if keyword_limit_reached:
                            break
                        if platform == "ctgoodjobs":
                            break
                        page += 1
                        if page > max_pages_per_keyword:
                            break
                    if len(qualified) >= target_email_count:
                        break
                if len(qualified) >= target_email_count:
                    break
            save_json(rejected_path, rejected)
            save_json(searched_history_path, list(searched_map.values()))
            if len(qualified) >= target_email_count:
                break
            all_keywords_exhausted = all(
                keyword_seen_counts.get(str(k).strip().lower(), 0) >= keyword_limit(str(k))
                for k in search_keywords
            )
            if all_keywords_exhausted:
                if args.once:
                    raise RuntimeError(
                        f"Only found {len(qualified)} qualified jobs in one scan cycle, target is {target_email_count}. "
                        "Keyword limits were exhausted."
                    )
                # Reset per-keyword counters and keep polling for fresh jobs instead of exiting.
                keyword_seen_counts = {str(k).strip().lower(): 0 for k in search_keywords}
                time.sleep(max(30, poll_seconds))
                continue
            if args.once:
                raise RuntimeError(
                    f"Only found {len(qualified)} qualified jobs in one scan cycle, target is {target_email_count}. "
                    "See job-agent/rejected-leads.json and rejected-leads.log.jsonl."
                )
            time.sleep(max(10, poll_seconds))
        leads = qualified[:target_email_count]

    if not args.send_test_only and (args.job_url or args.send_test_only):
        qualified: list[JobLead] = []
        rejected: list[dict[str, Any]] = []
        for lead in leads:
            ok, reason = analyze_lead_against_requirements(lead=lead, profile=profile, config=config)
            if ok:
                qualified.append(lead)
            else:
                rejected.append(
                    {
                        "title": lead.title,
                        "company": lead.company,
                        "url": lead.url,
                        "reason": reason,
                        "salaryMinHkd": lead.salary_min_hkd,
                        "requiredExperienceYears": lead.required_experience_years,
                        "skillOverlapCount": lead.skill_overlap_count,
                        "detailTextExtracted": bool(lead.detail_text),
                        "detailTitle": lead.detail_title,
                    }
                )
                append_jsonl(rejected_history_path, rejected[-1])
        save_json(rejected_path, rejected)
        if not qualified:
            raise RuntimeError(
                "No jobs matched required filters. See job-agent/rejected-leads.json for exact rejection reasons."
            )
        leads = rank_job_leads(leads=qualified, profile=profile)[:1]

    leads_json = [
        {
            "source": x.source,
            "title": x.title,
            "company": x.company,
            "location": x.location,
            "url": x.url,
            "postedDate": x.posted_date,
            "fitScore": x.fit_score,
            "snippet": x.snippet,
            "salaryMinHkd": x.salary_min_hkd,
            "requiredExperienceYears": x.required_experience_years,
            "skillOverlapCount": x.skill_overlap_count,
            "detailTextExtracted": bool(x.detail_text),
            "detailTitle": x.detail_title,
            "postedAgeDays": x.posted_age_days,
        }
        for x in leads
    ]
    save_json(leads_path, leads_json)

    queue = build_queue(leads=leads, recipient=recipient)
    save_json(queue_path, queue)

    dry_run = bool(config.get("draftOnly", True) or args.no_send)
    smtp_cfg = read_smtp_from_openclaw()
    smtp_server = os.getenv("EMAIL_SMTP_SERVER") or smtp_cfg.get("server", "")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT") or smtp_cfg.get("port", "587") or "587")
    sender = os.getenv("EMAIL_SENDER") or smtp_cfg.get("sender", "")
    password = os.getenv("EMAIL_SMTP_PASSWORD") or smtp_cfg.get("password", "")
    password = password.replace(" ", "")

    if (not dry_run) and (any(x.startswith("YOUR_") for x in [sender, password]) or not sender or not password):
        raise RuntimeError("SMTP credentials are placeholders. Set send-email env in ~/.openclaw/openclaw.json first.")

    for item, lead in zip(queue, leads):
        job_text = lead.detail_text
        requirements = extract_requirements(job_text=job_text, fallback_snippet=lead.snippet)
        evidence = select_cv_evidence(profile=profile, requirements=requirements)
        subject, body = render_email(profile=profile, lead=lead, requirements=requirements, evidence=evidence)
        ensure_formal_email_body(body)
        write_text(preview_path, f"Subject: {subject}\n\n{body}")
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        if dry_run:
            append_log(
                log_path,
                f"{ts},DRAFT,{item['recipient']},{lead.company},{lead.title},draftOnly enabled",
            )
            continue
        send_email(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            sender=sender,
            password=password,
            recipient=item["recipient"],
            subject=subject,
            body=body,
            attachment=cv_path,
            retry_count=int(config.get("retryCount", 2)),
        )
        append_log(log_path, f"{ts},SENT,{item['recipient']},{lead.company},{lead.title},ok")
        time.sleep(max(1.0, 60.0 / max(1, int(config.get("sendRatePerMinute", 3)))))

    print(f"Processed {len(queue)} item(s). dry_run={dry_run}")


if __name__ == "__main__":
    main()
