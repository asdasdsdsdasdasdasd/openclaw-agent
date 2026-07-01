#!/usr/bin/env python3
"""
Generate a comprehensive batch of jobs for evaluation.
Simulates search results from JobsDB for machine learning, ai engineer, and llm developer keywords.
"""

import json
from pathlib import Path
import random
from datetime import datetime, timedelta

OUTPUT_DIR = 'str(Path(__file__).resolve().parent)'

# Job templates for different categories
ML_JOB_TEMPLATES = [
    ("Machine Learning Engineer", "Build and deploy ML models using Python, TensorFlow, PyTorch"),
    ("Junior ML Engineer", "Entry-level ML position, Python and scikit-learn skills"),
    ("Senior Machine Learning Engineer", "Lead ML initiatives, 5+ years experience required"),
    ("ML Research Scientist", "Research on novel ML algorithms and architectures"),
    ("Applied ML Engineer", "Apply ML to real-world problems, production experience"),
    ("ML Infrastructure Engineer", "Build infrastructure for ML training and deployment"),
    ("Machine Learning Intern", "Internship for students interested in ML"),
    ("ML Platform Engineer", "Develop ML platforms and tools for data scientists"),
    ("Deep Learning Engineer", "Develop deep learning models, CNN, RNN, transformers"),
    ("Computer Vision Engineer", "Build computer vision systems, OpenCV, image processing"),
    ("NLP Engineer", "Natural language processing, text analysis, language models"),
    ("Data Scientist - ML", "Data science with focus on machine learning"),
    ("ML Operations Engineer", "MLOps, model deployment and monitoring"),
    ("Reinforcement Learning Engineer", "RL algorithms, PPO, DQN, simulation"),
    ("Generative AI Engineer", "Build generative AI applications, diffusion models, GANs"),
    ("AI/ML Engineer", "Cross-functional AI and ML development"),
    ("ML Algorithm Engineer", "Design and optimize ML algorithms"),
    ("Machine Learning Consultant", "Advise on ML strategy and implementation"),
    ("ML Software Engineer", "Software engineering for ML systems"),
    ("ML Data Engineer", "Data engineering for ML pipelines"),
]

AI_ENGINEER_TEMPLATES = [
    ("AI Engineer", "Develop AI solutions using modern frameworks"),
    ("Junior AI Engineer", "Entry-level AI development, Python required"),
    ("Senior AI Engineer", "Lead AI projects, 4+ years experience"),
    ("AI Software Engineer", "Build AI-powered software applications"),
    ("AI Application Developer", "Develop AI applications for end users"),
    ("AI Solutions Engineer", "Design and implement AI solutions"),
    ("AI Platform Engineer", "Build platforms for AI development"),
    ("AI Research Engineer", "Research and implement AI technologies"),
    ("AI Infrastructure Engineer", "Infrastructure for AI workloads"),
    ("AI Developer", "General AI development role"),
    ("AI/ML Developer", "AI and machine learning development"),
    ("AI Systems Engineer", "Build AI systems and integrations"),
    ("AI Technical Lead", "Lead AI engineering team"),
    ("AI Product Engineer", "AI product development"),
    ("AI Integration Engineer", "Integrate AI into existing systems"),
    ("AI Automation Engineer", "Build AI automation solutions"),
    ("AI Backend Engineer", "Backend development for AI applications"),
    ("AI Full Stack Engineer", "Full stack AI application development"),
    ("AI Cloud Engineer", "AI on cloud platforms, AWS/Azure/GCP"),
    ("AI Edge Engineer", "Deploy AI to edge devices"),
]

LLM_JOB_TEMPLATES = [
    ("LLM Engineer", "Work with large language models, fine-tuning, deployment"),
    ("LLM Developer", "Develop LLM applications and integrations"),
    ("LLM Research Engineer", "Research on LLM architectures and training"),
    ("LLM Application Engineer", "Build applications using LLMs"),
    ("LLM Fine-tuning Engineer", "Specialize in fine-tuning LLMs for specific tasks"),
    ("LLM Ops Engineer", "Operations for LLM deployment and monitoring"),
    ("LLM Integration Engineer", "Integrate LLMs into business applications"),
    ("Prompt Engineer", "Design and optimize prompts for LLMs"),
    ("LLM Backend Engineer", "Backend systems for LLM applications"),
    ("LLM Platform Engineer", "Build platforms for LLM development"),
    ("Conversational AI Engineer", "Build conversational AI using LLMs"),
    ("LLM Data Engineer", "Data engineering for LLM training"),
    ("LLM Evaluation Engineer", "Evaluate and benchmark LLMs"),
    ("LLM Security Engineer", "Security for LLM applications"),
    ("LLM Performance Engineer", "Optimize LLM inference performance"),
    ("RAG Engineer", "Build RAG systems with LLMs"),
    ("LLM Agent Engineer", "Build AI agents using LLMs"),
    ("Multimodal LLM Engineer", "Work with multimodal LLMs"),
    ("LLM Infrastructure Engineer", "Infrastructure for LLM training and serving"),
    ("LLM Solutions Architect", "Design LLM solutions for clients"),
]

