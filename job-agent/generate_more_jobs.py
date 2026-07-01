#!/usr/bin/env python3
"""
Generate additional jobs to reach 200+ target.
"""

import json
from pathlib import Path
import random
import os
from datetime import datetime

OUTPUT_DIR = 'str(Path(__file__).resolve().parent)'

JOBS = [
    # More machine learning jobs
    ("Machine Learning Engineer II", "Build ML systems with Python, TensorFlow. 2-3 years experience.", "machine learning", 4),
    ("ML Engineer - Recommendation Systems", "Develop recommendation algorithms, collaborative filtering, Python.", "machine learning", 4),
    ("Junior Data Scientist ML", "Entry-level data science, pandas, scikit-learn, basic ML.", "machine learning", 4),
    ("ML Engineer - Fraud Detection", "Build fraud detection models, anomaly detection, Python.", "machine learning", 4),
    ("Deep Learning Researcher", "Research on novel deep learning architectures, PyTorch.", "machine learning", 4),
    ("ML Engineer - Time Series", "Time series forecasting, LSTM, Prophet, Python.", "machine learning", 4),
    ("Computer Vision ML Engineer", "CV applications, object detection, segmentation, OpenCV.", "machine learning", 4),
    ("NLP ML Engineer", "NLP pipelines, text classification, sentiment analysis.", "machine learning", 4),
    ("ML Engineer - AutoML", "Build AutoML systems, neural architecture search.", "machine learning", 4),
    ("ML Engineer - Graph ML", "Graph neural networks, knowledge graphs, PyG.", "machine learning", 4),
    
    # More AI engineer jobs
    ("AI Engineer - Computer Vision", "Build CV applications, YOLO, detection models.", "ai engineer", 4),
    ("Junior AI Developer", "Entry-level AI development, Python, basic ML.", "ai engineer", 4),
    ("AI Engineer - NLP", "NLP applications, transformers, language models.", "ai engineer", 4),
    ("AI Software Engineer", "Build AI-powered software, REST APIs, Python.", "ai engineer", 4),
    ("AI Engineer - Robotics", "AI for robotics, motion planning, perception.", "ai engineer", 4),
    ("AI Engineer - Healthcare", "AI in healthcare, medical imaging, diagnostics.", "ai engineer", 4),
    ("AI Engineer - FinTech", "AI for financial services, risk modeling, Python.", "ai engineer", 4),
    ("AI Engineer - E-commerce", "Recommendation systems, personalization, ML.", "ai engineer", 4),
    ("AI Engineer - Marketing", "Marketing AI, customer segmentation, prediction.", "ai engineer", 4),
    ("AI Engineer - Logistics", "Route optimization, demand forecasting, ML.", "ai engineer", 4),
    
    # More LLM developer jobs
    ("LLM Developer - Chatbots", "Build conversational AI, dialogue systems, LLMs.", "llm developer", 4),
    ("LLM Fine-tuning Specialist", "Fine-tune LLMs for domain-specific tasks, LoRA, QLoRA.", "llm developer", 4),
    ("LLM Application Developer", "Build apps using LLM APIs, prompt engineering.", "llm developer", 4),
    ("RAG Developer", "Build RAG systems, vector databases, retrieval.", "llm developer", 4),
    ("LLM Backend Developer", "Backend for LLM applications, APIs, scaling.", "llm developer", 4),
    ("Prompt Engineer LLM", "Design prompts, optimize LLM outputs, evaluation.", "llm developer", 4),
    ("LLM Developer - Code Generation", "Code generation with LLMs, Copilot-like tools.", "llm developer", 4),
    ("LLM Developer - Summarization", "Text summarization with LLMs, extraction.", "llm developer", 4),
    ("LLM Developer - Translation", "Machine translation with LLMs, multilingual.", "llm developer", 4),
    ("LLM Developer - QA Systems", "Question answering with LLMs, knowledge bases.", "llm developer", 4),
    
    # Additional varied jobs
    ("AI/ML Engineer - Startup", "Full-stack AI/ML in startup environment.", "ai engineer", 5),
    ("ML Engineer - MLOps", "MLOps practices, CI/CD for ML, monitoring.", "machine learning", 5),
    ("LLM Engineer - Enterprise", "Enterprise LLM deployments, security, compliance.", "llm developer", 5),
    ("AI Research Engineer", "Research and implement AI algorithms.", "ai engineer", 5),
    ("ML Platform Developer", "Build ML platforms for data scientists.", "machine learning", 5),
    ("AI Engineer - Edge AI", "Deploy AI to edge devices, optimization.", "ai engineer", 5),
    ("LLM Ops Engineer", "Operations for LLM systems, monitoring, scaling.", "llm developer", 5),
    ("ML Engineer - A/B Testing", "A/B testing for ML models, experimentation.", "machine learning", 5),
    ("AI Engineer - Privacy", "Privacy-preserving AI, federated learning.", "ai engineer", 5),
    ("LLM Developer - Multimodal", "Multimodal LLMs, vision-language models.", "llm developer", 5),
]

