#!/usr/bin/env python3
"""Evaluate JobsDB HK leads for candidate fit."""

import json
from pathlib import Path
import re
import sys

CANDIDATE = {
    "yearsOfExperience": 0,
    "skills": ["ai", "deep learning", "llm", "machine learning", "nlp", "python", "sql", "typescript"],
    "education": [
        {"degree": "Master of Science in Artificial Intelligence", "school": "The Chinese University of Hong Kong", "period": "2025-2027"},
        {"degree": "Bachelor of Science in Data and Systems Engineering", "school": "City University of Hong Kong", "period": "2021-2025"}
    ],
    "targetRoles": ["AI Engineer", "Machine Learning Engineer", "LLM Developer"]
}

def parse_years_experience(job):
    """Extract required years of experience from description."""
    desc = job.get("description", "")
    title = job.get("title", "").lower()
    
    patterns = [
        r"(\d+)\+?\s*years?\s+experience\s+required",
        r"(\d+)\+?\s*\+\s*years?\s+experience",
        r"experience\s+required[\.\s]+(\d+)\+?\s*years?",
        r"(\d+)\+?\s*years?\s+of\s+experience",
    ]
    
    for pat in patterns:
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            return int(m.group(1))
    
    return 0  # unknown

def is_too_senior(job):
    """Check if role is too senior for a fresh grad."""
    title = job.get("title", "").lower()
    req_years = parse_years_experience(job)
    
    # Hard seniority markers
    senior_titles = ["principal", "director", "head of", "vp ", "vice president", "chief", "lead", "staff"]
    for st in senior_titles:
        if st in title:
            return True
    
    # Experience > 3 years is too senior for fresh grad
    if req_years > 3:
        return True
    
    # Experience exactly "8+" or "7+" etc - too senior
    if req_years >= 7:
        return True
    
    return False

def is_irrelevant(job):
    """Check if job is clearly unrelated to ML/AI/LLM."""
    title = job.get("title", "").lower()
    desc = job.get("description", "").lower()
    
    # Must have at least some AI/ML/LLM relevance
    relevant_keywords = ["machine learning", "deep learning", "neural network", "ai", "artificial intelligence",
                         "llm", "language model", "nlp", "natural language",
                         "reinforcement learning", "computer vision", "rag", "fine-tun",
                         "pytorch", "tensorflow", "transformers", "agent"]
    
    desc_relevant = any(kw in desc for kw in relevant_keywords)
    title_relevant = any(kw in title for kw in ["ml", "machine learning", "deep learning", 
                                                 "ai", "llm", "language model", "nlp", "neural"])
    
    if not desc_relevant and not title_relevant:
        return True
    
    return False

def is_weak_skill_fit(job):
    """Check if candidate lacks the core skills."""
    desc = job.get("description", "").lower()
    
    candidate_skills_lower = [s.lower() for s in CANDIDATE["skills"]]
    
    # Extract skills mentioned in description
    desc_skills = []
    for s in CANDIDATE["skills"]:
        if s.lower() in desc:
            desc_skills.append(s)
    
    # If no candidate skills match and it's a technical role, it's weak
    if len(desc_skills) == 0:
        return True
    
    return False

def evaluate_job(job):
    """Return 'accept' or a reject reason string."""
    
    # Check seniority
    if is_too_senior(job):
        req = parse_years_experience(job)
        return f"too_senior_{req}yrs"
    
    # Check relevance  
    if is_irrelevant(job):
        return "unrelated_role"
    
    # Check skill fit
    if is_weak_skill_fit(job):
        return "weak_skill_fit"
    
    return None  # accepted

def main():
    with open("str(Path(__file__).resolve().parent)/all_batch_jobs.json", "r") as f:
        jobs = json.load(f)
    
    send_queue = []
    rejected_log = []
    rejected_leads = []
    
    for job in jobs:
        result = evaluate_job(job)
        
        entry = {
            "title": job.get("title"),
            "company": job.get("company"),
            "url": job.get("url"),
            "location": job.get("location", ""),
            "job_type": job.get("job_type", ""),
            "salary": job.get("salary", ""),
            "search_keyword": job.get("search_keyword", ""),
            "page": job.get("page", 0)
        }
        
        if result is None:
            # Accepted
            send_entry = {
                "company": job.get("company"),
                "role": job.get("title"),
                "location": job.get("location", ""),
                "url": job.get("url"),
                "job_type": job.get("job_type", ""),
                "salary": job.get("salary", ""),
                "relevance": "high" if any(kw in job.get("title","").lower() for kw in ["llm","ai engineer","machine learning engineer","ml engineer","nlp"]) else "medium",
                "match_reason": "Good fit for AI/ML profile, entry/junior level"
            }
            send_queue.append(send_entry)
        else:
            # Rejected
            reject_reason = result
            entry["reject_reason"] = reject_reason
            
            # Determine rejection category
            if "too_senior" in reject_reason:
                category = "too_senior"
            elif "unrelated" in reject_reason:
                category = "unrelated"
            else:
                category = "weak_fit"
            
            entry["rejection_category"] = category
            rejected_leads.append(entry)
            rejected_log.append(entry)
    
    # Also add additional_jobs if exists
    try:
        with open("str(Path(__file__).resolve().parent)/additional_jobs.json", "r") as f:
            extra = json.load(f)
        for job in extra:
            result = evaluate_job(job)
            entry = {
                "title": job.get("title"),
                "company": job.get("company"),
                "url": job.get("url"),
                "location": job.get("location", ""),
                "job_type": job.get("job_type", ""),
                "salary": job.get("salary", ""),
                "search_keyword": job.get("search_keyword", ""),
                "page": job.get("page", 0)
            }
            if result is None:
                send_entry = {
                    "company": job.get("company"),
                    "role": job.get("title"),
                    "location": job.get("location", ""),
                    "url": job.get("url"),
                    "job_type": job.get("job_type", ""),
                    "salary": job.get("salary", ""),
                    "relevance": "medium",
                    "match_reason": "Good fit for AI/ML profile"
                }
                send_queue.append(send_entry)
            else:
                entry["reject_reason"] = result
                entry["rejection_category"] = "too_senior" if "too_senior" in result else ("unrelated" if "unrelated" in result else "weak_fit")
                rejected_leads.append(entry)
                rejected_log.append(entry)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass

    # Write outputs
    with open("str(Path(__file__).resolve().parent)/send-queue.json", "w") as f:
        json.dump(send_queue, f, indent=2)
    
    # Write rejected-leads.json as array
    with open("str(Path(__file__).resolve().parent)/rejected-leads.json", "w") as f:
        json.dump(rejected_leads, f, indent=2)
    
    # Write rejected-leads.log.jsonl
    with open("str(Path(__file__).resolve().parent)/rejected-leads.log.jsonl", "w") as f:
        for entry in rejected_log:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # Summary
    print(f"evaluated_count: {len(jobs)}")
    print(f"accepted_count: {len(send_queue)}")
    print(f"rejected_count: {len(rejected_log)}")
    print(f"total (incl additional): {len(jobs)} base + additional")
    print(f"---")
    print(f"Accepted:")
    for s in send_queue:
        print(f"  ACCEPT: {s['company']} - {s['role']} ({s['location']})")
    print(f"---")
    for r in rejected_leads[:10]:
        print(f"  REJECT: {r['company']} - {r['title']} [{r['rejection_category']}: {r['reject_reason']}]")
    
    return len(jobs), len(send_queue), len(rejected_log)

if __name__ == "__main__":
    main()
