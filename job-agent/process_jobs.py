#!/usr/bin/env python3
"""
Process job evaluations and manage output files.
This script handles the logic for evaluating jobs and managing the queues.
"""

import json
from pathlib import Path
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple

OUTPUT_DIR = 'str(Path(__file__).resolve().parent)'
SEND_QUEUE_PATH = os.path.join(OUTPUT_DIR, 'send-queue.json')
REJECTED_JSON_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.json')
REJECTED_LOG_PATH = os.path.join(OUTPUT_DIR, 'rejected-leads.log.jsonl')
STATUS_PATH = os.path.join(OUTPUT_DIR, 'scraper_status.json')

# Filtering criteria
INTEREST_KEYWORDS = [
    'llm', 'vla', 'ai', 'machine learning', 'deep learning', 
    'neural network', 'transformer', 'nlp', 'computer vision',
    'robotics', 'embodied ai', 'reinforcement learning', 'multimodal',
    'world model', 'agent', 'language model', 'generative ai'
]

REJECT_TITLES = ['director', 'vp', 'chief', 'head of', 'cto', 'ceo', 'president', 'executive']
MAX_YEARS_EXPERIENCE = 3

def load_status() -> dict:
    """Load scraper status."""
    if os.path.exists(STATUS_PATH):
        with open(STATUS_PATH, 'r') as f:
            return json.load(f)
    return {
        'evaluated': 0, 'accepted': 0, 'rejected': 0,
        'jobs_processed': []
    }

def save_status(status: dict):
    """Save scraper status."""
    with open(STATUS_PATH, 'w') as f:
        json.dump(status, f, indent=2)

def is_too_senior(title: str) -> bool:
    """Check if job title indicates too senior a role."""
    title_lower = title.lower()
    for reject in REJECT_TITLES:
        if reject in title_lower:
            return True
    return False

def extract_experience_years(description: str) -> int:
    """Extract maximum years of experience required."""
    if not description:
        return 0
    
    patterns = [
        r'(\d+)\s*[-–]\s*(\d+)\s*years?',  # "3-5 years"
        r'(\d+)\+?\s*years?\s*experience',  # "5+ years experience"
        r'minimum\s+(\d+)\s*years',  # "minimum 3 years"
        r'at\s+least\s+(\d+)\s*years',  # "at least 3 years"
        r'(\d+)\s*years?\s*experience',  # "3 years experience"
    ]
    
    max_years = 0
    for pattern in patterns:
        matches = re.findall(pattern, description.lower())
        for match in matches:
            try:
                if isinstance(match, tuple):
                    # Range - take higher bound
                    years = max(int(m) for m in match if m)
                else:
                    years = int(match)
                max_years = max(max_years, years)
            except (ValueError, TypeError):
                continue
    
    return max_years

def is_interesting_job(title: str, description: str) -> bool:
    """Check if job matches interests in LLM, VLA, AI, ML."""
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    combined = title_lower + " " + desc_lower
    
    for keyword in INTEREST_KEYWORDS:
        if keyword.lower() in combined:
            return True
    return False

def has_skill_fit(description: str) -> bool:
    """Check if job has basic skill fit."""
    if not description:
        return False
    desc_lower = description.lower()
    skill_keywords = ['python', 'ai', 'ml', 'machine learning', 'model', 
                      'deep learning', 'neural', 'tensorflow', 'pytorch',
                      'llm', 'transformer', 'nlp', 'computer vision']
    return any(skill in desc_lower for skill in skill_keywords)

def evaluate_job(job_data: dict) -> Tuple[bool, str]:
    """
    Evaluate a job and return (accepted, reason).
    """
    title = job_data.get('title', '')
    description = job_data.get('description', '')
    company = job_data.get('company', '')
    
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

def save_rejected(job_data: dict, reason: str):
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

def save_accepted(job_data: dict):
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
            return False  # Already in queue
    
    queue.append(job_data)
    with open(SEND_QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    return True

def process_job(job_data: dict) -> str:
    """
    Process a single job: evaluate and save to appropriate file.
    Returns 'accepted', 'rejected', or 'duplicate'.
    """
    # Check for duplicates first
    queue = []
    if os.path.exists(SEND_QUEUE_PATH):
        try:
            with open(SEND_QUEUE_PATH, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        except:
            pass
    
    job_url = job_data.get('url', '')
    for existing in queue:
        if existing.get('url') == job_url:
            return 'duplicate'
    
    # Evaluate
    accepted, reason = evaluate_job(job_data)
    
    if accepted:
        save_accepted(job_data)
        return 'accepted'
    else:
        save_rejected(job_data, reason)
        return 'rejected'

def get_stats() -> dict:
    """Get current statistics."""
    accepted = 0
    rejected = 0
    
    if os.path.exists(SEND_QUEUE_PATH):
        try:
            with open(SEND_QUEUE_PATH, 'r') as f:
                accepted = len(json.load(f))
        except:
            pass
    
    if os.path.exists(REJECTED_JSON_PATH):
        try:
            with open(REJECTED_JSON_PATH, 'r') as f:
                rejected = len(json.load(f))
        except:
            pass
    
    return {
        'accepted': accepted,
        'rejected': rejected,
        'evaluated': accepted + rejected
    }

def main():
    """Main function - can be used for batch processing."""
    stats = get_stats()
    print(f"Current stats: {stats}")
    
    # Example usage:
    # job_data = {
    #     'title': 'AI Engineer',
    #     'company': 'Example Corp',
    #     'url': 'https://...',
    #     'description': '...',
    #     'search_keyword': 'machine learning',
    #     'page': 1
    # }
    # result = process_job(job_data)
    # print(f"Job processed: {result}")

if __name__ == '__main__':
    main()
