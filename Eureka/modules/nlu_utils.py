import re

def extract_folder_name(text):
    # Extract folder name after "create folder" or similar phrases
    match = re.search(r'(?:create|make)\s+folder\s+(?:named\s+)?([^\s]+)', text.lower())
    return match.group(1) if match else None 