COMPANIES = [
    "Tech Innovations HK", "AI Solutions Ltd", "Deep Learning Corp", "ML Systems HK",
    "Data Science Partners", "Cloud AI Services", "FinTech AI", "Healthcare AI HK",
    "E-commerce Analytics", "Media Tech HK", "Robotics AI Lab", "Vision Systems Ltd",
    "NLP Technologies", "Speech AI Corp", "Autonomous Systems HK", "Smart City AI",
    "Banking AI Solutions", "Insurance Tech HK", "Logistics AI", "Retail Analytics Ltd",
    "Education Tech AI", "Gaming AI Studios", "Security AI Systems", "Energy AI HK",
    "Manufacturing AI", "Agriculture Tech AI", "Legal AI Solutions", "Real Estate AI",
    "Travel Tech HK", "Food Delivery AI", "Fitness Tech AI", "Fashion AI Analytics",
    "Music AI Corp", "Video Analytics HK", "Photo AI Systems", "Social Media AI",
    "News AI Platform", "Advertising Tech HK", "Marketing AI Solutions", "HR Tech AI",
    "LegalTech AI", "PropTech AI", "InsurTech Solutions", "RegTech AI HK"
]

LOCATIONS = [
    "Central", "Admiralty", "Causeway Bay", "Wan Chai", "North Point", "Quarry Bay",
    "Tai Kok Tsui", "Mong Kok", "Tsim Sha Tsui", "Jordan", "Kowloon Bay", "Wong Tai Sin",
    "Kwun Tong", "Shatin", "Tai Po", "Tuen Mun", "Yuen Long", "Science Park",
    "Innovation Centre", "Remote", "Hybrid", "Hong Kong Island", "Kowloon", "New Territories"
]

def generate_jobs(keyword, page, count=20):
    """Generate jobs for a specific keyword and page."""
    jobs = []
    
    if keyword == "machine learning":
        templates = ML_JOB_TEMPLATES
    elif keyword == "ai engineer":
        templates = AI_ENGINEER_TEMPLATES
    else:  # llm developer
        templates = LLM_JOB_TEMPLATES
    
    for i in range(count):
        # Select template
        title, description = random.choice(templates)
        
        # Add some variation
        company = random.choice(COMPANIES)
        location = random.choice(LOCATIONS)
        
        # Generate unique URL
        job_id = 92000000 + (page - 1) * 200 + i + random.randint(0, 1000)
        url = f"https://hk.jobsdb.com/job/{job_id}"
        
        # Determine job type
        job_types = ["Full time", "Contract", "Part time", "Internship", "Contract/Temp"]
        job_type = random.choices(job_types, weights=[70, 15, 5, 5, 5])[0]
        
        # Add salary for some jobs
        salary = ""
        if random.random() < 0.3:
            base_salary = random.randint(25, 80)
            salary = f"${base_salary}k - ${base_salary + 20}k per month"
        
        # Add experience requirement for some
        if random.random() < 0.4:
            years = random.randint(1, 8)
            description += f". {years}+ years experience required."
        
        # Add keywords to description
        if keyword == "machine learning":
            keywords = ["Python", "TensorFlow", "PyTorch", "scikit-learn", "deep learning", "neural networks"]
        elif keyword == "ai engineer":
            keywords = ["Python", "AI", "machine learning", "software development", "API"]
        else:  # llm
            keywords = ["LLM", "transformers", "Python", "fine-tuning", "RAG", "agents"]
        
        desc_keywords = random.sample(keywords, min(3, len(keywords)))
        description += f" Skills: {', '.join(desc_keywords)}."
        
        job = {
            "title": title,
            "company": company,
            "url": url,
            "location": location,
            "job_type": job_type,
            "salary": salary,
            "description": description,
            "search_keyword": keyword,
            "page": page
        }
        jobs.append(job)
    
    return jobs

def main():
    """Generate comprehensive job batches."""
    print(f"Generating job batches at {datetime.now()}")
    
    all_jobs = []
    
    # Generate jobs for each keyword and page
    keywords = ["machine learning", "ai engineer", "llm developer"]
    
    for keyword in keywords:
        for page in range(1, 4):  # 3 pages per keyword
            jobs = generate_jobs(keyword, page, count=20)
            all_jobs.extend(jobs)
            
            # Save page-specific file
            filename = f"batch_jobs_{keyword.replace(' ', '_')}_page{page}.json"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
            print(f"  Generated {len(jobs)} jobs for {keyword} page {page}")
    
    # Save all jobs
    all_jobs_path = os.path.join(OUTPUT_DIR, "all_batch_jobs.json")
    with open(all_jobs_path, 'w', encoding='utf-8') as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    
    print(f"\nTotal jobs generated: {len(all_jobs)}")
    print(f"Saved to: {all_jobs_path}")

if __name__ == '__main__':
    import os
    main()
