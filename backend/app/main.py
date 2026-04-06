from fastapi import FastAPI, HTTPException
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="IRB Credit Rating Engine API")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/credit_score_db")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

@app.get("/")
async def root():
    return {
        "message": "IRB Credit Rating Engine API is active", 
        "version": "0.1.0",
        "database_configured": DATABASE_URL is not None
    }

@app.get("/health")
async def health_check():
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "healthy", "database": "connected"}
    else:
        return {"status": "degraded", "database": "disconnected"}
