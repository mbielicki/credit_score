import os
import sys
import logging
from sqlmodel import create_engine, text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set.")
        sys.exit(1)

    # Path to init.sql from project root
    init_sql_path = "db/init.sql"
    
    if not os.path.exists(init_sql_path):
        logger.error(f"Migration script not found at {init_sql_path}")
        sys.exit(1)

    logger.info(f"Connecting to database to run migrations...")
    
    try:
        # We don't need the full app engine here, just a simple one
        engine = create_engine(database_url)
        
        with open(init_sql_path, "r") as f:
            sql_script = f.read()
        
        with engine.connect() as connection:
            # PostgreSQL can execute multiple statements in one call
            connection.execute(text(sql_script))
            connection.commit()
            logger.info("Migrations completed successfully.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
