"""
Database setup and models for the lead generation system.
Uses SQLite for persistence with status tracking.
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import json


class LeadStatus(str, Enum):
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    MESSAGED = "MESSAGED"
    SENT = "SENT"
    FAILED = "FAILED"


class Database:
    def __init__(self, db_path: str = "./data/leads.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Leads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                company_name TEXT NOT NULL,
                role_title TEXT NOT NULL,
                industry TEXT NOT NULL,
                company_website TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                linkedin_url TEXT NOT NULL,
                country TEXT NOT NULL,
                comments TEXT,
                source TEXT,
                status TEXT DEFAULT 'NEW',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Enrichment table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enrichment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                company_size TEXT,
                persona_tag TEXT,
                pain_points TEXT,
                buying_triggers TEXT,
                confidence_score INTEGER,
                enrichment_mode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                variation TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)
        
        # Outreach table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                sent_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (message_id) REFERENCES messages(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def insert_lead(self, lead_data: Dict) -> int:
        """Insert a new lead"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO leads (
                full_name, company_name, role_title, industry,
                company_website, email, phone, linkedin_url, country, comments, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_data['full_name'],
            lead_data['company_name'],
            lead_data['role_title'],
            lead_data['industry'],
            lead_data['company_website'],
            lead_data['email'],
            lead_data.get('phone', ''),
            lead_data['linkedin_url'],
            lead_data['country'],
            lead_data.get('comments', ''),
            lead_data.get('source', 'external')
        ))
        
        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return lead_id
    
    def insert_enrichment(self, lead_id: int, enrichment_data: Dict):
        """Insert enrichment data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO enrichment (
                lead_id, company_size, persona_tag, pain_points,
                buying_triggers, confidence_score, enrichment_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_id,
            enrichment_data['company_size'],
            enrichment_data['persona_tag'],
            json.dumps(enrichment_data['pain_points']),
            json.dumps(enrichment_data['buying_triggers']),
            enrichment_data['confidence_score'],
            enrichment_data.get('enrichment_mode', 'offline')
        ))
        
        conn.commit()
        conn.close()
    
    def insert_message(self, lead_id: int, channel: str, variation: str, content: str) -> int:
        """Insert a generated message"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages (lead_id, channel, variation, content)
            VALUES (?, ?, ?, ?)
        """, (lead_id, channel, variation, content))
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id
    
    def insert_outreach(self, lead_id: int, message_id: int, channel: str):
        """Record outreach attempt"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO outreach (lead_id, message_id, channel)
            VALUES (?, ?, ?)
        """, (lead_id, message_id, channel))
        
        conn.commit()
        conn.close()
    
    def update_lead_status(self, lead_id: int, status: LeadStatus):
        """Update lead status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE leads 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status.value, lead_id))
        
        conn.commit()
        conn.close()
    
    def update_outreach_status(self, outreach_id: int, status: str, error_message: Optional[str] = None):
        """Update outreach status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status == 'SENT':
            cursor.execute("""
                UPDATE outreach 
                SET status = ?, sent_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE id = ?
            """, (status, error_message, outreach_id))
        else:
            cursor.execute("""
                UPDATE outreach 
                SET status = ?, error_message = ?, retry_count = retry_count + 1
                WHERE id = ?
            """, (status, error_message, outreach_id))
        
        conn.commit()
        conn.close()
    
    def get_leads_by_status(self, status: Optional[LeadStatus] = None) -> List[Dict]:
        """Get leads filtered by status, ordered by newest first"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC", (status.value,))
        else:
            cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        leads = [dict(row) for row in rows]
        conn.close()
        return leads
    
    def get_lead_with_enrichment(self, lead_id: int) -> Optional[Dict]:
        """Get lead with enrichment data"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT l.*, e.company_size, e.persona_tag, e.pain_points,
                   e.buying_triggers, e.confidence_score
            FROM leads l
            LEFT JOIN enrichment e ON l.id = e.lead_id
            WHERE l.id = ?
        """, (lead_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        lead = dict(row)
        
        # Parse JSON fields
        if lead.get('pain_points'):
            try:
                lead['pain_points'] = json.loads(lead['pain_points'])
            except:
                lead['pain_points'] = []
        
        if lead.get('buying_triggers'):
            try:
                lead['buying_triggers'] = json.loads(lead['buying_triggers'])
            except:
                lead['buying_triggers'] = []
        
        return lead
    
    def get_lead_messages(self, lead_id: int) -> Dict:
        """Get generated messages for a lead"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT channel, variation, content
            FROM messages
            WHERE lead_id = ?
            ORDER BY created_at DESC
        """, (lead_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = {}
        for row in rows:
            channel = row['channel']
            variation = row['variation'].lower()
            content = row['content']
            
            if channel == 'email':
                # Parse email (format: "Subject: ...\n\nBody...")
                parts = content.split('\n\n', 1)
                subject = parts[0].replace('Subject: ', '').strip() if len(parts) > 0 else 'No Subject'
                body = parts[1].strip() if len(parts) > 1 else content
                messages[f'email_{variation}'] = {
                    'subject': subject,
                    'body': body
                }
            else:
                messages[f'{channel}_{variation}'] = {
                    'message': content
                }
        
        return messages
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = dict(row)
            if data.get('pain_points'):
                data['pain_points'] = json.loads(data['pain_points'])
            if data.get('buying_triggers'):
                data['buying_triggers'] = json.loads(data['buying_triggers'])
            return data
        return None
    
    def get_metrics(self) -> Dict:
        """Get pipeline metrics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total leads
        cursor.execute("SELECT COUNT(*) FROM leads")
        total_leads = cursor.fetchone()[0]
        
        # Leads by status
        cursor.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Messages generated
        cursor.execute("SELECT COUNT(*) FROM messages")
        messages_generated = cursor.fetchone()[0]
        
        # Messages sent
        cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'SENT'")
        messages_sent = cursor.fetchone()[0]
        
        # Failed messages
        cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'FAILED'")
        messages_failed = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_leads": total_leads,
            "leads_enriched": status_counts.get('ENRICHED', 0) + status_counts.get('MESSAGED', 0) + status_counts.get('SENT', 0),
            "messages_generated": messages_generated,
            "messages_sent": messages_sent,
            "messages_failed": messages_failed,
            "status_breakdown": status_counts
        }
    
    def clear_all_data(self):
        """Clear all data (for testing)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM outreach")
        cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM enrichment")
        cursor.execute("DELETE FROM leads")
        
        conn.commit()
        conn.close()


if __name__ == "__main__":
    import os
    
    # Create data directory if it doesn't exist
    os.makedirs("./data", exist_ok=True)
    
    # Initialize database
    db = Database()
    print("✅ Database initialized successfully!")
    print(f"📁 Database location: {db.db_path}")
