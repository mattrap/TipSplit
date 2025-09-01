import os
from datetime import datetime

# Determine log file location in the user's home directory
LOG_FILE = os.path.join(os.path.expanduser("~"), "TipSplit_debug.log")

def log_debug(message):
    """Append a timestamped debug message to the log file and print it."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Ensure logging never raises an exception
        pass
    print(line)
