from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps
import time
import hashlib
import secrets
from database import *
import pytz
import json
import os
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, render_template_string
import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Team-Code Definition
TEAM_CODE = 'RAUSCH2025'
TEILBEREICHE = ['besprechung', 'zeichnung', 'aufmass']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'benutzer_email' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def berechne_dauer_text(minuten):
    """Konvertiert Minuten in lesbaren Text"""
    if minuten < 60:
        return f"{minuten}m"

    stunden = minuten // 60
    rest_minuten = minuten % 60

    if stunden < 24:
        return f"{stunden}h {rest_minuten}m" if rest_minuten > 0 else f"{stunden}h"

    tage = stunden // 24
    rest_stunden = stunden % 24

    if tage < 7:
        result = f"{tage} Tag{'e' if tage > 1 else ''}"
        if rest_stunden > 0:
            result += f" {rest_stunden}h"
        if rest_minuten > 0:
            result += f" {rest_minuten}m"
        return result

    wochen = tage // 7
    rest_tage = tage % 7

    result = f"{wochen} Woche{'n' if wochen > 1 else ''}"
    if rest_tage > 0:
        result += f" {rest_tage} Tag{'e' if rest_tage > 1 else ''}"
    if rest_stunden > 0:
        result += f" {rest_stunden}h"
    if rest_minuten > 0:
        result += f" {rest_minuten}m"

    return result
@app.template_filter('german_time')
def german_time_filter(utc_string):
    try:
        utc_time = datetime.fromisoformat(utc_string.replace('Z', '+00:00'))
        german_tz = pytz.timezone('Europe/Berlin')
        german_time = utc_time.astimezone(german_tz)
        return german_time.strftime('%H:%M')
    except:
        return utc_string[11:16]
@app.template_filter('german_date')
def german_date_filter(utc_string):
    """Konvertiert UTC Datum zu deutschem Datum (DD.MM.)"""
    try:
        utc_time = datetime.fromisoformat(utc_string.replace('Z', '+00:00'))
        german_tz = pytz.timezone('Europe/Berlin')
        german_time = utc_time.astimezone(german_tz)
        return german_time.strftime('%d.%m.')
    except:
        if isinstance(utc_string, str) and len(utc_string) > 10:
            return f"{utc_string[8:10]}.{utc_string[5:7]}."
        return "01.01."
os.environ['TZ'] = 'Europe/Berlin'
time.tzset()
def berechne_aktuelle_dauer(start_zeit):
    """Berechnet die aktuelle Dauer einer laufenden Sitzung"""
    try:
        if isinstance(start_zeit, str):
            start = datetime.fromisoformat(start_zeit.replace('Z', '+00:00'))
        else:
            start = start_zeit
        
        jetzt = datetime.now()
        if start.tzinfo is not None:
            jetzt = datetime.now(pytz.UTC)
        
        diff = jetzt - start
        total_minuten = max(0, int(diff.total_seconds() / 60))
        
        stunden = total_minuten // 60
        minuten = total_minuten % 60
        
        return f"{stunden}h {minuten}m"
    except:
        return "0h 0m"

@app.template_filter('aktuelle_dauer')
def aktuelle_dauer_filter(start_zeit):
    return berechne_aktuelle_dauer(start_zeit)
@app.route('/')
def index():
    if 'benutzer_email' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/registrieren', methods=['POST'])
