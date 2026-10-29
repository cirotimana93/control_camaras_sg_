import os
from dotenv import load_dotenv

# devCt: carga de variables de entorno con limpieza de comillas y espacios
load_dotenv()

def getCleanEnv(key: str, defaultValue: str = "") -> str:
    rawValue = os.getenv(key, defaultValue)
    if rawValue is None:
        return defaultValue
    return rawValue.strip().strip('"').strip("'")

class Config:
    # database
    DB_HOST = getCleanEnv("DB_HOST", "localhost")
    DB_PORT = int(getCleanEnv("DB_PORT", "5432"))
    DB_DATABASE = getCleanEnv("DB_DATABASE", "db_cctv")
    DB_USERNAME = getCleanEnv("DB_USERNAME", "postgres")
    DB_PASSWORD = getCleanEnv("DB_PASSWORD", "")
    
    # emails
    EMAIL_RECEPTOR = getCleanEnv("EMAIL_RECEPTOR", "")
    EMAIL_EMISOR = getCleanEnv("EMAIL_EMISOR", "")
    
    # microsoft graph api
    GRAPH_CLIENT_ID = getCleanEnv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET = getCleanEnv("GRAPH_CLIENT_SECRET", "")
    GRAPH_TENANT_ID = getCleanEnv("GRAPH_TENANT_ID", "")
