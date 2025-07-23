import json
import os
from datetime import datetime
from database import get_db_connection, init_database

def migrate_json_to_db():
    """Migriert JSON-Daten NUR EINMAL zur PostgreSQL"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # ✅ PRÜFEN OB MIGRATION BEREITS LIEF
        cursor.execute("SELECT COUNT(*) FROM benutzer")
        benutzer_count = cursor.fetchone()['count']
        
        if benutzer_count > 0:
            print("✅ Migration bereits durchgeführt - überspringe...")
            return
        
        print("🚀 Starte Migration von JSON zu PostgreSQL...")
        
        # 1. Datenbank-Tabellen erstellen
        init_database()
        
        # 2. BENUTZER migrieren
        if os.path.exists('benutzer.json'):
            print("📁 Migriere Benutzer...")
            with open('benutzer.json', 'r', encoding='utf-8') as f:
                benutzer_data = json.load(f)
            
            for email, data in benutzer_data.items():
                cursor.execute('''
                    INSERT INTO benutzer (email, password_hash, name, team_code_verwendet, registriert_am)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                ''', (
                    email, 
                    data['password_hash'], 
                    data['name'],
                    data.get('team_code_verwendet'),
                    data['registriert_am']
                ))
            print(f"✅ {len(benutzer_data)} Benutzer migriert")
        
        # 3. MITARBEITER migrieren
        if os.path.exists('mitarbeiter.json'):
            print("👥 Migriere Mitarbeiter...")
            with open('mitarbeiter.json', 'r', encoding='utf-8') as f:
                mitarbeiter_data = json.load(f)
            
            for mitarbeiter in mitarbeiter_data:
                cursor.execute('''
                    INSERT INTO mitarbeiter (name) VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                ''', (mitarbeiter,))
            print(f"✅ {len(mitarbeiter_data)} Mitarbeiter migriert")
        
        # 4. KUNDEN migrieren
        if os.path.exists('kunden.json'):
            print("🏢 Migriere Kunden...")
            with open('kunden.json', 'r', encoding='utf-8') as f:
                kunden_data = json.load(f)
            
            for kunde in kunden_data:
                cursor.execute('''
                    INSERT INTO kunden (name) VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                ''', (kunde,))
            print(f"✅ {len(kunden_data)} Kunden migriert")
        
        # 5. PROJEKTE migrieren
        if os.path.exists('projekte.json'):
            print("📋 Migriere Projekte...")
            with open('projekte.json', 'r', encoding='utf-8') as f:
                projekte_data = json.load(f)
            
            for projekt in projekte_data:
                cursor.execute('''
                    INSERT INTO projekte (id, name, kunde, ersteller, status, erstellt_am, erster_start, letzter_start, beendet_am)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                ''', (
                    projekt['id'],
                    projekt['name'],
                    projekt['kunde'],
                    projekt['ersteller'],
                    projekt['status'],
                    projekt['erstellt_am'],
                    projekt.get('erster_start'),
                    projekt.get('letzter_start'),
                    projekt.get('beendet_am')
                ))
                
                # AKTIVE SITZUNGEN migrieren
                for mitarbeiter, sitzung in projekt.get('aktive_sitzungen', {}).items():
                    cursor.execute('''
                        INSERT INTO aktive_sitzungen (projekt_id, mitarbeiter, teilbereich, start_zeit)
                        VALUES (%s, %s, %s, %s)
                    ''', (
                        projekt['id'],
                        mitarbeiter,
                        sitzung['teilbereich'],
                        sitzung['start']
                    ))
                
                # BEENDETE SITZUNGEN migrieren
                for teilbereich_name, teilbereich_data in projekt.get('teilbereiche', {}).items():
                    for sitzung in teilbereich_data.get('sitzungen', []):
                        cursor.execute('''
                            INSERT INTO sitzungen (projekt_id, mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        ''', (
                            projekt['id'],
                            sitzung['mitarbeiter'],
                            teilbereich_name,
                            sitzung['start'],
                            sitzung['end'],
                            sitzung['dauer_minuten']
                        ))
            
            print(f"✅ {len(projekte_data)} Projekte migriert")
            
            # Auto-increment für Projekte korrekt setzen
            cursor.execute('SELECT MAX(id) FROM projekte')
            max_id_result = cursor.fetchone()
            try:
                max_id = max_id_result['max'] if max_id_result and max_id_result['max'] is not None else 0
                cursor.execute(f'ALTER SEQUENCE projekte_id_seq RESTART WITH {max_id + 1}')
            except (KeyError, TypeError):
                cursor.execute('ALTER SEQUENCE projekte_id_seq RESTART WITH 1')

        # Verifikation
        cursor.execute('SELECT COUNT(*) FROM benutzer')
        benutzer_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) FROM projekte')
        projekte_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) FROM sitzungen')
        sitzungen_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) FROM aktive_sitzungen')
        aktive_count = cursor.fetchone()['count']

        print(f"📊 Migration Ergebnis:")
        print(f"   👤 {benutzer_count} Benutzer")
        print(f"   📋 {projekte_count} Projekte")
        print(f"   ⏱️ {sitzungen_count} beendete Sitzungen")
        print(f"   🔄 {aktive_count} aktive Sitzungen")
        
        conn.commit()
        print("✅ Migration erfolgreich abgeschlossen!")
        
    except Exception as e:
        print(f"❌ Fehler bei Migration: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()