def registrieren():
    email = request.form['email'].strip().lower()
    password = request.form['password']
    team_code = request.form.get('team_code', '').strip()

    if len(password) < 8:
        return jsonify({'status': 'error', 'message': 'Passwort muss mindestens 8 Zeichen haben'})

    benutzer = load_benutzer()
    if email in benutzer:
        return jsonify({'status': 'error', 'message': 'E-Mail bereits registriert'})

    if not team_code:
        return jsonify({'status': 'error', 'message': 'Team-Code ist erforderlich'})

    if team_code != TEAM_CODE:
        return jsonify({'status': 'error', 'message': 'Ungültiger Team-Code'})

    # Benutzer speichern
    benutzer_data = {
        'password_hash': hash_password(password),
        'registriert_am': datetime.now().isoformat(),
        'name': email.split('@')[0].title(),
        'team_code_verwendet': team_code
    }
    
    save_benutzer(email, benutzer_data)

    session['benutzer_email'] = email
    session['benutzer_name'] = benutzer_data['name']

    return jsonify({
        'status': 'success',
        'sofort_zugriff': True,
        'message': 'Willkommen im Team!'
    })

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip().lower()
    password = request.form['password']

    benutzer = load_benutzer()
    if email not in benutzer or benutzer[email]['password_hash'] != hash_password(password):
        return jsonify({'status': 'error', 'message': 'Ungültige Anmeldedaten'})

    session['benutzer_email'] = email
    session['benutzer_name'] = benutzer[email]['name']
    return jsonify({'status': 'success'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
@login_required
def dashboard():
    projekte = load_projekte_for_user(session['benutzer_email'])
    mitarbeiter = load_mitarbeiter()
    kunden = load_kunden()

    return render_template('dashboard.html',
                         projekte=projekte,
                         teilbereiche=TEILBEREICHE,
                         mitarbeiter=mitarbeiter,
                         kunden=kunden,
                         benutzer_name=session['benutzer_name'])

@app.route('/projekt/neu', methods=['POST'])
@login_required
def neues_projekt():
    name = request.form['name'].strip()
    kunde = request.form['kunde'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Projektname erforderlich'})
    if not kunde:
        return jsonify({'status': 'error', 'message': 'Kunde erforderlich'})

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO projekte (name, kunde, ersteller, status, erstellt_am)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', (name, kunde, session['benutzer_email'], 'gestoppt', datetime.now().isoformat()))
    
    projekt_id = cursor.fetchone()['id']
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'projekt_id': projekt_id})

@app.route('/projekt/<int:projekt_id>')
@login_required
def projekt_details(projekt_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projekte WHERE id = %s', (projekt_id,))
    projekt_row = cursor.fetchone()
    
    if not projekt_row:
        conn.close()
        return "Projekt nicht gefunden", 404

    projekt = dict(projekt_row)
    
    # Team-Berechtigung prüfen
    benutzer_email = session['benutzer_email']
    cursor.execute('SELECT team_code_verwendet FROM benutzer WHERE email = %s', (benutzer_email,))
    benutzer_info = cursor.fetchone()
    user_team_code = benutzer_info['team_code_verwendet'] if benutzer_info else None
    
    if user_team_code == TEAM_CODE:
        pass  # Team-Mitglied hat Zugriff
    elif projekt['ersteller'] == benutzer_email:
        pass  # Eigenes Projekt
    else:
        conn.close()
        return "Keine Berechtigung für dieses Projekt", 403

    # Aktive Sitzungen laden
    cursor.execute('''
        SELECT mitarbeiter, teilbereich, start_zeit 
        FROM aktive_sitzungen 
        WHERE projekt_id = %s
    ''', (projekt_id,))
    
    aktive_sitzungen = {}
    for sitzung in cursor.fetchall():
        # Start-Zeit korrekt für JavaScript formatieren
        start_zeit = sitzung['start_zeit']
        if isinstance(start_zeit, datetime):
            if start_zeit.tzinfo is None:
                # Keine Timezone = UTC annehmen
                start_zeit = pytz.UTC.localize(start_zeit)
            start_iso = start_zeit.isoformat()
        else:
            # String-Format zu ISO mit Z-Suffix
            start_iso = str(start_zeit).replace(' ', 'T') + 'Z'

        aktive_sitzungen[sitzung['mitarbeiter']] = {
            'teilbereich': sitzung['teilbereich'],
            'start': start_iso,
            'dauer': berechne_aktuelle_dauer(sitzung['start_zeit'])
        }
    
    projekt['aktive_sitzungen'] = aktive_sitzungen
    
    # Teilbereiche laden
    teilbereiche = {}
    for tb in TEILBEREICHE:
        cursor.execute('''
            SELECT mitarbeiter, start_zeit, end_zeit, dauer_minuten 
            FROM sitzungen 
            WHERE projekt_id = %s AND teilbereich = %s
            ORDER BY start_zeit DESC
        ''', (projekt_id, tb))
        
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
    
    # Datumskonvertierung
    if projekt['erstellt_am']:
        projekt['erstellt_am'] = projekt['erstellt_am'].isoformat()
    if projekt['beendet_am']:
        projekt['beendet_am'] = projekt['beendet_am'].isoformat()
    
    conn.close()
    
    mitarbeiter = load_mitarbeiter()
    return render_template('projekt_details.html',
                         projekt=projekt,
                         teilbereiche=TEILBEREICHE,
                         mitarbeiter=mitarbeiter,
                         benutzer_name=session['benutzer_name'])
@app.route('/projekt/<int:projekt_id>/aktivität/starten', methods=['POST'])
@login_required
def aktivität_starten(projekt_id):
    mitarbeiter = request.form['mitarbeiter']
    teilbereich = request.form['teilbereich']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Prüfen ob Mitarbeiter bereits aktiv
    cursor.execute('SELECT id FROM aktive_sitzungen WHERE projekt_id = %s AND mitarbeiter = %s', 
                   (projekt_id, mitarbeiter))
    if cursor.fetchone():
        conn.close()
        return jsonify({'status': 'error', 'message': f'{mitarbeiter} arbeitet bereits'})

    jetzt = datetime.now(pytz.UTC)
    
    # Aktive Sitzung einfügen
    cursor.execute('''
        INSERT INTO aktive_sitzungen (projekt_id, mitarbeiter, teilbereich, start_zeit)
        VALUES (%s, %s, %s, %s)
    ''', (projekt_id, mitarbeiter, teilbereich, jetzt))
    
    # Projekt-Status auf laufend setzen
    cursor.execute('''
        UPDATE projekte 
        SET status = 'laufend', letzter_start = %s
        WHERE id = %s
    ''', (jetzt, projekt_id))
    
    # Erster Start setzen falls noch nicht gesetzt
    cursor.execute('''
        UPDATE projekte 
        SET erster_start = %s
        WHERE id = %s AND erster_start IS NULL
    ''', (jetzt, projekt_id))
    
    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})


