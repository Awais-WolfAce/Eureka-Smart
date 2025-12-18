import re
import openai
import json
from utils.config import Config

client = openai.AzureOpenAI(
    api_key=Config.OPENAI_API_KEY,
    api_version="2024-02-15-preview",
    azure_endpoint=Config.OPENAI_ENDPOINT
)

class Intent:
    def __init__(self, name, entities=None):
        self.name = name
        self.entities = entities or {}

class NLU:
    def simple_rules(self, text):
        txt = text.lower()

        # Database query intents - be very permissive to catch all database-related queries
        if any(phrase in txt for phrase in [
            'query database', 'database query', 'query the database', 'show database', 
            'database info', 'adventureworks', 'adventure works', 'sql', 'query',
            'how many', 'count', 'total', 'list', 'show me', 'what', 'who', 'when', 'where',
            'sales', 'products', 'customers', 'orders', 'employees', 'database', 'data',
            'table', 'tables', 'records', 'rows', 'information', 'details'
        ]):
            return Intent('query_database', {'query': text})

        # If it sounds like a question or data request, treat as database query
        if any(word in txt for word in ['?', 'how', 'what', 'which', 'tell me', 'show', 'get', 'find']):
            return Intent('query_database', {'query': text})

        return Intent('unknown', {'text': text})

    def parse(self, text):
        # Try rule-based first
        intent = self.simple_rules(text)
        if intent.name == 'query_database':
            return intent

        # Fallback to OpenAI for anything else - but still try to identify as database query
        prompt = (
            "You are an intent parser for a database assistant. "
            "Given the user utterance, determine if it's a database query. "
            "If it asks about data, sales, products, customers, orders, employees, or any business information, "
            "respond with query_database intent. Otherwise, respond with unknown intent. "
            "Respond with JSON: {\"intent\": \"query_database\" or \"unknown\", \"entities\": {\"query\": \"user's original text\"}}"
        )
        
        try:
            resp = client.chat.completions.create(
                model=Config.OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ]
            )
            
            # parse the JSON from GPT
            data = json.loads(resp.choices[0].message.content)
            intent_name = data.get('intent', 'unknown')
            entities = data.get('entities', {})
            
            if intent_name == 'query_database' and 'query' not in entities:
                entities['query'] = text
            
            return Intent(intent_name, entities)
            
        except Exception as e:
            # Default to database query if we can't parse
            return Intent('query_database', {'query': text})
