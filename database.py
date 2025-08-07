import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

def get_db_connection():
    """Verbindung zur PostgreSQL-Datenbank auf Render"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'timely'),
            user=os.environ.get('DB_USER', 'timely_user'),
            password=os.environ.get('DB_PASSWORD', ''),
            port=os.environ.get('DB_PORT', '5432'),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
        raise

def load_benutzer():
    """Lade alle Benutzer aus der Datenbank"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM benutzer')
        users = cursor.fetchall()
        conn.close()
        
        # Als Dictionary zurückgeben
        result = {}
        for user in users:
            result[user['email']] = dict(user)
        return result
    except Exception as e:
        print(f"❌ Fehler beim Laden der Benutzer: {e}")
        return {}

def save_benutzer(email, benutzer_data):
    """Speichere einen Benutzer in der Datenbank"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO benutzer (email, password_hash, name, team_code_verwendet, registriert_am)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                name = EXCLUDED.name,
                team_code_verwendet = EXCLUDED.team_code_verwendet
        ''', (
            email,
            benutzer_data['password_hash'],
            benutzer_data['name'],
            benutzer_data.get('team_code_verwendet', ''),
            benutzer_data.get('registriert_am', 'NOW()')
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Fehler beim Speichern des Benutzers: {e}")
        return False

def load_projekte_for_user(benutzer_email):
    """Lade Projekte für einen Benutzer"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Team-Code prüfen
        cursor.execute('SELECT team_code_verwendet FROM benutzer WHERE email = %s', (benutzer_email,))
        benutzer_info = cursor.fetchone()
        user_team_code = benutzer_info['team_code_verwendet'] if benutzer_info else None
        
        TEAM_CODE = 'RAUSCH2025'  # Dein Team-Code
        
        if user_team_code == TEAM_CODE:
            # Admin sieht alle Projekte
            cursor.execute('SELECT * FROM projekte ORDER BY erstellt_am DESC')
        else:
            # Normale Benutzer nur ihre eigenen
            cursor.execute('SELECT * FROM projekte WHERE ersteller = %s ORDER BY erstellt_am DESC', (benutzer_email,))
        
        projekte = cursor.fetchall()
        
        # Teilbereiche für jedes Projekt laden
        for projekt in projekte:
            projekt_id = projekt['id']
            
            # Teilbereiche initialisieren
            projekt['teilbereiche'] = {
                'besprechung': {'sitzungen': [], 'gesamt_minuten': 0},
                'zeichnung': {'sitzungen': [], 'gesamt_minuten': 0},
                'aufmass': {'sitzungen': [], 'gesamt_minuten': 0}
            }
            
            # Sitzungen laden
            cursor.execute('''
                SELECT teilbereich, SUM(dauer_minuten) as gesamt_minuten
                FROM sitzungen 
                WHERE projekt_id = %s 
                GROUP BY teilbereich
            ''', (projekt_id,))
            
            teilbereich_summen = cursor.fetchall()
            for summe in teilbereich_summen:
                tb = summe['teilbereich'].lower().strip()
                if tb in projekt['teilbereiche']:
                    projekt['teilbereiche'][tb]['gesamt_minuten'] = summe['gesamt_minuten'] or 0
                elif tb == 'aufmaß':
                    projekt['teilbereiche']['aufmass']['gesamt_minuten'] = summe['gesamt_minuten'] or 0
        
        conn.close()
        return [dict(p) for p in projekte]
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Projekte: {e}")
        return []

def load_mitarbeiter():
    """Lade alle Mitarbeiter"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM mitarbeiter ORDER BY name')
        mitarbeiter = cursor.fetchall()
        conn.close()
        return [m['name'] for m in mitarbeiter]
    except Exception as e:
        print(f"❌ Fehler beim Laden der Mitarbeiter: {e}")
        return []

def load_kunden():
    """Lade alle Kunden"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM kunden ORDER BY name')
        kunden = cursor.fetchall()
        conn.close()
        return [k['name'] for k in kunden]
    except Exception as e:
        print(f"❌ Fehler beim Laden der Kunden: {e}")
        return []