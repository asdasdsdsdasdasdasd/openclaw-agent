#!/usr/bin/env python3
"""
Final evaluation of JobsDB HK leads for candidate profile.
Fresh graduate (0 yrs exp), skills: AI, deep learning, LLM, ML, NLP, Python, SQL, TypeScript.
Only JobsDB. No applications. Just evaluate.
"""
import json
from pathlib import Path
import re

LEADS = str(Path(__file__).resolve().parent) + '/all_batch_jobs.json'
ADD = str(Path(__file__).resolve().parent) + '/additional_jobs.json'
INIT = str(Path(__file__).resolve().parent) + '/initial_jobs.json'
SQL = str(Path(__file__).resolve().parent) + '/send-queue.json'
RJ = str(Path(__file__).resolve().parent) + '/rejected-leads.json'
RJ_LOG = str(Path(__file__).resolve().parent) + '/rejected-leads.log.jsonl'

CANDIDATE = {
    "skills": {"ai", "deep learning", "llm", "machine learning", "nlp", "python", "sql", "typescript"},
    "target_roles": ["AI Engineer", "Machine Learning Engineer", "LLM Developer"],
    "priority": "LLM / VLA / AI / Machine Learning"
}

def extract_yrs(desc, title):
    d = (desc + " " + title).lower()
    pats = [
        r"(\d+)\+?\s*years?\s+experience\s+required",
        r"(\d+)\+?\s*\+\s*years?\s+experience",
        r"experience\s+required[\.\s]+(\d+)\+?\s*years?",
        r"(\d+)\+?\s*years?\s+of\s+experience",
        r"(\d+)\s*-\s*(\d+)\s*years?\s+experience",
    ]
    for p in pats:
        m = re.search(p, d)
        if m:
            return max(int(x) for x in m.groups() if x)
    return 0

def classify(job):
    """
    Returns ('accept', dict) or ('reject', reason_dict)
    """
    title = job.get("title", "")
    company = job.get("company", "")
    desc = job.get("description", "")
    url = job.get("url", "")
    location = job.get("location", "")
    jt = job.get("job_type", "")
    salary = job.get("salary", "")
    sk = job.get("search_keyword", "")
    pg = job.get("page", 0)
    
    tl = title.lower()
    dl = desc.lower()
    yrs = extract_yrs(desc, title)
    
    base = {
        "title": title, "company": company, "url": url,
        "location": location, "job_type": jt, "salary": salary,
        "search_keyword": sk, "page": pg
    }
    
    # === HARD REJECTIONS ===
    
    # Senior/lead/manager/director titles (even without explicit yr req)
    hard_senior = ["senior", "principal", "director", "head ", "vp ", "vice president", 
                   "chief", "staff", "lead", "manager", "architect"]
    for kw in hard_senior:
        if kw in tl.split() or kw in tl:
            return ("reject", {**base, "reject_reason": f"senior_title_{kw.strip()}", "rejection_category": "too_senior"})
    
    # Experience > 3 years
    if yrs > 3:
        return ("reject", {**base, "reject_reason": f"exp_req_{yrs}yrs", "rejection_category": "too_senior"})
    
    # === CONTENT RELEVANCE ===
    
    # Title-based priority detection (highest)
    priority_titles = [
        "llm developer", "llm engineer", "llm research engineer", "llm agent engineer",
        "llm application engineer", "llm integration engineer",
        "machine learning engineer", "ml engineer",
        "ai engineer", "ai/ml engineer", "ai/ml developer",
        "junior ml engineer", "junior ai engineer",
        "applied ml engineer", "applied ai engineer",
        "reinforcement learning engineer",
        "nlp engineer", "deep learning engineer",
        "generative ai engineer", "multimodal llm engineer",
        "prompt engineer", "rag engineer",
        "llm fine-tuning engineer", "llm ops engineer",
        "conversational ai engineer",
        "llm developer", "llm backend engineer",
        "llm security engineer", "llm platform engineer",
        "llm data engineer", "llm performance engineer",
        "multimodal llm engineer", "llm fine-tuning specialist",
        "llm application developer", "llm developer",
        "llm engineer"
    ]
    
    # Check if title matches any priority pattern
    is_priority = False
    for pt in priority_titles:
        if pt in tl:
            is_priority = True
            break
    
    # Also check for key AI/ML terms in title
    title_ml_terms = ["machine learning", "ml ", "ai ", "llm", "language model", 
                      "deep learning", "neural", "nlp", "reinforcement"]
    has_title_ml = any(t in tl.split() or t.strip() in tl for t in title_ml_terms)
    
    if not is_priority and not has_title_ml:
        # Check description for AI/ML substance
        desc_ai_ml = any(kw in dl for kw in [
            "machine learning", "deep learning", "neural network", "ai", "artificial intelligence",
            "llm", "language model", "nlp", "natural language",
            "reinforcement learning", "computer vision", "rag", "fine-tun",
            "pytorch", "tensorflow", "transformers", "agent", "multimodal",
            "recommendation system", "time series", "anomaly detection"
        ])
        if not desc_ai_ml:
            return ("reject", {**base, "reject_reason": "no_ml_content", "rejection_category": "unrelated"})
    
    # === SKILL FIT ===
    candidate_skills = {s.lower() for s in CANDIDATE["skills"]}
    matched_skills = [s for s in candidate_skills if s in dl]
    
    # For ML/AI Engineer roles, must have at least Python matching
    if "engineer" in tl and "python" not in dl:
        if "developer" in tl or "engineer" in tl:
            if len(matched_skills) == 0:
                return ("reject", {**base, "reject_reason": "no_skill_match", "rejection_category": "weak_fit"})
    
    # === REJECT SPECIFIC ROLE TYPES that are poor fit for this candidate ===
    
    # Infrastructure-only, platform-only, ops-only without ML depth
    infra_ops_kw = ["infrastructure", "platform", "operations", "ops", "cloud"]
    is_infra_role = any(kw in tl for kw in infra_ops_kw)
    has_decent_ml_desc = any(kw in dl for kw in ["pytorch", "tensorflow", "model", "training", "neural", "llm", "nlp", "deep learning", "transformers"])
    
    if is_infra_role and not has_decent_ml_desc:
        return ("reject", {**base, "reject_reason": "infra_ops_no_ml_depth", "rejection_category": "unrelated"})
    
    # Pure Data Scientist roles (different career track)
    if "data scientist" in tl and "ml" not in tl and "machine learning" not in tl and "ai" not in tl:
        return ("reject", {**base, "reject_reason": "data_scientist_role", "rejection_category": "weak_fit"})
    
    # Consultant roles (typically very senior)
    if "consultant" in tl:
        return ("reject", {**base, "reject_reason": "consultant_role_generally_senior", "rejection_category": "too_senior"})
    
    # Research Scientist without PhD requirement
    if "research scientist" in tl or "research engineer" in tl:
        # Only accept if it mentions LLM/AI/ML and no PhD required
        if "phd" in dl or "ph.d" in dl or "doctorate" in dl:
            return ("reject", {**base, "reject_reason": "phd_required", "rejection_category": "too_senior"})
    
    # Integration/System Engineer without clear ML focus
    if ("system engineer" in tl or "integration engineer" in tl or "edge engineer" in tl or 
        "automation" in tl or "full stack" in tl or "backend engineer" in tl):
        if not has_decent_ml_desc:
            return ("reject", {**base, "reject_reason": "generic_role_no_ml", "rejection_category": "weak_fit"})
    
    # === DETERMINE RELEVANCE TIER ===
    if "llm" in tl or "language model" in tl:
        relevance = "high_llm"
    elif "machine learning" in tl and ("engineer" in tl or "developer" in tl):
        relevance = "high_ml"
    elif "ai" in tl and ("engineer" in tl or "developer" in tl):
        relevance = "high_ai"
    elif "nlp" in tl or "deep learning" in tl:
        relevance = "high_nlp_dl"
    else:
        relevance = "medium"
    
    # Calculate match reason
    stext = ", ".join(matched_skills) if matched_skills else "none"
    send_entry = {
        "company": company,
        "role": title,
        "location": location,
        "url": url,
        "job_type": jt,
        "salary": salary,
        "relevance": relevance,
        "match_reason": f"skills:[{stext}] exp_req:{yrs}yrs"
    }
    
    return ("accept", send_entry)