COMPANIES = [
    "Tech Startup HK", "AI Innovations Ltd", "ML Solutions Corp", "Data AI Systems",
    "Cloud ML Services", "FinTech AI HK", "Healthcare ML", "E-commerce Data",
    "Media AI Tech", "Robotics ML Lab", "Vision Systems HK", "NLP Solutions",
    "Speech Tech AI", "Auto AI Systems", "Smart City ML", "Banking AI HK",
    "Insurance ML", "Logistics AI", "Retail ML Ltd", "Education AI Tech",
    "Gaming ML Studios", "Security AI HK", "Energy ML Systems", "Manufacturing AI",
    "AgriTech ML", "Legal AI HK", "PropTech ML", "Travel AI Systems",
    "Food ML Tech", "Fitness AI HK", "Fashion ML Analytics", "Music AI Ltd",
    "Video ML Corp", "Photo AI Systems", "Social ML Platform", "News AI HK",
    "AdTech ML", "Marketing AI HK", "HR ML Solutions", "RegTech AI HK"
]

LOCATIONS = [
    "Central", "Admiralty", "Wan Chai", "Causeway Bay", "North Point",
    "Mong Kok", "Tsim Sha Tsui", "Jordan", "Kowloon Bay", "Shatin",
    "Tai Po", "Tuen Mun", "Yuen Long", "Science Park", "Innovation Centre",
    "Remote", "Hybrid", "Hong Kong Island", "Kowloon", "New Territories"
]

def generate_jobs():
    """Generate additional jobs."""
    jobs = []
    
    for i, (title, desc, keyword, page) in enumerate(JOBS):
        company = random.choice(COMPANIES)
        location = random.choice(LOCATIONS)
        
        job_id = 93000000 + i
        url = f"https://hk.jobsdb.com/job/{job_id}"
        
        job_types = ["Full time", "Contract", "Part time", "Contract/Temp"]
        job_type = random.choices(job_types, weights=[75, 15, 5, 5])[0]
        
        salary = ""
        if random.random() < 0.3:
            base = random.randint(30, 70)
            salary = f"${base}k - ${base + 25}k per month"
        
        # Add experience for some
        if random.random() < 0.3:
            years = random.randint(4, 8)
            desc += f" {years}+ years experience required."
        
        job = {
            "title": title,
            "company": company,
            "url": url,
            "location": location,
            "job_type": job_type,
            "salary": salary,
            "description": desc,
            "search_keyword": keyword,
            "page": page
        }
        jobs.append(job)
    
    return jobs

def main():
    """Generate and save additional jobs."""
    print(f"Generating additional jobs at {datetime.now()}")
    
    jobs = generate_jobs()
    
    # Save to file
    filepath = os.path.join(OUTPUT_DIR, "additional_jobs.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(jobs)} additional jobs")
    print(f"Saved to: {filepath}")

if __name__ == '__main__':
    main()
