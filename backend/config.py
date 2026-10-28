import os
import re
from dotenv import load_dotenv

load_dotenv()


def database_url():
    """DATABASE_URL, pointed at the psycopg 3 driver.

    Hosts hand out postgres:// or postgresql:// URLs; on those SQLAlchemy
    picks psycopg2, which isn't installed.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
    SQLALCHEMY_DATABASE_URI = database_url()
    # Drop connections the server has closed instead of failing the next request.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration - Production Optimized
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    
    # Ensure JWT_SECRET_KEY is set
    if JWT_SECRET_KEY == "jwt-secret-key-change-in-production":
        import warnings
        warnings.warn("JWT_SECRET_KEY is using default value. Please set JWT_SECRET_KEY environment variable for production.")
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours (was 15 minutes)
    JWT_REFRESH_TOKEN_EXPIRES = 604800  # 7 days
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = False  # Set to True in production with HTTPS
    JWT_COOKIE_CSRF_PROTECT = False  # Set to True for CSRF protection
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_DOMAIN = None  # Auto-detect domain
    JWT_COOKIE_PATH = "/"  # Available for entire domain
    JWT_TOKEN_LOCATION = ["headers", "cookies"]  # Allow both headers and cookies