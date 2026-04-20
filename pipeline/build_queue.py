"""Build queue from web search results."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
queue_file = REPO_ROOT / "jobs" / "queue.json"
existing = json.loads(queue_file.read_text()) if queue_file.exists() else []
existing_urls = {item.get("linkedin_url", "") for item in existing}

skip_companies = {
    "people in ai", "d24 search", "techolution", "sectech solutions", "pocket",
    "hanalytica", "james search group", "brooksource", "elantis", "lorven technologies",
    "softserve", "nayya", "coalition", "linkedin", "quantiphi", "career soft solutions",
    "sr2", "oxbow talent", "incedo", "rightclick", "24 seven talent", "bluecloud",
    "jove", "the phoenix group", "anthropic", "netflix", "openai", "jane street",
    "notion", "techcorp",
}

new_jobs = [
    {"title": "Senior Staff AI Engineer", "company": "Palo Alto Networks", "linkedin_url": "https://www.linkedin.com/jobs/view/4249438455/", "location": "Remote"},
    {"title": "Senior Staff AI Engineer / Senior Technical Lead, AI Modeling", "company": "LinkedIn Corp", "linkedin_url": "https://www.linkedin.com/jobs/view/4379039102/", "location": "Remote"},
    {"title": "Staff AI Engineer, Agent Orchestration", "company": "CookUnity", "linkedin_url": "https://www.linkedin.com/jobs/view/4312825730/", "location": "Remote"},
    {"title": "AI/LLM Engineer (Remote)", "company": "Safe Sign Technologies", "linkedin_url": "https://www.linkedin.com/jobs/view/4155460553/", "location": "Remote"},
    {"title": "Generative AI Engineer (100% Remote)", "company": "Radian", "linkedin_url": "https://www.linkedin.com/jobs/view/4061794378/", "location": "Remote"},
    {"title": "AI Architect (Agentic Platform) - Remote", "company": "Dice Agentic", "linkedin_url": "https://www.linkedin.com/jobs/view/4381884984/", "location": "Remote"},
    {"title": "Remote GenAI Solutions Architect", "company": "Beacon Hill", "linkedin_url": "https://www.linkedin.com/jobs/view/4251145141/", "location": "Remote"},
    {"title": "Gen AI Architect", "company": "Cognizant", "linkedin_url": "https://www.linkedin.com/jobs/view/3815902283/", "location": "United States"},
    {"title": "AI Architect", "company": "McCarthy Building Companies", "linkedin_url": "https://www.linkedin.com/jobs/view/4077623185/", "location": "United States"},
    {"title": "Full Stack AI Engineer (Remote)", "company": "BJAK", "linkedin_url": "https://www.linkedin.com/jobs/view/4263939256/", "location": "Remote"},
    {"title": "Full Stack AI Engineer", "company": "Intelligenic", "linkedin_url": "https://www.linkedin.com/jobs/view/3917204174/", "location": "San Francisco"},
    {"title": "Full Stack AI Engineer", "company": "Jobot", "linkedin_url": "https://www.linkedin.com/jobs/view/4376252722/", "location": "Remote"},
    {"title": "AI Engineer (Python | LLM | RAG | Agentic AI)", "company": "Dice Atlanta", "linkedin_url": "https://www.linkedin.com/jobs/view/4362181294/", "location": "Atlanta, GA"},
    {"title": "100% Remote Senior AI Engineer / Agentic AI / LLM", "company": "Newt Global", "linkedin_url": "https://www.linkedin.com/jobs/view/4375940812/", "location": "Remote"},
    {"title": "AI Developer (Python | LLM | GenAI | RAG Expert) Remote", "company": "Dice Remote", "linkedin_url": "https://www.linkedin.com/jobs/view/4276862950/", "location": "Remote"},
    {"title": "Senior Deep Learning Engineer, Agentic AI", "company": "NVIDIA", "linkedin_url": "https://www.linkedin.com/jobs/view/4017922703/", "location": "United States"},
    {"title": "100% Remote Agentic AI-ML Engineer (Azure ML, LLM, RAG)", "company": "Talent Groups", "linkedin_url": "https://www.linkedin.com/jobs/view/4333090215/", "location": "Remote"},
    {"title": "Senior AI Full-Stack Engineer (LLMs, RAG, Agentic Systems)", "company": "Talent Global LLC", "linkedin_url": "https://www.linkedin.com/jobs/view/4365808001/", "location": "Remote"},
    {"title": "ML/AI Engineer", "company": "Figma", "linkedin_url": "https://www.linkedin.com/jobs/view/3536500904/", "location": "United States"},
    {"title": "Machine Learning Engineer (Remote)", "company": "Taskify AI", "linkedin_url": "https://www.linkedin.com/jobs/view/4376541770/", "location": "Remote"},
    {"title": "Machine Learning Team Lead (Remote)", "company": "Absorb Software", "linkedin_url": "https://www.linkedin.com/jobs/view/2825752381/", "location": "Remote"},
    {"title": "Senior AI Engineer", "company": "Navisite", "linkedin_url": "https://www.linkedin.com/jobs/view/3824277060/", "location": "Remote"},
    {"title": "Senior AI Engineer - Machine Learning / NLP", "company": "Cynch AI", "linkedin_url": "https://www.linkedin.com/jobs/view/3746568531/", "location": "San Francisco (Hybrid)"},
    {"title": "Generative AI Engineer", "company": "HeyIris.AI", "linkedin_url": "https://www.linkedin.com/jobs/view/3755483791/", "location": "Remote"},
    {"title": "AI Engineer, Professional Services, Google Cloud", "company": "Google", "linkedin_url": "https://www.linkedin.com/jobs/view/2717407714/", "location": "New York, NY"},
    {"title": "Senior Azure Engineer (Gen AI)", "company": "New York Life Insurance", "linkedin_url": "https://www.linkedin.com/jobs/view/3700665194/", "location": "NYC Metro"},
    {"title": "Software Engineer Lead - AI Specialist", "company": "Firsthand", "linkedin_url": "https://www.linkedin.com/jobs/view/3812227606/", "location": "New York, NY"},
    {"title": "Artificial Intelligence Engineer", "company": "Ramp Talent", "linkedin_url": "https://www.linkedin.com/jobs/view/3832910416/", "location": "NYC Metro"},
    {"title": "AI Engineer (LLM) (100% Remote US)", "company": "Tether.io", "linkedin_url": "https://www.linkedin.com/jobs/view/3966082974/", "location": "Remote"},
    {"title": "Machine Learning Engineer, LLM Infrastructure", "company": "Scale AI", "linkedin_url": "https://www.linkedin.com/jobs/view/3744005830/", "location": "San Francisco"},
    # Batch 2
    {"title": "Senior AI/ML Engineer", "company": "Consumer Reports", "linkedin_url": "https://www.linkedin.com/jobs/view/3835341629/", "location": "Yonkers, NY (Remote)"},
    {"title": "Lead AI / ML Engineer", "company": "Consumer Reports", "linkedin_url": "https://www.linkedin.com/jobs/view/3745666303/", "location": "Remote"},
    {"title": "Senior Machine Learning Engineer (MLOps) - Fully Remote", "company": "Averity", "linkedin_url": "https://www.linkedin.com/jobs/view/3580663609/", "location": "Remote"},
    {"title": "AIML - ML Engineer (Privacy)", "company": "Apple", "linkedin_url": "https://www.linkedin.com/jobs/view/3402600275/", "location": "New York, NY"},
    {"title": "Senior Staff Machine Learning Engineer", "company": "TaskRabbit", "linkedin_url": "https://www.linkedin.com/jobs/view/3895672299/", "location": "Remote"},
    {"title": "Senior Machine Learning Engineer (Knowledge Graph), USA Remote", "company": "Dell Technologies", "linkedin_url": "https://www.linkedin.com/jobs/view/2836854347/", "location": "Remote"},
    {"title": "Senior / Staff Machine Learning Engineer", "company": "CloseFactor", "linkedin_url": "https://www.linkedin.com/jobs/view/3655271557/", "location": "Remote"},
    {"title": "Senior Machine Learning Engineer - Remote - USA", "company": "Fullstack", "linkedin_url": "https://www.linkedin.com/jobs/view/4388204266/", "location": "Remote"},
    {"title": "NLP Engineer - Remote", "company": "Weave", "linkedin_url": "https://www.linkedin.com/jobs/view/3623805351/", "location": "New York (Remote)"},
    {"title": "Computer Vision Engineer (100% Remote)", "company": "Jobot CV", "linkedin_url": "https://www.linkedin.com/jobs/view/3528170432/", "location": "Remote"},
    {"title": "Senior Full Stack Python/FastAPI/React Engineer [REMOTE]", "company": "Anovium", "linkedin_url": "https://www.linkedin.com/jobs/view/3715272948/", "location": "Remote"},
    {"title": "Backend Software Engineer (AI, Python / FastAPI)", "company": "Conrad", "linkedin_url": "https://www.linkedin.com/jobs/view/4253880349/", "location": "Remote"},
    {"title": "Senior Python Developer (React and FastAPI)", "company": "R Systems", "linkedin_url": "https://www.linkedin.com/jobs/view/4293010821/", "location": "Remote"},
    {"title": "Senior Machine Learning Engineer", "company": "EIS Ltd", "linkedin_url": "https://www.linkedin.com/jobs/view/3197774374/", "location": "Remote"},
    {"title": "AI/ML Engineering Manager", "company": "Lockheed Martin", "linkedin_url": "https://www.linkedin.com/jobs/view/3719121330/", "location": "Fort Worth, TX"},
    {"title": "AI Engineer, Entry Level", "company": "Jobright.ai", "linkedin_url": "https://www.linkedin.com/jobs/view/4388600832/", "location": "United States"},
    {"title": "NLP Engineer", "company": "Samsung Electronics America", "linkedin_url": "https://www.linkedin.com/jobs/view/2741561910/", "location": "Mountain View, CA"},
    {"title": "Senior Machine Learning Engineer", "company": "Upwork", "linkedin_url": "https://www.linkedin.com/jobs/view/3273797522/", "location": "Remote"},
    {"title": "Senior Machine Learning Engineer", "company": "Exos", "linkedin_url": "https://www.linkedin.com/jobs/view/2938141067/", "location": "Remote"},
    {"title": "AI/ML Engineer - GTRI", "company": "Georgia Tech Research Institute", "linkedin_url": "https://www.linkedin.com/jobs/view/3816809012/", "location": "Washington, DC"},
    {"title": "Founding Lead Software Engineer (AI)", "company": "Konko AI", "linkedin_url": "https://www.linkedin.com/jobs/view/3732182084/", "location": "New York, NY"},
]

added = 0
for job in new_jobs:
    url = job["linkedin_url"]
    co_lower = job["company"].lower()
    if url in existing_urls:
        continue
    if any(skip in co_lower for skip in skip_companies):
        continue
    job["status"] = "pending"
    job["score"] = 4
    existing.append(job)
    existing_urls.add(url)
    added += 1

queue_file.write_text(json.dumps(existing, indent=2))
print(f"Added {added} new jobs to queue. Total queue size: {len(existing)}")
