#!/usr/bin/env python3
"""
Einfache Migration ohne init_database Import
"""
import os
import sys

print("🚀 Migration gestartet...")

try:
    # Nur get_db_connection importieren
    from database import get_db_connection
    
    print("✅ Database-Modul importiert")
    
    # Verbindung testen
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("✅ Datenbank-Verbindung erfolgreich!")
    
    # Einfache Tabellen-Prüfung
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    
    tabellen_count = cursor.fetchone()[0]
    print(f"📋 Gefundene Tabellen: {tabellen_count}")
    
    # Wenn keine Tabellen, erstelle Basis-Struktur
    if tabellen_count == 0:
        print("🔧 Erstelle Basis-Tabellen...")
        
        # Nur die wichtigsten Tabellen erstellen
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projekte (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                kunde VARCHAR(255) NOT NULL,
                ersteller VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'gestoppt',
                erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sitzungen (
                id SERIAL PRIMARY KEY,
                projekt_id INTEGER REFERENCES projekte(id),
                mitarbeiter VARCHAR(255) NOT NULL,
                teilbereich VARCHAR(100) NOT NULL,
                start_zeit TIMESTAMP NOT NULL,
                end_zeit TIMESTAMP,
                dauer_minuten INTEGER
            )
        ''')
        
        conn.commit()
        print("✅ Basis-Tabellen erstellt!")
    
    conn.close()
    print("✅ Migration erfolgreich abgeschlossen!")
    
except Exception as e:
    print(f"❌ Migration fehlgeschlagen: {e}")
    print(f"❌ Fehler-Typ: {type(e).__name__}")
    # Nicht mit exit(1) beenden - das crasht Railway
    print("⚠️  Fahre trotzdem mit App-Start fort...")

print("🎯 Migration beendet - App kann starten")