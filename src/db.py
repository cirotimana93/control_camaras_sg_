import psycopg
from contextlib import contextmanager
from src.config import Config

# devCt: conexion directa mediante context manager para liberar recursos de forma automatica
@contextmanager
def getDbConnection():
    connection = psycopg.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_DATABASE,
        user=Config.DB_USERNAME,
        password=Config.DB_PASSWORD,
        connect_timeout=15
    )
    try:
        yield connection
    finally:
        connection.close()
