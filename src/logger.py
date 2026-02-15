from datetime import datetime
import os

class Logger:
    def __init__(self):
        os.makedirs('logs', exist_ok=True)
        self.filename: str = f"logs/chatbot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    def log_error(self, error: str):
        with open(self.filename, 'a') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ERROR: {error}\n")

    def log_message(self, message: str):
        with open(self.filename, 'a') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - MESSAGE: {message}\n")

    