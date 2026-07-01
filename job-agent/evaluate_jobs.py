#!/usr/bin/env python3
"""
Evaluate jobs from initial_jobs.json and populate send-queue and rejected files.
"""

import json
from pathlib import Path
import os
import re
from datetime import datetime

OUTPUT_DIR = 'str(Path(__file__).resolve().parent)'
INITIAL_JOBS_PATH = os.path.join(OUTPUT_DIR, 'initial_jobs.json')
SEND_QUEUE_PATH = os.path.join(OUTPUT_DIR, 'send-queue.json')
REJECTED_JSON_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.json')
REJECTED_LOG_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.log.jsonl')
STATUS_PATH = os.path.join(OUTPUT_DIR, 'scraper_status.json')

# Filtering criteria
INTEREST_KEYWORDS = [
    'llm', 'vla', 'ai', 'machine learning', 'deep learning', 
    'neural network', 'transformer', 'nlp', 'computer vision',
    'robotics', 'embodied ai', 'reinforcement learning', 'multimodal',
    'world model', 'agent', 'language model', 'generative ai',
    'rag', 'multimodal', 'large model', 'fine-tuning', 'sft'
]

REJECT_TITLES = ['director', 'vp', 'chief', 'head of', 'cto', 'ceo', 'president', 'executive']
MAX_YEARS_EXPERIENCE = 3

def is_too_senior(title):
    """Check if job title indicates too senior a role."""
    title_lower = title.lower()
    for reject in REJECT_TITLES:
        if reject in title_lower:
            return True
    return False

def extract_experience_years(description):
    """Extract maximum years of experience required."""
    if not description:
        return 0
    
    patterns = [
        r'(\d+)\s*[-–]\s*(\d+)\s*years?',
        r'(\d+)\+?\s*years?\s*experience',
        r'minimum\s+(\d+)\s*years',
        r'at\s+least\s+(\d+)\s*years',
        r'(\d+)\s*years?\s*experience',
    ]
    
    max_years = 0
    for pattern in patterns:
        matches = re.findall(pattern, description.lower())
        for match in matches:
            try:
                if isinstance(match, tuple):
                    years = max(int(m) for m in match if m)
                else:
                    years = int(match)
                max_years = max(max_years, years)
            except (ValueError, TypeError):
                continue
    
    return max_years

def is_interesting_job(title, description):
    """Check if job matches interests in LLM, VLA, AI, ML."""
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    combined = title_lower + " " + desc_lower
    
    for keyword in INTEREST_KEYWORDS:
        if keyword.lower() in combined:
            return True
    return False

def has_skill_fit(description):
    """Check if job has basic skill fit."""
    if not description:
        return False
    desc_lower = description.lower()
    skill_keywords = ['python', 'ai', 'ml', 'machine learning', 'model', 
                      'deep learning', 'neural', 'tensorflow', 'pytorch',
                      'llm', 'transformer', 'nlp', 'computer vision',
                      'robotics', 'agent', 'rag', 'fine-tuning']
    return any(skill in desc_lower for skill in skill_keywords)

def evaluate_job(job_data):
    """Evaluate a job and return (accepted, reason)."""
    title = job_data.get('title', '')
    description = job_data.get('description', '')
    
    # Check if already applied
    if job_data.get('status') == 'already_applied':
        return False, "Already applied"
    
    # Check if too senior
    if is_too_senior(title):
        return False, f"Too senior: {title}"
    
    # Check experience requirements (if specified)
    years = extract_experience_years(description)
    if years > MAX_YEARS_EXPERIENCE:
        return False, f"Experience requirement too high ({years} years > {MAX_YEARS_EXPERIENCE} max)"
    
    # Check if matches interests
    if not is_interesting_job(title, description):
        return False, "Does not match interests (LLM/VLA/AI/ML)"
    
    # Check for basic skill fit
    if not has_skill_fit(description):
        return False, "Lacks skill fit (no Python/AI/ML/model keywords)"
    
    return True, "accepted"

def save_rejected(job_data, reason):
    """Save rejected job to both JSON and JSONL files."""
    rejected_entry = {
        'timestamp': datetime.now().isoformat(),
        'title': job_data.get('title', ''),
        'company': job_data.get('company', ''),
        'url': job_data.get('url', ''),
        'reason': reason,
        'search_keyword': job_data.get('search_keyword', ''),
        'page': job_data.get('page', 1),
        'location': job_data.get('location', ''),
        'salary': job_data.get('salary', ''),
        'job_type': job_data.get('job_type', '')
    }
    
    # Append to JSONL
    with open(REJECTED_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rejected_entry, ensure_ascii=False) + '\n')
    
    # Update JSON array
    rejected_list = []
    if os.path.exists(REJECTED_JSON_PATH):
        try:
            with open(REJECTED_JSON_PATH, 'r', encoding='utf-8') as f:
                rejected_list = json.load(f)
        except:
            pass
    
    rejected_list.append(rejected_entry)
    with open(REJECTED_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(rejected_list, f, indent=2, ensure_ascii=False)

def save_accepted(job_data):
    """Save accepted job to send queue."""
    queue = []
    if os.path.exists(SEND_QUEUE_PATH):
        try:
            with open(SEND_QUEUE_PATH, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        except:
            pass
    
    # Check for duplicates by URL
    job_url = job_data.get('url', '')
    for existing in queue:
        if existing.get('url') == job_url:
            return False
    
    queue.append(job_data)
    with open(SEND_QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    return True

def main():
    """Main evaluation function."""
    print(f"Starting job evaluation at {datetime.now()}")
    
    # Load initial jobs
    if not os.path.exists(INITIAL_JOBS_PATH):
        print(f"Error: {INITIAL_JOBS_PATH} not found")
        return
    
    with open(INITIAL_JOBS_PATH, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    print(f"Loaded {len(jobs)} jobs to evaluate")
    
    accepted = 0
    rejected = 0
    duplicates = 0
    already_applied = 0
    
    for job in jobs:
        # Check if already applied
        if job.get('status') == 'already_applied':
            already_applied += 1
            print(f"  SKIP (already applied): {job['title']} at {job['company']}")
            continue
        
        # Evaluate
        eval_result = evaluate_job(job)
        
        if eval_result[0]:  # Accepted
            if save_accepted(job):
                accepted += 1
                print(f"  ACCEPT: {job['title']} at {job['company']}")
            else:
                duplicates += 1
                print(f"  DUPLICATE: {job['title']} at {job['company']}")
        else:
            rejected += 1
            save_rejected(job, eval_result[1])
            print(f"  REJECT ({eval_result[1]}): {job['title']} at {job['company']}")
    
    # Update status
    status = {
        'evaluated': accepted + rejected + already_applied,
        'accepted': accepted,
        'rejected': rejected,
        'already_applied': already_applied,
        'duplicates': duplicates,
        'last_updated': datetime.now().isoformat()
    }
    
    with open(STATUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Summary ===")
    print(f"Total processed: {accepted + rejected + already_applied}")
    print(f"Accepted: {accepted}")
    print(f"Rejected: {rejected}")
    print(f"Already applied: {already_applied}")
    print(f"Duplicates: {duplicates}")
    
    # Show queue preview
    if os.path.exists(SEND_QUEUE_PATH):
        with open(SEND_QUEUE_PATH, 'r', encoding='utf-8') as f:
            queue = json.load(f)
        print(f"\n=== Send Queue Preview (up to 10) ===")
        for i, job in enumerate(queue[:10], 1):
            print(f"{i}. {job['title']} at {job['company']}")
            print(f"   URL: {job['url']}")
            print()

if __name__ == '__main__':
    main()
