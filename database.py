import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    """Stelle Verbindung zur PostgreSQL Datenbank her"""
    try:
        # Railway DATABASE_URL parsen
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            print(f"🔗 Nutze DATABASE_URL: {database_url[:50]}...")
            
            # URL parsen für Railway-Format
            if database_url.startswith('postgresql://'):
                # Standard psycopg2 Verbindung
                conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            else:
                # Railway-Format parsen
                url = urlparse(database_url)
                conn = psycopg2.connect(
                    host=url.hostname,
                    database=url.path[1:],  # Remove leading slash
                    user=url.username,
                    password=url.password,
                    port=url.port or 5432,
                    cursor_factory=RealDictCursor
                )
        else:
            # Fallback: Einzelne Umgebungsvariablen
            print("⚠️  Keine DATABASE_URL - nutze Railway Env-Vars")
            conn = psycopg2.connect(
                host=os.environ.get('PGHOST', 'localhost'),
                database=os.environ.get('PGDATABASE', 'railway'),
                user=os.environ.get('PGUSER', 'postgres'),
                password=os.environ.get('PGPASSWORD', ''),
                port=os.environ.get('PGPORT', '5432'),
                cursor_factory=RealDictCursor
            )
        
        print("✅ Datenbankverbindung erfolgreich!")
        return conn
        
    except Exception as e:
        print(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
        
        # Debug: Zeige verfügbare Env-Vars
        print("🔍 Verfügbare DB-Variablen:")
        for key in ['DATABASE_URL', 'PGHOST', 'PGDATABASE', 'PGUSER', 'PGPORT']:
            value = os.environ.get(key, 'nicht gesetzt')
            if 'password' in key.lower():
                value = '***' if value != 'nicht gesetzt' else value
            print(f"   {key}: {value}")
        
        raise

def execute_query(query, params=None, fetch=False):
    """Führe SQL-Query aus mit automatischer Verbindungsverwaltung"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return True
            
    except Exception as e:
        print(f"❌ Query-Fehler: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

def init_database():
    """Initialisiere alle Datenbank-Tabellen"""
    print("🔧 Initialisiere Datenbank...")
    
    tables = [
        '''CREATE TABLE IF NOT EXISTS projekte (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            kunde VARCHAR(255) NOT NULL,
            ersteller VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'gestoppt',
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        
        '''CREATE TABLE IF NOT EXISTS sitzungen (
            id SERIAL PRIMARY KEY,
            projekt_id INTEGER REFERENCES projekte(id),
            mitarbeiter VARCHAR(255) NOT NULL,
            teilbereich VARCHAR(100) NOT NULL,
            start_zeit TIMESTAMP NOT NULL,
            end_zeit TIMESTAMP,
            dauer_minuten INTEGER
        )''',
        
        '''CREATE TABLE IF NOT EXISTS benutzer (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    ]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for table_sql in tables:
            cursor.execute(table_sql)
        
        conn.commit()
        conn.close()
        print("✅ Datenbank erfolgreich initialisiert!")
        
    except Exception as e:
        print(f"❌ Fehler bei Initialisierung: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise