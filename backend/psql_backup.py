import os
import subprocess
import logging
from datetime import datetime
import sys
from dotenv import load_dotenv
import gzip

# Load environment variables from .env file
load_dotenv()

# Configuration
BACKUP_DIR = "backup.log"  # Replace with your backup storage path
PG_HOST = os.getenv("POSTGRES_SERVER", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
PG_DATABASES = [os.getenv("POSTGRES_DB", "poultry_db")]
LOG_FILE = os.path.join(BACKUP_DIR, "backup.log")

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_message(message, level="info"):
    """Log messages to file and print to console."""
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    print(message)

def backup_postgres():
    """Backup PostgreSQL databases."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success = True
    
    for db in PG_DATABASES:
        backup_path = os.path.join(BACKUP_DIR, f"postgres_{db}_backup_{timestamp}.sql.gz")
        command = f"pg_dump -h {PG_HOST} -p {PG_PORT} -U {PG_USER} {db}"
        
        try:
            with gzip.open(backup_path, 'wb') as f:
                process = subprocess.Popen(command, shell=True, stdout=f, stderr=subprocess.PIPE)
                _, stderr = process.communicate()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, command, output=stderr)
            log_message(f"Successfully backed up database {db} to {backup_path}")
        except subprocess.CalledProcessError as e:
            log_message(f"Error backing up database {db}: {e.stderr.decode('utf-8')}", level="error")
            success = False
    
    return success

def cleanup_old_backups(keep_days=7):
    """Delete backups older than keep_days."""
    cutoff_time = datetime.now().timestamp() - (keep_days * 86400)
    
    for file in os.listdir(BACKUP_DIR):
        file_path = os.path.join(BACKUP_DIR, file)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
            try:
                os.remove(file_path)
                log_message(f"Deleted old backup: {file_path}")
            except Exception as e:
                log_message(f"Error deleting old backup {file_path}: {e}", level="error")

def main():
    """Main function to run backups."""
    log_message("Starting PostgreSQL backup process...")
    
    # Backup PostgreSQL databases
    postgres_success = backup_postgres()
    
    # Cleanup old backups
    cleanup_old_backups()
    
    # Summary
    if postgres_success:
        log_message("Backup process completed successfully.")
    else:
        log_message("Backup process completed with errors.", level="error")
        sys.exit(1)

if __name__ == "__main__":
    main()