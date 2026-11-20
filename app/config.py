import os

from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
FERNET_KEY = os.environ["FERNET_KEY"]
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemma3:4b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
DB_URL = os.environ["DB_URL"]  # ex : postgresql+psycopg://user:Chat@127.0.0.1:5432/medassist
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.45"))
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200").split(",")
    if o.strip()
]
CHAT_NUM_CTX = int(os.getenv("CHAT_NUM_CTX", "3072"))        
CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "350"))   
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "2m")                   
STRONG_SCORE = 0.75
