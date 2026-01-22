"""
Simple configuration module for the application.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Groq API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    # Email/SMTP
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
    
    # Application
    DRY_RUN_MODE = os.getenv("DRY_RUN_MODE", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
    
    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/leads.db")
    
    # API
    API_PORT = int(os.getenv("API_PORT", "8000"))
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))
    
    # n8n Configuration
    N8N_URL = os.getenv("N8N_URL", "https://92e249f97c50.ngrok-free.app")
    N8N_WORKFLOW_ID = os.getenv("N8N_WORKFLOW_ID", "Dl9AKWe6K3mx3qUO2q-VJ")
