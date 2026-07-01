#!/usr/bin/env python3
"""Tracking helpers for JobsDB application workflow."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

_JOB_DIR = Path(__file__).resolve().parent
SENT_JSON = str(_JOB_DIR / 'sent-applications.json')
SENT_LOG = str(_JOB_DIR / 'sent-applications.log.jsonl')
REJECTED_JSON = str(_JOB_DIR / 'rejected-leads.json')
REJECTED_LOG = str(_JOB_DIR / 'rejected-leads.log.jsonl')

def get_state():
    state = {
        'sent_count': 0,
        'sent_jobs': [],
        'rejected_count': 0,
        'processed_urls': set(),
        'sent_urls': set()
    }
    
    # Read sent JSON
    if os.path.exists(SENT_JSON):
        try:
            with open(SENT_JSON) as f:
                sj = json.load(f)
            if isinstance(sj, dict):
                state['sent_count'] = sj.get('sent_count', 0)
        except: pass
    
    # Read sent log for URLs
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        state['sent_jobs'].append(d)
                        state['sent_urls'].add(d.get('url', ''))
                        state['processed_urls'].add(d.get('url', ''))
                    except: pass
    
    # Read rejected JSON for URLs
    if os.path.exists(REJECTED_JSON):
        try:
            with open(REJECTED_JSON) as f:
                rj = json.load(f)
            state['rejected_count'] = len(rj) if isinstance(rj, list) else 0
            if isinstance(rj, list):
                for r in rj:
                    state['processed_urls'].add(r.get('url', ''))
        except: pass
    
    # Read rejected log for additional URLs
    if os.path.exists(REJECTED_LOG):
        with open(REJECTED_LOG) as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        state['processed_urls'].add(d.get('url', ''))
                    except: pass
    
    return state

def log_sent(company, role, url, timestamp=None):
    entry = {
        'timestamp': timestamp or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'company': company,
        'role': role,
        'url': url,
        'action': 'sent'
    }
    
    # Append to log
    with open(SENT_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    # Read existing sent entries
    entries = []
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except: pass
    
    # Update sent JSON
    state = get_state()
    sent_count = len(entries)
    
    output = {
        'sent_count': sent_count,
        'sent_jobs': entries
    }
    with open(SENT_JSON, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    return sent_count

def log_rejected(title, company, url, reason, category='weak_fit'):
    entry = {
        'title': title,
        'company': company,
        'url': url,
        'reject_reason': reason,
        'rejection_category': category
    }
    
    # Append to log
    with open(REJECTED_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    # Read existing rejected
    entries = []
    if os.path.exists(REJECTED_JSON):
        try:
            with open(REJECTED_JSON) as f:
                entries = json.load(f)
        except:
            entries = []
    
    entries.append(entry)
    with open(REJECTED_JSON, 'w') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    s = get_state()
    print(f'Sent count: {s["sent_count"]}')
    print(f'Sent jobs count: {len(s["sent_jobs"])}')
    print(f'Total processed URLs: {len(s["processed_urls"])}')
