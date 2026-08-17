import os

from dotenv import load_dotenv

load_dotenv(".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
CACHE_TTL_SECONDS = 300
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://idx-stock.netlify.app",
]
