import sqlite3
import os
from datetime import datetime
import difflib

DB = 'memory.db'

class Memory:
    def __init__(self):
        self.conn = sqlite3.connect(DB, check_same_thread=False)
        self.conn.execute('CREATE TABLE IF NOT EXISTS facts(key TEXT PRIMARY KEY, value TEXT)')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # New table for storing every word spoken
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS word_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                context TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                frequency INTEGER DEFAULT 1
            )
        ''')
        # Index for faster word lookups
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_word_memory_word ON word_memory(word)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_word_memory_timestamp ON word_memory(timestamp)')
        self.conn.commit()

    def remember(self, key, value):
        key = key.strip().lower()
        self.conn.execute('REPLACE INTO facts VALUES (?,?)', (key, value))
        self.conn.commit()

    def recall(self, key):
        key = key.strip().lower()
        cur = self.conn.execute('SELECT value FROM facts WHERE key=?', (key,))
        row = cur.fetchone()
        if row:
            return row[0]
        # Fuzzy match fallback
        all_keys = [row[0] for row in self.conn.execute('SELECT key FROM facts').fetchall()]
        matches = difflib.get_close_matches(key, all_keys, n=1, cutoff=0.6)
        if matches:
            cur = self.conn.execute('SELECT value FROM facts WHERE key=?', (matches[0],))
            row = cur.fetchone()
            if row:
                return row[0]
        return None

    def forget(self, key):
        self.conn.execute('DELETE FROM facts WHERE key=?', (key,))
        self.conn.commit()

    def remember_chat_message(self, role, content):
        self.conn.execute('INSERT INTO chat_history (role, content) VALUES (?, ?)', (role, content))
        self.conn.commit()

    def recall_chat_history(self, limit=10):
        cur = self.conn.execute('SELECT role, content FROM chat_history ORDER BY timestamp DESC LIMIT ?', (limit,))
        # Reverse the results to get chronological order for the API
        history = cur.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(history)]

    def forget_chat_history(self):
        self.conn.execute('DELETE FROM chat_history')
        self.conn.commit()

    # New methods for word-level memory
    def remember_word(self, word, context=None):
        """Store a single word with optional context"""
        word = word.lower().strip()
        if not word or len(word) < 2:  # Skip very short words
            return
            
        # Check if word already exists recently (within last 5 minutes)
        cur = self.conn.execute('''
            SELECT id, frequency FROM word_memory 
            WHERE word = ? AND timestamp > datetime('now', '-5 minutes')
            ORDER BY timestamp DESC LIMIT 1
        ''', (word,))
        row = cur.fetchone()
        
        if row:
            # Update frequency of existing word
            self.conn.execute('UPDATE word_memory SET frequency = frequency + 1 WHERE id = ?', (row[0],))
        else:
            # Insert new word
            self.conn.execute('INSERT INTO word_memory (word, context) VALUES (?, ?)', (word, context))
        
        self.conn.commit()

    def remember_sentence(self, sentence, context=None):
        """Break down a sentence and store each word"""
        if not sentence:
            return
            
        words = sentence.lower().split()
        for word in words:
            # Clean the word (remove punctuation)
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word:
                self.remember_word(clean_word, context)

    def get_word_frequency(self, word, hours=24):
        """Get how often a word has been spoken in the last N hours"""
        cur = self.conn.execute('''
            SELECT SUM(frequency) FROM word_memory 
            WHERE word = ? AND timestamp > datetime('now', '-{} hours')
        '''.format(hours), (word.lower(),))
        row = cur.fetchone()
        return row[0] if row[0] else 0

    def get_most_common_words(self, limit=10, hours=24):
        """Get the most frequently spoken words in the last N hours"""
        cur = self.conn.execute('''
            SELECT word, SUM(frequency) as total_freq 
            FROM word_memory 
            WHERE timestamp > datetime('now', '-{} hours')
            GROUP BY word 
            ORDER BY total_freq DESC 
            LIMIT ?
        '''.format(hours), (limit,))
        return cur.fetchall()

    def get_recent_words(self, limit=20):
        """Get the most recently spoken words"""
        cur = self.conn.execute('''
            SELECT word, context, timestamp, frequency 
            FROM word_memory 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        return cur.fetchall()

    def search_words(self, query, limit=10):
        """Search for words containing the query"""
        cur = self.conn.execute('''
            SELECT word, context, timestamp, frequency 
            FROM word_memory 
            WHERE word LIKE ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (f'%{query.lower()}%', limit))
        return cur.fetchall()

    def get_word_context(self, word, limit=5):
        """Get recent contexts where a word was used"""
        cur = self.conn.execute('''
            SELECT context, timestamp 
            FROM word_memory 
            WHERE word = ? AND context IS NOT NULL 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (word.lower(), limit))
        return cur.fetchall()

    def get_vocabulary_stats(self):
        """Get statistics about the vocabulary"""
        cur = self.conn.execute('SELECT COUNT(DISTINCT word) FROM word_memory')
        unique_words = cur.fetchone()[0]
        
        cur = self.conn.execute('SELECT COUNT(*) FROM word_memory')
        total_words = cur.fetchone()[0]
        
        cur = self.conn.execute('SELECT COUNT(*) FROM word_memory WHERE timestamp > datetime("now", "-24 hours")')
        words_today = cur.fetchone()[0]
        
        return {
            'unique_words': unique_words,
            'total_words': total_words,
            'words_today': words_today
        }

    def get_conversation_summary(self, limit=5):
        """Get a summary of recent conversations for context"""
        cur = self.conn.execute('''
            SELECT role, content, timestamp 
            FROM chat_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit * 2,))  # Get more to pair user/assistant messages
        
        messages = cur.fetchall()
        summary = []
        
        # Group messages by conversation pairs
        for i in range(0, len(messages) - 1, 2):
            if i + 1 < len(messages):
                user_msg = messages[i + 1]  # User message
                assistant_msg = messages[i]  # Assistant message
                
                if user_msg[0] == 'user' and assistant_msg[0] == 'assistant':
                    summary.append({
                        'user': user_msg[1],
                        'assistant': assistant_msg[1],
                        'timestamp': user_msg[2]
                    })
        
        return summary

    def get_recent_topics(self, limit=10):
        """Extract recent conversation topics for context"""
        cur = self.conn.execute('''
            SELECT content 
            FROM chat_history 
            WHERE role = 'user' 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        topics = []
        for row in cur.fetchall():
            content = row[0].lower()
            # Extract potential topics (simple keyword extraction)
            words = content.split()
            for word in words:
                if len(word) > 3 and word not in ['what', 'when', 'where', 'which', 'that', 'this', 'with', 'from', 'have', 'been', 'they', 'will', 'your', 'about', 'would', 'could', 'should']:
                    topics.append(word)
        
        return list(set(topics))[:limit]  # Remove duplicates and limit

    def bulk_remember(self, facts_dict):
        """Add multiple key-value facts to memory at once."""
        for key, value in facts_dict.items():
            self.remember(key, value)

    def clear_facts(self):
        self.conn.execute('DELETE FROM facts')
        self.conn.commit()