@app.route('/projekt/<int:projekt_id>/aktivität/beenden', methods=['POST'])
@login_required
def aktivität_beenden(projekt_id):
    try:
        print(f"Beende Aktivität für Projekt {projekt_id}")
        
        # Mitarbeiter aus Form holen
        mitarbeiter = request.form.get('mitarbeiter')
        if not mitarbeiter:
            return jsonify({'status': 'error', 'message': 'Mitarbeiter fehlt'})
        
        print(f"Mitarbeiter: {mitarbeiter}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Aktive Sitzung finden
        cursor.execute('''
            SELECT teilbereich, start_zeit FROM aktive_sitzungen 
            WHERE projekt_id = %s AND mitarbeiter = %s
        ''', (projekt_id, mitarbeiter))
        
        aktive_sitzung = cursor.fetchone()
        print(f"Aktive Sitzung gefunden: {aktive_sitzung}")
        
        if not aktive_sitzung:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Keine aktive Sitzung gefunden'})

        # Jetzige Zeit
        end_zeit = datetime.now(pytz.UTC)
        start_zeit = aktive_sitzung['start_zeit']
        
        print(f"Start: {start_zeit}, End: {end_zeit}")
        
        # Timezone handling
        if isinstance(start_zeit, str):
            start_zeit = datetime.fromisoformat(start_zeit.replace('Z', '+00:00'))
        elif start_zeit.tzinfo is None:
            start_zeit = pytz.UTC.localize(start_zeit)
        
        # Dauer berechnen
        time_diff = end_zeit - start_zeit
        dauer_minuten = max(1, int(time_diff.total_seconds() / 60))
        
        print(f"Dauer: {dauer_minuten} Minuten")

        # Sitzung in beendete Sitzungen einfügen
        cursor.execute('''
            INSERT INTO sitzungen (projekt_id, mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (projekt_id, mitarbeiter, aktive_sitzung['teilbereich'], 
              start_zeit, end_zeit, dauer_minuten))
        
        print("Sitzung in DB eingefügt")
        
        # Aktive Sitzung löschen
        cursor.execute('''
            DELETE FROM aktive_sitzungen 
            WHERE projekt_id = %s AND mitarbeiter = %s
        ''', (projekt_id, mitarbeiter))
        
        deleted_rows = cursor.rowcount
        print(f"Aktive Sitzungen gelöscht: {deleted_rows}")
        
        # Prüfen ob noch aktive Sitzungen vorhanden - FIXED
        cursor.execute('SELECT COUNT(*) as count FROM aktive_sitzungen WHERE projekt_id = %s', (projekt_id,))
        result = cursor.fetchone()
        aktive_count = result['count'] if result else 0
        print(f"Verbleibende aktive Sitzungen: {aktive_count}")
        
        if aktive_count == 0:
            cursor.execute('UPDATE projekte SET status = %s WHERE id = %s', ('pausiert', projekt_id))
            print("Projekt-Status auf 'pausiert' gesetzt")
        
        conn.commit()
        conn.close()
        
        # Dauer-Text erstellen
        stunden = dauer_minuten // 60
        minuten = dauer_minuten % 60
        if stunden > 0:
            dauer_text = f"{stunden}h {minuten}m"
        else:
            dauer_text = f"{minuten}m"

        print(f"Erfolgreich beendet: {dauer_text}")
        
        return jsonify({
            'status': 'success',
            'message': 'Aktivität beendet',
            'dauer_text': dauer_text,
            'dauer_minuten': dauer_minuten
        })
        
    except Exception as e:
        print(f"FEHLER in aktivität_beenden: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass
                
        return jsonify({
            'status': 'error', 
            'message': f'Server-Fehler: {str(e)}',
            'error_type': type(e).__name__
        })

@app.route('/projekte/<int:projekt_id>/beenden', methods=['POST'])
@login_required
def projekt_beenden(projekt_id):
    try:
        print(f"🏁 BEENDEN-REQUEST für Projekt ID: {projekt_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Erst prüfen ob Projekt existiert und Namen holen
        cursor.execute('SELECT id, name, status FROM projekte WHERE id = %s', (projekt_id,))
        projekt_row = cursor.fetchone()
        
        if not projekt_row:
            conn.close()
            return jsonify({
                'status': 'error', 
                'message': f'Projekt {projekt_id} nicht gefunden'
            }), 404
        
        # ✅ SICHERER ZUGRIFF AUF PROJEKT-DATEN
        projekt = dict(projekt_row)
        projekt_name = projekt['name']
        
        print(f"📋 Gefundenes Projekt: {projekt}")
        
        # Alle aktiven Sitzungen für dieses Projekt beenden
        cursor.execute('SELECT COUNT(*) as count FROM aktive_sitzungen WHERE projekt_id = %s', (projekt_id,))
        aktive_count = cursor.fetchone()['count']
        
        if aktive_count > 0:
            print(f"⚠️ Beende {aktive_count} aktive Sitzungen")
            cursor.execute('DELETE FROM aktive_sitzungen WHERE projekt_id = %s', (projekt_id,))
        
        # Status auf 'beendet' setzen
        cursor.execute(
            'UPDATE projekte SET status = %s, beendet_am = %s WHERE id = %s', 
            ('beendet', datetime.now().isoformat(), projekt_id)
        )
        
        affected_rows = cursor.rowcount
        print(f"📝 Betroffene Zeilen: {affected_rows}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Projekt {projekt_id} erfolgreich beendet")
        
        return jsonify({
            'status': 'success',
            'message': f'Projekt "{projekt_name}" wurde beendet'
        })
        
    except Exception as e:
        print(f"❌ FEHLER beim Beenden von Projekt {projekt_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if 'conn' in locals():
            try:
                conn.close()
            except:
                pass
        
        return jsonify({
            'status': 'error',
            'message': f'Server-Fehler: {str(e)}'
        }), 500
    

@app.route('/mitarbeiter/hinzufügen', methods=['POST'])
@login_required
def mitarbeiter_hinzufügen():
    name = request.form['name'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name ist erforderlich'})

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO mitarbeiter (name) VALUES (%s)', (name,))
        conn.commit()
        return jsonify({'status': 'success'})
    except:
        return jsonify({'status': 'error', 'message': 'Mitarbeiter existiert bereits'})
    finally:
        conn.close()

@app.route('/mitarbeiter/löschen', methods=['POST'])
@login_required
def mitarbeiter_löschen():
    name = request.form['name']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM mitarbeiter WHERE name = %s', (name,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/kunde/hinzufügen', methods=['POST'])
@login_required
def kunde_hinzufügen():
    name = request.form['name'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name ist erforderlich'})

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO kunden (name) VALUES (%s)', (name,))
        conn.commit()
        return jsonify({'status': 'success'})
    except:
        return jsonify({'status': 'error', 'message': 'Kunde existiert bereits'})
    finally:
        conn.close()

@app.route('/kunde/löschen', methods=['POST'])
@login_required
def kunde_löschen():
    name = request.form['name']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM kunden WHERE name = %s', (name,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/projekte/löschen', methods=['POST'])
@login_required
def projekte_löschen():
    projekt_ids = request.json.get('projekt_ids', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for projekt_id in projekt_ids:
        cursor.execute('DELETE FROM projekte WHERE id = %s', (projekt_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})
@app.route('/export/vorschau', methods=['POST'])
@login_required
def export_vorschau():
    try:
        # Parameter aus Form holen
        von_datum_str = request.form.get('von_datum', '')
        bis_datum_str = request.form.get('bis_datum', '')
        format_type = request.form.get('format', 'pdf')
        
        print(f"Export-Vorschau Request: von={von_datum_str}, bis={bis_datum_str}, format={format_type}")
        
        # Validierung der Eingaben
        if not von_datum_str or not bis_datum_str:
            return jsonify({
                'status': 'error',
                'message': 'Von- und Bis-Datum sind erforderlich'
            })
        
        # Datum parsen - mehrere Formate unterstützen
        def parse_date(date_str):
            formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Ungültiges Datumsformat: {date_str}")
        
        try:
            von_datum = parse_date(von_datum_str)
            bis_datum = parse_date(bis_datum_str)
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            })
        
        # Bis-Datum bis Ende des Tages setzen
        bis_datum = bis_datum.replace(hour=23, minute=59, second=59)
        
        # Validierung: Von-Datum nicht nach Bis-Datum
        if von_datum > bis_datum:
            return jsonify({
                'status': 'error',
                'message': 'Von-Datum darf nicht nach Bis-Datum liegen'
            })
        
        # Datenbank-Verbindung
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Benutzer-Berechtigung prüfen
        benutzer_email = session.get('benutzer_email')
        if not benutzer_email:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Nicht angemeldet'
            })
        
        cursor.execute('SELECT team_code_verwendet FROM benutzer WHERE email = %s', (benutzer_email,))
        benutzer_info = cursor.fetchone()
        user_team_code = benutzer_info['team_code_verwendet'] if benutzer_info else None
        
        # Team-Code definieren (falls nicht vorhanden)
        TEAM_CODE = "MASTER2024"  # Passen Sie dies an Ihren Code an
        
        # Projekte mit Sitzungen im Zeitraum laden
        if user_team_code == TEAM_CODE:
            # Admin kann alle Projekte sehen
            projekte_query = '''
                SELECT DISTINCT p.* FROM projekte p 
                JOIN sitzungen s ON p.id = s.projekt_id 
                WHERE s.start_zeit >= %s AND s.start_zeit <= %s
                ORDER BY p.name
            '''
            cursor.execute(projekte_query, (von_datum, bis_datum))
        else:
            # Normale Benutzer nur ihre eigenen Projekte
            projekte_query = '''
                SELECT DISTINCT p.* FROM projekte p 
                JOIN sitzungen s ON p.id = s.projekt_id 
                WHERE p.ersteller = %s AND s.start_zeit >= %s AND s.start_zeit <= %s
                ORDER BY p.name
            '''
            cursor.execute(projekte_query, (benutzer_email, von_datum, bis_datum))
        
        projekte_rows = cursor.fetchall()
        projekte_data = []
        gesamt_minuten_periode = 0
        
        for projekt_row in projekte_rows:
            projekt = dict(projekt_row)
            
            # Sitzungen für dieses Projekt im Zeitraum laden
            cursor.execute('''
                SELECT mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten 
                FROM sitzungen 
                WHERE projekt_id = %s AND start_zeit >= %s AND start_zeit <= %s
                AND end_zeit IS NOT NULL
                ORDER BY start_zeit ASC
            ''', (projekt['id'], von_datum, bis_datum))
            
            sitzungen = cursor.fetchall()
            
            if not sitzungen:  # Überspringen wenn keine abgeschlossenen Sitzungen
                continue
            
            # Daten nach Mitarbeiter gruppieren
            mitarbeiter_stats = {}
            gesamt_minuten_projekt = 0
            
            for sitzung in sitzungen:
                mitarbeiter = sitzung['mitarbeiter']
                teilbereich = sitzung['teilbereich']
                minuten = sitzung['dauer_minuten'] or 0
                
                if mitarbeiter not in mitarbeiter_stats:
                    mitarbeiter_stats[mitarbeiter] = {
                        'besprechung': 0,
                        'zeichnung': 0,
                        'aufmass': 0,
                        'gesamt': 0
                    }
                
                mitarbeiter_stats[mitarbeiter][teilbereich] += minuten
                mitarbeiter_stats[mitarbeiter]['gesamt'] += minuten
                gesamt_minuten_projekt += minuten
            
            projekt_dict = {
                'id': projekt['id'],
                'name': projekt['name'],
                'kunde': projekt['kunde'],
                'mitarbeiter_stats': mitarbeiter_stats,
                'gesamt_minuten': gesamt_minuten_projekt
            }
            
            projekte_data.append(projekt_dict)
            gesamt_minuten_periode += gesamt_minuten_projekt
        
        conn.close()
        
        # Erfolgreiche Response zurückgeben
        return jsonify({
            'status': 'success',
            'projekte': projekte_data,
            'gesamt_minuten': gesamt_minuten_periode,
            'anzahl_projekte': len(projekte_data),
            'von_datum': von_datum_str,
            'bis_datum': bis_datum_str,
            'format': format_type,
            'zeitraum_text': f"{von_datum.strftime('%d.%m.%Y')} bis {bis_datum.strftime('%d.%m.%Y')}"
        })
        
    except Exception as e:
        print(f"Fehler bei Export-Vorschau: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error', 
            'message': f'Server-Fehler: {str(e)}'
        })
@app.route('/projekt/<int:projekt_id>/bericht')
@login_required
def projekt_bericht(projekt_id):
    try:
        print(f"📊 Bericht für Projekt {projekt_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ PROJEKT-DETAILS HOLEN
        cursor.execute('SELECT id, name, kunde, status, erstellt_am, beendet_am FROM projekte WHERE id = %s', (projekt_id,))
        projekt_row = cursor.fetchone()
        
        if not projekt_row:
            conn.close()
            return "Projekt nicht gefunden", 404
        
        projekt = dict(projekt_row)
        print(f"📋 Projekt gefunden: {projekt['name']}")
        
        # ✅ ALLE SITZUNGEN FÜR DIESES PROJEKT
        cursor.execute('''
            SELECT mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten
            FROM sitzungen 
            WHERE projekt_id = %s
            ORDER BY start_zeit ASC
        ''', (projekt_id,))
        
        sitzungen = cursor.fetchall()
        print(f"📊 {len(sitzungen)} Sitzungen gefunden")
        
        # ✅ DATEN AUFBEREITEN
        mitarbeiter_stats = {}
        teilbereiche_gesamt = {
            'besprechung': {'gesamt_minuten': 0, 'anzahl_sitzungen': 0},
            'zeichnung': {'gesamt_minuten': 0, 'anzahl_sitzungen': 0},
            'aufmass': {'gesamt_minuten': 0, 'anzahl_sitzungen': 0}
        }
        
        gesamt_minuten = 0
        start_datum = None
        end_datum = None
        
        for sitzung in sitzungen:
            mitarbeiter = sitzung['mitarbeiter']
            teilbereich = sitzung['teilbereich'].lower().strip()
            minuten = sitzung['dauer_minuten'] or 0
            
            # Datum tracking
            if sitzung['start_zeit']:
                if start_datum is None or sitzung['start_zeit'] < start_datum:
                    start_datum = sitzung['start_zeit']
                if end_datum is None or sitzung['start_zeit'] > end_datum:
                    end_datum = sitzung['start_zeit']
            
            # Mitarbeiter initialisieren
            if mitarbeiter not in mitarbeiter_stats:
                mitarbeiter_stats[mitarbeiter] = {
                    'besprechung': 0,
                    'zeichnung': 0,
                    'aufmass': 0,
                    'gesamt': 0,
                    'sitzungen': 0
                }
            
            # Teilbereich zuordnen
            if teilbereich in ['besprechung', 'zeichnung', 'aufmass']:
                mitarbeiter_stats[mitarbeiter][teilbereich] += minuten
                mitarbeiter_stats[mitarbeiter]['gesamt'] += minuten
                mitarbeiter_stats[mitarbeiter]['sitzungen'] += 1
                
                teilbereiche_gesamt[teilbereich]['gesamt_minuten'] += minuten
                teilbereiche_gesamt[teilbereich]['anzahl_sitzungen'] += 1
                
            elif teilbereich == 'aufmaß':
                mitarbeiter_stats[mitarbeiter]['aufmass'] += minuten
                mitarbeiter_stats[mitarbeiter]['gesamt'] += minuten
                mitarbeiter_stats[mitarbeiter]['sitzungen'] += 1
                
                teilbereiche_gesamt['aufmass']['gesamt_minuten'] += minuten
                teilbereiche_gesamt['aufmass']['anzahl_sitzungen'] += 1
            
            gesamt_minuten += minuten
        
        # ✅ ZEIT FORMATIERUNG
        def format_minuten(minuten):
            if minuten < 60:
                return f"{minuten}min"
            stunden = minuten // 60
            rest_min = minuten % 60
            if rest_min == 0:
                return f"{stunden}h"
            return f"{stunden}h {rest_min}min"
        
        # ✅ KALENDERTAGE BERECHNEN
        kalendertage = 0
        if start_datum and end_datum:
            try:
                if isinstance(start_datum, str):
                    start_dt = datetime.fromisoformat(start_datum.replace('Z', '+00:00'))
                else:
                    start_dt = start_datum
                
                if isinstance(end_datum, str):
                    end_dt = datetime.fromisoformat(end_datum.replace('Z', '+00:00'))
                else:
                    end_dt = end_datum
                
                kalendertage = (end_dt.date() - start_dt.date()).days + 1
            except:
                kalendertage = 1
        
        # ✅ MITARBEITER DATEN FORMATIEREN
        mitarbeiter_formatted = {}
        for name, stats in mitarbeiter_stats.items():
            mitarbeiter_formatted[name] = {
                'gesamt_zeit': format_minuten(stats['gesamt']),
                'teilbereiche': {
                    'besprechung': format_minuten(stats['besprechung']),
                    'zeichnung': format_minuten(stats['zeichnung']),
                    'aufmass': format_minuten(stats['aufmass'])
                }
            }
        
        # ✅ BERICHT-DATEN STRUKTUR
        bericht_data = {
            'projekt_name': projekt['name'],
            'gesamt_arbeitszeit': format_minuten(gesamt_minuten),
            'kalendertage': kalendertage,
            'mitarbeiter': mitarbeiter_formatted,
            'teilbereiche': teilbereiche_gesamt
        }
        
        conn.close()
        
        print(f"✅ Bericht erstellt: {gesamt_minuten} min, {len(mitarbeiter_stats)} Mitarbeiter")
        
        # ✅ TEMPLATE RENDERN
        return render_template('bericht.html', 
                             projekt=projekt,
                             bericht=bericht_data)
        
    except Exception as e:
        print(f"❌ Fehler beim Bericht: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Fehler beim Laden des Berichts</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", 500
    
@app.route('/export/vollbericht')
@login_required
def export_vollbericht():
    try:
        von_datum_str = request.args.get('von', '')
        bis_datum_str = request.args.get('bis', '')
        
        print(f"📊 Vollbericht: {von_datum_str} bis {bis_datum_str}")
        
        if not von_datum_str or not bis_datum_str:
            return "<h1>❌ Von- und Bis-Datum erforderlich</h1>", 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ ALLE BEENDETEN PROJEKTE IM ZEITRAUM
        cursor.execute('''
            SELECT id, name, kunde, status, beendet_am
            FROM projekte 
            WHERE status = 'beendet' 
            AND beendet_am IS NOT NULL
            AND DATE(beendet_am) BETWEEN %s AND %s
            ORDER BY beendet_am DESC
        ''', (von_datum_str, bis_datum_str))
        
        projekte_rows = cursor.fetchall()
        projekte_data = []
        gesamt_minuten_alle = 0
        
        print(f"🔍 Gefundene beendete Projekte: {len(projekte_rows)}")
        
        for projekt_row in projekte_rows:
            projekt = dict(projekt_row)
            projekt_id = projekt['id']
            
            print(f"📋 Bearbeite Projekt: {projekt['name']}")
            
            # ✅ DETAILLIERTE SITZUNGEN FÜR DIESES PROJEKT
            cursor.execute('''
                SELECT mitarbeiter, teilbereich, dauer_minuten, start_zeit
                FROM sitzungen 
                WHERE projekt_id = %s
                ORDER BY start_zeit
            ''', (projekt_id,))
            
            sitzungen = cursor.fetchall()
            
            # ✅ MITARBEITER-DATEN AUFBAUEN (wie beim einzelnen Bericht)
            mitarbeiter_data = {}
            projekt_gesamt = 0
            
            for sitzung in sitzungen:
                ma = sitzung['mitarbeiter']
                tb = sitzung['teilbereich'].lower().strip()
                minuten = sitzung['dauer_minuten'] or 0
                
                if ma not in mitarbeiter_data:
                    mitarbeiter_data[ma] = {
                        'besprechung': 0,
                        'zeichnung': 0,
                        'aufmass': 0,
                        'gesamt': 0
                    }
                
                # Teilbereich zuordnen
                if tb in ['besprechung', 'zeichnung', 'aufmass']:
                    mitarbeiter_data[ma][tb] += minuten
                elif tb == 'aufmaß':
                    mitarbeiter_data[ma]['aufmass'] += minuten
                
                mitarbeiter_data[ma]['gesamt'] += minuten
                projekt_gesamt += minuten
            
            gesamt_minuten_alle += projekt_gesamt
            
            # Beendet-am Datum formatieren
            beendet_am = ""
            if projekt['beendet_am']:
                try:
                    if isinstance(projekt['beendet_am'], str):
                        beendet_datum = datetime.fromisoformat(projekt['beendet_am'].replace('Z', '+00:00'))
                    else:
                        beendet_datum = projekt['beendet_am']
                    beendet_am = beendet_datum.strftime('%d.%m.%Y')
                except:
                    beendet_am = str(projekt['beendet_am'])[:10]
            
            projekte_data.append({
                'id': projekt_id,
                'name': projekt['name'],
                'kunde': projekt['kunde'],
                'beendet_am': beendet_am,
                'mitarbeiter_data': mitarbeiter_data,
                'gesamt_minuten': projekt_gesamt
            })
        
        conn.close()
        
        # Zeitraum formatieren
        try:
            von_datum = datetime.strptime(von_datum_str, '%Y-%m-%d')
            bis_datum = datetime.strptime(bis_datum_str, '%Y-%m-%d')
            von_formatted = von_datum.strftime('%d.%m.%Y')
            bis_formatted = bis_datum.strftime('%d.%m.%Y')
            zeitraum_text = f"{von_formatted} bis {bis_formatted}"
        except:
            zeitraum_text = f"{von_datum_str} bis {bis_datum_str}"
        
        print(f"✅ {len(projekte_data)} Projekte, {gesamt_minuten_alle} Minuten")
        
        # ✅ VOLLSTÄNDIGES HTML MIT MITARBEITER-DETAILS
        html_content = f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAUSCH - Gesamt-Bericht {zeitraum_text}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
            font-size: 14px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #007bff;
        }}
        .main-title {{
            font-size: 2.2em;
            color: #333;
            margin-bottom: 10px;
        }}
        .zeitraum {{
            font-size: 1.3em;
            color: #666;
            margin-bottom: 15px;
        }}
        .gesamt-stats {{
            background: #007bff;
            color: white;
            padding: 15px 25px;
            border-radius: 25px;
            display: inline-block;
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .projekt-container {{
            margin: 30px 0;
            border: 2px solid #ddd;
            border-radius: 12px;
            overflow: hidden;
            background: #f9f9f9;
        }}
        .projekt-header {{
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .projekt-info {{
            flex: 1;
        }}
        .projekt-name {{
            font-size: 1.4em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .projekt-details {{
            font-size: 1em;
            opacity: 0.9;
        }}
        .projekt-gesamt {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.1em;
            backdrop-filter: blur(10px);
        }}
        
        .mitarbeiter-section {{
            padding: 20px;
        }}
        .mitarbeiter-title {{
            font-size: 1.2em;
            color: #333;
            margin-bottom: 20px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .mitarbeiter-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .mitarbeiter-card {{
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }}
        .mitarbeiter-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #007bff;
        }}
        .mitarbeiter-name {{
            font-size: 1.1em;
            font-weight: bold;
            color: #333;
        }}
        .mitarbeiter-total {{
            background: #28a745;
            color: white;
            padding: 6px 12px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        .teilbereiche {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }}
        .teilbereich {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-left: 4px solid #007bff;
            padding: 10px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .teilbereich-name {{
            font-weight: bold;
            color: #495057;
            font-size: 0.9em;
        }}
        .teilbereich-zeit {{
            color: #007bff;
            font-weight: bold;
        }}
        
        .buttons {{
            text-align: center;
            margin-top: 40px;
            padding-top: 30px;
            border-top: 2px solid #ddd;
        }}
        .btn {{
            padding: 15px 30px;
            margin: 0 15px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s;
        }}
        .btn-print {{
            background: #28a745;
            color: white;
        }}
        .btn-print:hover {{
            background: #218838;
            transform: translateY(-2px);
        }}
        .btn-back {{
            background: #6c757d;
            color: white;
        }}
        .btn-back:hover {{
            background: #545b62;
            transform: translateY(-2px);
        }}
        
        @media (max-width: 768px) {{
            .projekt-header {{
                flex-direction: column;
                text-align: center;
            }}
            .mitarbeiter-grid {{
                grid-template-columns: 1fr;
            }}
            .buttons {{
                display: flex;
                flex-direction: column;
                gap: 15px;
                align-items: center;
            }}
            .btn {{
                width: 250px;
            }}
        }}
        
        @media print {{
            .buttons {{ display: none !important; }}
            body {{ background: white !important; padding: 10px !important; font-size: 12px !important; }}
            .container {{ box-shadow: none !important; padding: 20px !important; }}
            .projekt-container {{ page-break-inside: avoid; margin: 20px 0 !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="main-title">📊 RAUSCH Gesamt-Bericht</div>
            <div class="zeitraum">📅 Zeitraum: {zeitraum_text}</div>
            <div class="gesamt-stats">
                🏗️ {len(projekte_data)} Projekt(e) | ⏱️ {gesamt_minuten_alle // 60}h {gesamt_minuten_alle % 60}min gesamt
            </div>
        </div>
        
        <div class="projekte-section">'''
        
        if projekte_data:
            for projekt in projekte_data:
                html_content += f'''
            <div class="projekt-container">
                <div class="projekt-header">
                    <div class="projekt-info">
                        <div class="projekt-name">{projekt['name']}</div>
                        <div class="projekt-details">👤 {projekt['kunde']} | 📅 Beendet: {projekt['beendet_am']}</div>
                    </div>
                    <div class="projekt-gesamt">
                        ⏱️ {projekt['gesamt_minuten'] // 60}h {projekt['gesamt_minuten'] % 60}min
                    </div>
                </div>
                
                <div class="mitarbeiter-section">
                    <div class="mitarbeiter-title">👥 Mitarbeiter-Details ({len(projekt['mitarbeiter_data'])})</div>'''
                
                if projekt['mitarbeiter_data']:
                    html_content += '<div class="mitarbeiter-grid">'
                    
                    for ma_name, ma_data in projekt['mitarbeiter_data'].items():
                        html_content += f'''
                        <div class="mitarbeiter-card">
                            <div class="mitarbeiter-header">
                                <div class="mitarbeiter-name">👤 {ma_name}</div>
                                <div class="mitarbeiter-total">{ma_data['gesamt'] // 60}h {ma_data['gesamt'] % 60}min</div>
                            </div>
                            <div class="teilbereiche">
                                <div class="teilbereich">
                                    <div class="teilbereich-name">💬 Besprechung</div>
                                    <div class="teilbereich-zeit">{ma_data['besprechung']}min</div>
                                </div>
                                <div class="teilbereich">
                                    <div class="teilbereich-name">📐 Zeichnung</div>
                                    <div class="teilbereich-zeit">{ma_data['zeichnung']}min</div>
                                </div>
                                <div class="teilbereich">
                                    <div class="teilbereich-name">📏 Aufmaß</div>
                                    <div class="teilbereich-zeit">{ma_data['aufmass']}min</div>
                                </div>
                            </div>
                        </div>'''
                    
                    html_content += '</div>'
                else:
                    html_content += '''
                    <div style="text-align: center; padding: 20px; color: #666; font-style: italic;">
                        📭 Keine Mitarbeiter-Daten für dieses Projekt
                    </div>'''
                
                html_content += '''
                </div>
            </div>'''
        else:
            html_content += '''
            <div style="text-align: center; padding: 60px; color: #666;">
                <h3>📭 Keine beendeten Projekte im gewählten Zeitraum</h3>
            </div>'''
        
        html_content += '''
        </div>
        
        <div class="buttons">
            <button onclick="window.print()" class="btn btn-print">🖨️ Drucken</button>
            <button onclick="window.close()" class="btn btn-back">← Schließen</button>
        </div>
    </div>
</body>
</html>'''
        
        return html_content
        
    except Exception as e:
        print(f"❌ Fehler in vollbericht: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>❌ Fehler: {str(e)}</h1><pre>{traceback.format_exc()}</pre>", 500
    
@app.route('/projekte/bulk-delete', methods=['POST'])
@login_required
def projekte_bulk_delete():
    try:
        data = request.get_json()
        projekt_ids = data.get('projekt_ids', [])
        
        if not projekt_ids:
            return jsonify({'status': 'error', 'message': 'Keine Projekte ausgewählt'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        deleted_count = 0
        for projekt_id in projekt_ids:
            cursor.execute('DELETE FROM aktive_sitzungen WHERE projekt_id = %s', (projekt_id,))
            cursor.execute('DELETE FROM sitzungen WHERE projekt_id = %s', (projekt_id,))
            cursor.execute('DELETE FROM projekte WHERE id = %s', (projekt_id,))
            
            if cursor.rowcount > 0:
                deleted_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)