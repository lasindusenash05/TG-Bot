
import os
from datetime import datetime

class ChatLogger:
    def __init__(self):
        self.logs_dir = "chat_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def save_message(self, user_id, message_text, is_bot_response=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        sender = "Bot" if is_bot_response else f"User {user_id}"
        log_entry = f"[{timestamp}] {sender}: {message_text}\n"
        
        # Save to daily log file
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.logs_dir, f"chat_log_{date}.txt")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    def get_chat_history(self, start_time, end_time):
        chat_history = []
        try:
            date = start_time.strftime("%Y-%m-%d")
            log_file = os.path.join(self.logs_dir, f"chat_log_{date}.txt")
            
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            timestamp_str = line[1:line.find("]")]
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %I:%M:%S %p")
                            if start_time <= timestamp <= end_time:
                                chat_history.append(line.strip())
                        except:
                            continue
                            
        except Exception as e:
            print(f"Error reading chat history: {str(e)}")
            
        return chat_history
