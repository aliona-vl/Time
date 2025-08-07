import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Stelle Verbindung zur PostgreSQL Datenbank her"""
    try:
        # Railway automatische DATABASE_URL verwenden
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            print(f"🔗 Nutze DATABASE_URL: {database_url[:50]}...")
            conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        else:
            # Fallback für lokale Entwicklung
            print("⚠️  Keine DATABASE_URL gefunden - nutze lokale Verbindung")
            conn = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'timetracking'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', 'password'),
                port=os.environ.get('DB_PORT', '5432'),
                cursor_factory=RealDictCursor
            )
        
        print("✅ Datenbankverbindung erfolgreich!")
        return conn
        
    except Exception as e:
        print(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
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
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            beendet_am TIMESTAMP NULL,
            erster_start TIMESTAMP NULL,
            letzter_start TIMESTAMP NULL
        )''',
        
        '''CREATE TABLE IF NOT EXISTS mitarbeiter (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        
        '''CREATE TABLE IF NOT EXISTS kunden (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        
        '''CREATE TABLE IF NOT EXISTS sitzungen (
            id SERIAL PRIMARY KEY,
            projekt_id INTEGER REFERENCES projekte(id) ON DELETE CASCADE,
            mitarbeiter VARCHAR(255) NOT NULL,
            teilbereich VARCHAR(100) NOT NULL,
            start_zeit TIMESTAMP NOT NULL,
            end_zeit TIMESTAMP,
            dauer_minuten INTEGER,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        
        '''CREATE TABLE IF NOT EXISTS aktive_sitzungen (
            id SERIAL PRIMARY KEY,
            projekt_id INTEGER REFERENCES projekte(id) ON DELETE CASCADE,
            mitarbeiter VARCHAR(255) NOT NULL,
            teilbereich VARCHAR(100) NOT NULL,
            start_zeit TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        
        '''CREATE TABLE IF NOT EXISTS benutzer (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            team_code_verwendet VARCHAR(50),
            registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            aktiv BOOLEAN DEFAULT TRUE
        )''',
        
        '''CREATE TABLE IF NOT EXISTS password_resets (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            token VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used BOOLEAN DEFAULT FALSE
        )'''
    ]
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for table_sql in tables:
            cursor.execute(table_sql)
        
        # Standard-Daten einfügen
        cursor.execute('''
            INSERT INTO mitarbeiter (name) 
            VALUES ('Max Mustermann'), ('Anna Schmidt'), ('Tom Weber')
            ON CONFLICT (name) DO NOTHING
        ''')
        
        cursor.execute('''
            INSERT INTO kunden (name) 
            VALUES ('Mustermann GmbH'), ('Schmidt & Co'), ('Weber Bau')
            ON CONFLICT (name) DO NOTHING
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Datenbank erfolgreich initialisiert!")
        
    except Exception as e:
        print(f"❌ Fehler bei Initialisierung: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise