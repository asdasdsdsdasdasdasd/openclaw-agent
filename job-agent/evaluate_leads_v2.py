#!/usr/bin/env python3
"""
Careful evaluation of JobsDB HK leads for candidate profile.
Candidate: fresh MSc AI (2025-27), BSc Data & Systems Eng (2021-25), 0 yrs exp.
Skills: AI, deep learning, LLM, ML, NLP, Python, SQL, TypeScript.
Only JobsDB HK URLs considered.
"""
import json
from pathlib import Path
import re
import sys

LEADS_FILE = str(Path(__file__).resolve().parent) + '/all_batch_jobs.json'
ADDITIONAL_FILE = str(Path(__file__).resolve().parent) + '/additional_jobs.json'
INITIAL_FILE = str(Path(__file__).resolve().parent) + '/initial_jobs.json'
SEND_QUEUE = str(Path(__file__).resolve().parent) + '/send-queue.json'
REJECTED_JSON = str(Path(__file__).resolve().parent) + '/rejected-leads.json'
REJECTED_JSONL = str(Path(__file__).resolve().parent) + '/rejected-leads.log.jsonl'

CANDIDATE = {
    "years_of_exp": 0,
    "skills": {"ai", "deep learning", "llm", "machine learning", "nlp", "python", "sql", "typescript"},
    "target_roles": ["AI Engineer", "Machine Learning Engineer", "LLM Developer"],
    "relevance_priority": ["llm", "vla", "ai", "machine learning"]
}

# --- Experience parsing ---
def extract_req_years(desc, title):
    """Extract required years of experience from description."""
    t = title.lower()
    d = desc.lower()
    
    pats = [
        (r"(\d+)\+?\s*years?\s+experience\s+required", 1),
        (r"(\d+)\+?\s*\+\s*years?\s+experience", 1),
        (r"experience\s+required[\.\s]+(\d+)\+?\s*years?", 1),
        (r"(\d+)\+?\s*years?\s+of\s+experience", 1),
        (r"(\d+)\s*-\s*(\d+)\s*years?\s+experience", 2),
    ]
    for pat, grp in pats:
        m = re.search(pat, d)
        if m:
            if grp == 1:
                return int(m.group(1))
            elif grp == 2:
                return int(m.group(2))  # take the upper bound
    return 0

# --- Seniority check ---
SENIOR_TITLE_WORDS = {"principal", "director", "head", "vp", "vice president", "chief", "staff", "lead", "manager"}
MANAGER_ROLES = {"project manager", "program manager", "product manager"}

def is_senior_title(title):
    t = title.lower()
    words = set(t.split())
    # Check for senior-indicating patterns
    for sw in SENIOR_TITLE_WORDS:
        if sw in words or sw in t:
            return True
    if t.startswith("senior "):
        return True
    for mr in MANAGER_ROLES:
        if mr in t:
            return True
    return False

# --- Relevance scoring ---
def compute_relevance(job):
    """Score 0-100 how relevant this job is for the candidate."""
    title = job.get("title", "").lower()
    desc = job.get("description", "").lower()
    combined = title + " " + desc
    
    score = 0
    
    # Title match (high weight)
    title_exact = {
        "machine learning engineer": 100,
        "ml engineer": 95,
        "ai engineer": 90,
        "llm developer": 90,
        "llm engineer": 90,
        "nlp engineer": 85,
        "deep learning engineer": 85,
        "junior ml engineer": 95,
        "junior ai engineer": 90,
        "applied ml engineer": 80,
        "llm agent engineer": 90,
        "llm research engineer": 80,
        "ai/ml developer": 75,
        "ai software engineer": 70,
        "multimodal llm engineer": 85,
        "prompt engineer": 70,
        "llm application engineer": 75,
        "data scientist": 50,
        "ml data engineer": 60,
    }
    
    for key, val in title_exact.items():
        if key in title:
            score = max(score, val)
    
    # If no exact title match, check keywords
    if score == 0:
        if any(kw in title for kw in ["llm", "language model"]):
            score = 70
        elif any(kw in title for kw in ["machine learning", "ml"]):
            score = 60
        elif "ai" in title and any(kw in title for kw in ["engineer", "developer", "research"]):
            score = 55
        elif any(kw in title for kw in ["deep learning", "neural", "nlp", "reinforcement"]):
            score = 50
    
    # Boost if description mentions skills the candidate has
    candidate_skills_lower = {s.lower() for s in CANDIDATE["skills"]}
    desc_skills = set()
    for s in candidate_skills_lower:
        if s in desc:
            desc_skills.add(s)
    
    skill_overlap = len(desc_skills & candidate_skills_lower)
    score += skill_overlap * 5
    
    # Strong negative: infrastructure/platform/ops focus with no ML substance
    infra_only = ("infrastructure" in title or "platform" in title or "ops" in title or "cloud" in title)
    has_ml_content = any(kw in desc for kw in ["machine learning", "deep learning", "neural network", "nlp", "llm", "pytorch", "tensorflow"])
    if infra_only and not has_ml_content:
        score -= 30
    
    # Strong negative: too senior title
    if is_senior_title(title):
        score -= 40
    
    # Negative: experience requirement > 3 years
    yrs = extract_req_years(desc, title)
    if yrs > 3:
        score -= 20 * (yrs - 3)
    
    # Negative: contract/temp/internship for roles
    jt = job.get("job_type", "").lower()
    if "internship" in jt:
        score -= 10
    elif "part time" in jt:
        score -= 5
    
    return score

def main():
    all_jobs = []
    
    # Load from all files
    for fp in [LEADS_FILE, ADDITIONAL_FILE, INITIAL_FILE]:
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_jobs.extend(data)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    # Deduplicate by URL
    seen = set()
    unique_jobs = []
    for j in all_jobs:
        url = j.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique_jobs.append(j)
    
    print(f"Total unique job leads loaded: {len(unique_jobs)}")
    
    accepted = []
    rejected = []
    
    for job in unique_jobs:
        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")
        desc = job.get("description", "")
        salary = job.get("salary", "")
        location = job.get("location", "")
        job_type = job.get("job_type", "")
        search_kw = job.get("search_keyword", "")
        page = job.get("page", 0)
        
        # JobsDB-only enforcement
        if "jobsdb" not in url.lower():
            continue
        
        score = compute_relevance(job)
        yrs = extract_req_years(desc, title)
        
        entry = {
            "title": title,
            "company": company,
            "url": url,
            "location": location,
            "job_type": job_type,
            "salary": salary,
            "search_keyword": search_kw,
            "page": page
        }
        
        # Decision logic
        reject_reason = None
        
        # 1. Too senior (permanent reject)
        if is_senior_title(title):
            reject_reason = "senior_title"
        elif yrs > 3:
            reject_reason = f"too_many_years_{yrs}"
        
        # 2. Irrelevant to AI/ML/LLM
        if not reject_reason:
            title_lower = title.lower()
            desc_lower = desc.lower()
            relevant_kw_in_title = any(kw in title_lower for kw in [
                "machine learning", "ml ", "ai ", "llm", "language model", 
                "deep learning", "neural", "nlp", "reinforcement", "rag"
            ])
            relevant_kw_in_desc = any(kw in desc_lower for kw in [
                "machine learning", "deep learning", "neural network", "ai", "artificial intelligence",
                "llm", "language model", "nlp", "natural language",
                "reinforcement learning", "computer vision", "rag", "fine-tun",
                "pytorch", "tensorflow", "transformers", "agent", "multimodal"
            ])
            
            if not relevant_kw_in_title and not relevant_kw_in_desc:
                reject_reason = "irrelevant"
        
        # 3. Weak skill match
        if not reject_reason:
            candidate_skills_lower = {s.lower() for s in CANDIDATE["skills"]}
            desc_lower = desc.lower()
            matching = [s for s in candidate_skills_lower if s in desc_lower]
            if len(matching) == 0:
                reject_reason = "no_skill_overlap"
        
        # 4. Score too low
        if not reject_reason and score < 40:
            reject_reason = f"low_score_{score}"
        
        if reject_reason:
            # Categorize
            if "senior" in reject_reason or "years" in reject_reason:
                cat = "too_senior"
            elif "irrelevant" in reject_reason:
                cat = "unrelated"
            else:
                cat = "weak_fit"
            
            entry["reject_reason"] = reject_reason
            entry["rejection_category"] = cat
            rejected.append(entry)
        else:
            # Determine relevance tier
            rel = "medium"
            if "llm" in title.lower() or "language model" in title.lower():
                rel = "high_llm"
            elif any(kw in title.lower() for kw in ["machine learning engineer", "ml engineer", "ai engineer"]):
                rel = "high_ml"
            elif "nlp" in title.lower() or "deep learning" in title.lower():
                rel = "high_nlp_dl"
            
            send_entry = {
                "company": company,
                "role": title,
                "location": location,
                "url": url,
                "job_type": job_type,
                "salary": salary,
                "relevance": rel,
                "match_reason": f"score={score}, skills_match={len([s for s in candidate_skills_lower if s in desc.lower()])}, yr_req={yrs}"
            }
            accepted.append(send_entry)
    
    # Write outputs
    with open(SEND_QUEUE, "w") as f:
        json.dump(accepted, f, indent=2)
    
    with open(REJECTED_JSON, "w") as f:
        json.dump(rejected, f, indent=2)
    
    with open(REJECTED_JSONL, "w") as f:
        for entry in rejected:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"\n{'='*60}")
    print(f"evaluated_count: {len(unique_jobs)}")
    print(f"accepted_count: {len(accepted)}")
    print(f"rejected_count: {len(rejected)}")
    print(f"{'='*60}")
    
    print(f"\n--- ACCEPTED ({len(accepted)}) ---")
    for a in accepted[:10]:
        print(f"  {a['company']:40s} | {a['role']:35s} | rel={a['relevance']} | {a['location']}")
    if len(accepted) > 10:
        print(f"  ... and {len(accepted)-10} more")
    
    print(f"\n--- REJECTED first 15 ---")
    for r in rejected[:15]:
        print(f"  {r['company']:40s} | {r['title']:35s} | {r['rejection_category']:12s} | {r['reject_reason']}")
    
    print(f"\n--- Summary sizes ---")
    print(f"send-queue.json: {len(accepted)} entries")
    print(f"rejected-leads.json: {len(rejected)} entries")
    print(f"rejected-leads.log.jsonl: {len(rejected)} lines")

if __name__ == "__main__":
    main()