def main():
    all_jobs = []
    for fp in [LEADS, ADD, INIT]:
        try:
            with open(fp) as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_jobs.extend(data)
        except Exception:
            pass
    
    # Dedup
    seen = set()
    unique = []
    for j in all_jobs:
        u = j.get("url", "")
        if u and u not in seen:
            seen.add(u)
            unique.append(j)
    
    print(f"Total unique: {len(unique)}")
    
    accepted = []
    rejected = []
    count = 0
    
    for job in unique:
        url = job.get("url", "")
        if "jobsdb" not in url.lower():
            continue
        
        count += 1
        if count > 200:
            break
        
        result, data = classify(job)
        if result == "accept":
            accepted.append(data)
        else:
            rejected.append(data)
    
    # Write
    with open(SQL, "w") as f:
        json.dump(accepted, f, indent=2)
    with open(RJ, "w") as f:
        json.dump(rejected, f, indent=2)
    with open(RJ_LOG, "w") as f:
        for e in rejected:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    # Final summary
    print(f"evaluated_count: {count}")
    print(f"accepted_count: {len(accepted)}")
    print(f"rejected_count: {len(rejected)}")
    print(f"jobsdb_only: True")
    print()
    print("=== ACCEPTED ===")
    for a in accepted:
        print(f"  [{a['relevance']:12s}] {a['company']:35s} | {a['role']:40s} | {a['location']}")
    print()
    print("=== REJECTED (first 20) ===")
    for r in rejected[:20]:
        print(f"  [{r['rejection_category']:12s}] {r['company']:35s} | {r['title']:40s} | {r['reject_reason']}")
    
    # Queue preview
    print("\n=== QUEUE PREVIEW (first 10) ===")
    for a in accepted[:10]:
        print(json.dumps(a, ensure_ascii=False))

if __name__ == "__main__":
    main()
