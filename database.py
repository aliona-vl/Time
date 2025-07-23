import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

def get_db_connection():
    """PostgreSQL Verbindung"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # Lokale Entwicklung
        DATABASE_URL = "postgresql://localhost/rausch_local"
    
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_database():
    """Erstellt alle Tabellen"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Benutzer Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS benutzer (
            email VARCHAR(255) PRIMARY KEY,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            team_code_verwendet VARCHAR(50),
            registriert_am TIMESTAMP NOT NULL
        )
    ''')
    
    # Projekte Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projekte (
            id SERIAL PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            kunde VARCHAR(500) NOT NULL,
            ersteller VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'gestoppt',
            erstellt_am TIMESTAMP NOT NULL,
            erster_start TIMESTAMP,
            letzter_start TIMESTAMP,
            beendet_am TIMESTAMP,
            FOREIGN KEY (ersteller) REFERENCES benutzer (email)
        )
    ''')
    
    # Aktive Sitzungen Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aktive_sitzungen (
            id SERIAL PRIMARY KEY,
            projekt_id INTEGER NOT NULL,
            mitarbeiter VARCHAR(255) NOT NULL,
            teilbereich VARCHAR(100) NOT NULL,
            start_zeit TIMESTAMP NOT NULL,
            FOREIGN KEY (projekt_id) REFERENCES projekte (id) ON DELETE CASCADE
        )
    ''')
    
    # Beendete Sitzungen Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sitzungen (
            id SERIAL PRIMARY KEY,
            projekt_id INTEGER NOT NULL,
            mitarbeiter VARCHAR(255) NOT NULL,
            teilbereich VARCHAR(100) NOT NULL,
            start_zeit TIMESTAMP NOT NULL,
            end_zeit TIMESTAMP NOT NULL,
            dauer_minuten INTEGER NOT NULL,
            FOREIGN KEY (projekt_id) REFERENCES projekte (id) ON DELETE CASCADE
        )
    ''')
    
    # Mitarbeiter Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mitarbeiter (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
    ''')
    
    # Kunden Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kunden (
            id SERIAL PRIMARY KEY,
            name VARCHAR(500) UNIQUE NOT NULL
        )
    ''')
    
    conn.commit()
    
    # Standard-Daten einfügen
    insert_default_data(cursor)
    conn.commit()
    conn.close()
    print("✅ Datenbank initialisiert!")

def insert_default_data(cursor):
    """Fügt Standard-Mitarbeiter und Kunden ein"""
    standard_mitarbeiter = ['Andreas', 'Mark', 'Fritz', 'Sabine', 'Thomas']
    standard_kunden = [
        'Bosch Lollar', 'Buderus Guss GmbH', 'Duktus', 'Fritz Winter',
        'Geissler', 'Hasenclever', 'Herborner Pumpenfabrik', 'Nowakowski'
    ]
    
    for ma in standard_mitarbeiter:
        cursor.execute('INSERT INTO mitarbeiter (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (ma,))
    
    for kunde in standard_kunden:
        cursor.execute('INSERT INTO kunden (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (kunde,))

# Hilfsfunktionen für die App
def load_benutzer():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM benutzer')
    benutzer = {row['email']: dict(row) for row in cursor.fetchall()}
    conn.close()
    return benutzer

def save_benutzer(email, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO benutzer (email, password_hash, name, team_code_verwendet, registriert_am)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        name = EXCLUDED.name,
        team_code_verwendet = EXCLUDED.team_code_verwendet
    ''', (email, data['password_hash'], data['name'], 
          data.get('team_code_verwendet'), data['registriert_am']))
    conn.commit()
    conn.close()

def load_mitarbeiter():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM mitarbeiter ORDER BY name')
    mitarbeiter = [row['name'] for row in cursor.fetchall()]
    conn.close()
    return mitarbeiter

def load_kunden():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM kunden ORDER BY name')
    kunden = [row['name'] for row in cursor.fetchall()]
    conn.close()
    return kunden

def load_projekte_for_user(benutzer_email):
    """Lädt alle Projekte für einen Benutzer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Team-Berechtigung prüfen
    cursor.execute('SELECT team_code_verwendet FROM benutzer WHERE email = %s', (benutzer_email,))
    user_data = cursor.fetchone()
    
    if user_data and user_data['team_code_verwendet'] == 'RAUSCH2025':
        cursor.execute('SELECT * FROM projekte ORDER BY erstellt_am DESC')
    else:
        cursor.execute('SELECT * FROM projekte WHERE ersteller = %s ORDER BY erstellt_am DESC', (benutzer_email,))
    
    projekte = []
    for projekt_row in cursor.fetchall():
        projekt = dict(projekt_row)
        
        # Aktive Sitzungen laden
        cursor.execute('''
            SELECT mitarbeiter, teilbereich, start_zeit 
            FROM aktive_sitzungen 
            WHERE projekt_id = %s
        ''', (projekt['id'],))
        
        aktive_sitzungen = {}
        for sitzung in cursor.fetchall():
            aktive_sitzungen[sitzung['mitarbeiter']] = {
                'teilbereich': sitzung['teilbereich'],
                'start': sitzung['start_zeit'].isoformat()
            }
        projekt['aktive_sitzungen'] = aktive_sitzungen
        
        # Teilbereiche laden
        teilbereiche = {}
        for tb in ['besprechung', 'zeichnung', 'aufmass']:
            cursor.execute('''
                SELECT mitarbeiter, start_zeit, end_zeit, dauer_minuten 
                FROM sitzungen 
                WHERE projekt_id = %s AND teilbereich = %s
                ORDER BY start_zeit DESC
            ''', (projekt['id'], tb))
            
            sitzungen = []
            gesamt_minuten = 0
            
            for sitzung in cursor.fetchall():
                sitzung_dict = {
                    'mitarbeiter': sitzung['mitarbeiter'],
                    'start': sitzung['start_zeit'].isoformat(),
                    'end': sitzung['end_zeit'].isoformat(),
                    'dauer_minuten': sitzung['dauer_minuten']
                }
                sitzungen.append(sitzung_dict)
                gesamt_minuten += sitzung['dauer_minuten']
            
            teilbereiche[tb] = {
                'sitzungen': sitzungen,
                'gesamt_minuten': gesamt_minuten
            }
        
        projekt['teilbereiche'] = teilbereiche
        
        # Datumskonvertierung für Templates
        if projekt['erstellt_am']:
            projekt['erstellt_am'] = projekt['erstellt_am'].isoformat()
        if projekt['beendet_am']:
            projekt['beendet_am'] = projekt['beendet_am'].isoformat()
        if projekt['erster_start']:
            projekt['erster_start'] = projekt['erster_start'].isoformat()
        if projekt['letzter_start']:
            projekt['letzter_start'] = projekt['letzter_start'].isoformat()
            
        projekte.append(projekt)
    
    conn.close()
    return projekte