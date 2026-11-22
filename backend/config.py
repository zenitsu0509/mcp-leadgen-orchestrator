"""
Simple configuration module for the application.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Groq API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    
    # Email/SMTP
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
    SENDER_NAME = os.getenv("SENDER_NAME", "Himanshu")
    COMPANY_NAME = os.getenv("COMPANY_NAME", "AI Solutions")
    REPLY_TO_EMAIL = os.getenv("REPLY_TO_EMAIL", SMTP_FROM_EMAIL)
    
    # Application
    DRY_RUN_MODE = os.getenv("DRY_RUN_MODE", "true").lower() == "true"
    REQUIRE_EMAIL_APPROVAL = os.getenv("REQUIRE_EMAIL_APPROVAL", "true").lower() == "true"
    PIPELINE_WORKER_ENABLED = os.getenv("PIPELINE_WORKER_ENABLED", "true").lower() == "true"
    WORKER_POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "1.5"))
    JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
    API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
    APP_ENV = os.getenv("APP_ENV", "development")
    CORS_ORIGINS = [origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000"
    ).split(",") if origin.strip()]
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/leads.db")
    
    # API
    API_PORT = int(os.getenv("API_PORT", "8000"))
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))
    
    # n8n Configuration
    N8N_URL = os.getenv("N8N_URL", "https://92e249f97c50.ngrok-free.app")
    N8N_WORKFLOW_ID = os.getenv("N8N_WORKFLOW_ID", "Dl9AKWe6K3mx3qUO2q-VJ")

    # Follow-up and Inbound Configuration
    AUTO_FOLLOWUP_ENABLED = os.getenv("AUTO_FOLLOWUP_ENABLED", "true").lower() == "true"
    FOLLOWUP_DELAY_DAYS = int(os.getenv("FOLLOWUP_DELAY_DAYS", "3"))
    FOLLOWUP_DELAY_DAYS_STEP2 = int(os.getenv("FOLLOWUP_DELAY_DAYS_STEP2", "4"))
    MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", "2"))
    INBOUND_WEBHOOK_SECRET = os.getenv("INBOUND_WEBHOOK_SECRET", "")
