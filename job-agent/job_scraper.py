#!/usr/bin/env python3
"""
JobsDB job scraper with deterministic keyword cycle.
Searches for: 'machine learning', 'ai engineer', 'llm developer'
Order: K1 page1..N, K2 page1..N, K3 page1..N, repeat
N starts at 3, increases after exhausting all three keywords.
"""

import json
from pathlib import Path
import os
import time
import re
from datetime import datetime
from urllib.parse import quote

# Configuration
KEYWORDS = ['machine learning', 'ai engineer', 'llm developer']
BASE_URL = 'https://hk.jobsdb.com'
OUTPUT_DIR = 'str(Path(__file__).resolve().parent)'
SEND_QUEUE_PATH = os.path.join(OUTPUT_DIR, 'send-queue.json')
REJECTED_JSON_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.json')
REJECTED_LOG_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.log.jsonl')

# Filtering criteria
INTEREST_KEYWORDS = ['llm', 'vla', 'ai', 'machine learning', 'deep learning', 
                     'neural network', 'transformer', 'nlp', 'computer vision',
                     'robotics', 'embodied ai', 'reinforcement learning', 'multimodal']
REJECT_TITLES = ['director', 'vp', 'chief', 'head of', 'cto', 'ceo', 'president']
MAX_YEARS_EXPERIENCE = 3

def sanitize_text(text):
    """Clean and normalize text."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def is_interesting_job(title, description):
    """Check if job matches interests in LLM, VLA, AI, ML."""
    title_lower = title.lower() if title else ""
    desc_lower = description.lower() if description else ""
    combined = title_lower + " " + desc_lower
    
    for keyword in INTEREST_KEYWORDS:
        if keyword.lower() in combined:
            return True
    return False

def is_too_senior(title):
    """Check if job is too senior."""
    title_lower = title.lower() if title else ""
    for reject in REJECT_TITLES:
        if reject in title_lower:
            return True
    return False

def extract_experience_years(description):
    """Extract years of experience requirement from description."""
    if not description:
        return 0
    
    # Look for patterns like "3-5 years", "5+ years", "minimum 3 years"
    patterns = [
        r'(\d+)\s*[-–]?\s*(\d+)?\s*years?',
        r'(\d+)\+?\s*years?',
        r'minimum\s+(\d+)\s*years?',
        r'at\s+least\s+(\d+)\s*years?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description.lower())
        if match:
            try:
                if len(match.groups()) >= 2 and match.group(2):
                    # Range like "3-5 years" - take the higher bound
                    return int(match.group(2))
                else:
                    return int(match.group(1))
            except (ValueError, IndexError):
                continue
    return 0

def evaluate_job(job_data):
    """
    Evaluate a job and return (accepted, reason).
    Returns (True, "accepted") or (False, "rejection_reason")
    """
    title = job_data.get('title', '')
    description = job_data.get('description', '')
    company = job_data.get('company', '')
    
    # Check if too senior
    if is_too_senior(title):
        return False, f"Too senior: {title}"
    
    # Check experience requirements
    years = extract_experience_years(description)
    if years > MAX_YEARS_EXPERIENCE:
        return False, f"Experience requirement too high ({years} years > {MAX_YEARS_EXPERIENCE} max)"
    
    # Check if matches interests
    if not is_interesting_job(title, description):
        return False, f"Does not match interests (LLM/VLA/AI/ML)"
    
    # Check for basic skill fit
    if not any(skill in description.lower() for skill in ['python', 'ai', 'ml', 'learning', 'model']):
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
        'page': job_data.get('page', 1)
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
    
    # Check for duplicates
    job_url = job_data.get('url', '')
    for existing in queue:
        if existing.get('url') == job_url:
            return  # Skip duplicates
    
    queue.append(job_data)
    with open(SEND_QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

def log_progress(keyword, page, evaluated, accepted, rejected):
    """Log progress to console."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Keyword: {keyword}, Page: {page} | "
          f"Evaluated: {evaluated} | Accepted: {accepted} | Rejected: {rejected}")

def main():
    """Main scraper function."""
    print(f"Starting job search at {datetime.now()}")
    print(f"Keywords: {KEYWORDS}")
    print(f"Output directory: {OUTPUT_DIR}")
    
    evaluated = 0
    accepted = 0
    rejected = 0
    
    page_count = 3  # Start with 3 pages per keyword
    keyword_index = 0
    
    # Initialize output files
    if not os.path.exists(REJECTED_LOG_PATH):
        open(REJECTED_LOG_PATH, 'w').close()
    if not os.path.exists(REJECTED_JSON_PATH):
        with open(REJECTED_JSON_PATH, 'w') as f:
            json.dump([], f)
    if not os.path.exists(SEND_QUEUE_PATH):
        with open(SEND_QUEUE_PATH, 'w') as f:
            json.dump([], f)
    
    # This is a placeholder - actual scraping requires browser automation
    # For now, we'll create a simulation that shows the structure
    
    print("\n" + "="*60)
    print("NOTE: This script requires browser automation to scrape JobsDB")
    print("The actual implementation needs to use the OpenClaw browser tool")
    print("to navigate pages and extract job details.")
    print("="*60 + "\n")
    
    # Create a status file for the browser-based scraper to use
    status_file = os.path.join(OUTPUT_DIR, 'scraper_status.json')
    status = {
        'started_at': datetime.now().isoformat(),
        'evaluated': evaluated,
        'accepted': accepted,
        'rejected': rejected,
        'current_keyword': KEYWORDS[0],
        'current_page': 1,
        'max_pages_per_keyword': page_count,
        'target_evaluations': 200,
        'status': 'initializing'
    }
    
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)
    
    print(f"Status file created: {status_file}")
    print("Ready for browser-based scraping...")
    
    return {
        'evaluated': evaluated,
        'accepted': accepted,
        'rejected': rejected
    }

if __name__ == '__main__':
    main()
