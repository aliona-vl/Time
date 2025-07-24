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
    @app.route('/projekt/<int:projekt_id>/beenden', methods=['POST'])
@login_required
def projekt_beenden(projekt_id):
    """Projekt manuell beenden"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Alle aktiven Sitzungen für dieses Projekt beenden
        cursor.execute('''
            SELECT mitarbeiter, teilbereich, start_zeit 
            FROM aktive_sitzungen 
            WHERE projekt_id = %s
        ''', (projekt_id,))
        
        aktive_sitzungen = cursor.fetchall()
        
        # Jede aktive Sitzung beenden
        for sitzung in aktive_sitzungen:
            end_zeit = datetime.now(pytz.UTC)
            start_zeit = sitzung['start_zeit']
            
            if isinstance(start_zeit, str):
                start_zeit = datetime.fromisoformat(start_zeit.replace('Z', '+00:00'))
            elif start_zeit.tzinfo is None:
                start_zeit = pytz.UTC.localize(start_zeit)
            
            time_diff = end_zeit - start_zeit
            dauer_minuten = max(1, int(time_diff.total_seconds() / 60))
            
            # Sitzung speichern
            cursor.execute('''
                INSERT INTO sitzungen (projekt_id, mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (projekt_id, sitzung['mitarbeiter'], sitzung['teilbereich'], 
                  start_zeit, end_zeit, dauer_minuten))
        
        # Aktive Sitzungen löschen
        cursor.execute('DELETE FROM aktive_sitzungen WHERE projekt_id = %s', (projekt_id,))
        
        # Projekt auf beendet setzen
        cursor.execute('''
            UPDATE projekte 
            SET status = 'beendet', beendet_am = %s 
            WHERE id = %s
        ''', (datetime.now(), projekt_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Projekt beendet'})
        
    except Exception as e:
        print(f"Fehler beim Beenden: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

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

@app.route('/projekt/<int:projekt_id>/bericht')
@login_required
def projekt_bericht(projekt_id):
    """Einzelprojekt-Bericht"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projekte WHERE id = %s', (projekt_id,))
        projekt_row = cursor.fetchone()
        
        if not projekt_row:
            conn.close()
            return "Projekt nicht gefunden", 404
        
        projekt = dict(projekt_row)
        
        if projekt['status'] != 'beendet':
            conn.close()
            return "Projekt ist noch nicht beendet", 400
        
        conn.close()
        return f"<h1>Bericht für Projekt: {projekt['name']}</h1><p><a href='/dashboard'>← Zurück</a></p>"
        
    except Exception as e:
        return f"<h1>Fehler: {str(e)}</h1>"
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
@app.route('/gesamt-bericht')
def gesamt_bericht():
    """Gesamt-Bericht mit sicherer ID-Extraktion"""
    try:
        von_datum_str = request.args.get('von', '')
        bis_datum_str = request.args.get('bis', '')
        
        print(f"📊 Gesamt-Bericht: {von_datum_str} bis {bis_datum_str}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # ✅ PROJEKTE holen
        projekte_query = '''
            SELECT DISTINCT p.id, p.name, p.kunde, p.status, p.erstellt_am
            FROM projekte p
            WHERE p.status = 'beendet'
            ORDER BY p.erstellt_am DESC
        '''
        
        cur.execute(projekte_query)
        projekte_raw = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        projekte_dict = [dict(zip(columns, row)) for row in projekte_raw]
        
        print(f"🔍 Columns: {columns}")
        print(f"🔍 Gefundene Projekte: {len(projekte_dict)}")
        
        # PROJEKTE MIT SITZUNGEN AUFBAUEN
        projekte = []
        
        for projekt in projekte_dict:
            # ✅ SICHERE ID-EXTRAKTION
            print(f"🔍 DEBUG projekt dict: {projekt}")
            
            # ID sicher extrahieren
            if 'id' in projekt and projekt['id'] != 'id':
                projekt_id = projekt['id']
            elif columns and len(projekt.values()) > 0:
                # Erste Spalte sollte ID sein
                projekt_id = list(projekt.values())[0]
            else:
                print(f"❌ Kann ID nicht finden für: {projekt}")
                continue

            # Sicherstellen dass es eine Zahl ist
            try:
                projekt_id = int(projekt_id)
                print(f"✅ Verwende projekt_id: {projekt_id}")
            except (ValueError, TypeError):
                print(f"❌ Ungültige projekt_id: {projekt_id}, überspringe Projekt")
                continue
            
            # ✅ SITZUNGEN holen
            if von_datum_str and bis_datum_str:
                sitzungen_query = '''
                    SELECT teilbereich, 
                           SUM(EXTRACT(EPOCH FROM (end_zeit - start_zeit))/3600) as stunden_gesamt
                    FROM sitzungen 
                    WHERE projekt_id = %s 
                      AND DATE(start_zeit) BETWEEN %s AND %s
                    GROUP BY teilbereich
                '''
                cur.execute(sitzungen_query, (projekt_id, von_datum_str, bis_datum_str))
            else:
                sitzungen_query = '''
                    SELECT teilbereich, 
                           SUM(EXTRACT(EPOCH FROM (end_zeit - start_zeit))/3600) as stunden_gesamt
                    FROM sitzungen 
                    WHERE projekt_id = %s
                    GROUP BY teilbereich
                '''
                cur.execute(sitzungen_query, (projekt_id,))
            
            sitzungen_raw = cur.fetchall()
            sitzungen_columns = [desc[0] for desc in cur.description]
            sitzungen = [dict(zip(sitzungen_columns, row)) for row in sitzungen_raw]
            
            print(f"🔍 Projekt {projekt_id}: {len(sitzungen)} Teilbereiche gefunden")
            
            # Teilbereiche initialisieren
            teilbereiche = {
                'besprechung': {'gesamt_minuten': 0},
                'zeichnung': {'gesamt_minuten': 0},
                'aufmass': {'gesamt_minuten': 0}
            }
            
            # Sitzungen zu Teilbereichen zuordnen
            for sitzung in sitzungen:
                teilbereich = sitzung['teilbereich'].lower().strip()
                stunden = float(sitzung['stunden_gesamt'] or 0)
                minuten = int(stunden * 60)
                
                print(f"🔍 Teilbereich: {teilbereich}, Stunden: {stunden}, Minuten: {minuten}")
                
                if teilbereich in teilbereiche:
                    teilbereiche[teilbereich]['gesamt_minuten'] = minuten
                elif teilbereich == 'aufmaß':
                    teilbereiche['aufmass']['gesamt_minuten'] = minuten
            
            projekt_final = {
                'id': projekt_id,
                'name': projekt.get('name', 'Unbekannt'),
                'kunde': projekt.get('kunde', 'Unbekannt'),
                'status': projekt.get('status', 'unbekannt'),
                'erstellt_am': projekt.get('erstellt_am', ''),
                'teilbereiche': teilbereiche
            }
            
            projekte.append(projekt_final)
        
        cur.close()
        conn.close()
        
        # DATUM FORMATIERUNG
        if von_datum_str and bis_datum_str:
            try:
                von_formatted = datetime.strptime(von_datum_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                bis_formatted = datetime.strptime(bis_datum_str, '%Y-%m-%d').strftime('%d.%m.%Y')
                zeitraum_text = f"{von_formatted} bis {bis_formatted}"
            except:
                zeitraum_text = f"{von_datum_str} bis {bis_datum_str}"
        else:
            zeitraum_text = "Alle beendeten Projekte"
        
        # GESAMT-ZEIT BERECHNEN
        alle_zeit_minuten = 0
        for projekt in projekte:
            projekt_zeit = (projekt['teilbereiche']['besprechung']['gesamt_minuten'] + 
                          projekt['teilbereiche']['zeichnung']['gesamt_minuten'] + 
                          projekt['teilbereiche']['aufmass']['gesamt_minuten'])
            alle_zeit_minuten += projekt_zeit
        
        print(f"✅ {len(projekte)} Projekte gefunden, {alle_zeit_minuten} Minuten gesamt")
        
        # IHR EXAKTES HTML TEMPLATE
        html_content = f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAUSCH - Gesamt-Bericht {zeitraum_text}</title>
    <style>
        :root {{
            --primary-dark: #4a5568;
            --primary-blue: #3498db;
            --background-light: #f8f9fa;
            --text-dark: #2c3e50;
            --text-light: #6c757d;
            --success: #28a745;
            --warning: #ffc107;
            --danger: #dc3545;
            --white: #ffffff;
            --border-color: #dee2e6;
            --gray: #6c757d;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            padding: 15px;
            font-size: 12px;
            line-height: 1.4;
        }}

        .report-container {{
            max-width: 100%;
            margin: 0 auto;
            background: white;
        }}

        .report-header {{
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 3px solid var(--primary-blue);
        }}

        .report-title {{
            font-size: 1.3em;
            font-weight: bold;
            color: var(--primary-dark);
            margin-bottom: 6px;
            line-height: 1.2;
        }}

        .report-subtitle {{
            font-size: 0.9em;
            color: var(--text-light);
        }}

        .report-section {{
            margin-bottom: 20px;
            background: var(--background-light);
            border-radius: 8px;
            padding: 12px;
            border-left: 3px solid var(--primary-blue);
        }}

        .section-title {{
            font-size: 1em;
            font-weight: bold;
            color: var(--primary-dark);
            margin-bottom: 12px;
        }}

        .projekt-item {{
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 10px;
            page-break-inside: avoid;
        }}

        .projekt-header {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 2px solid var(--primary-blue);
        }}

        .projekt-name {{
            font-size: 1em;
            font-weight: bold;
            color: var(--primary-dark);
            line-height: 1.2;
        }}

        .projekt-kunde {{
            color: var(--text-light);
            font-style: italic;
            font-size: 0.85em;
        }}

        .projekt-gesamt {{
            background: var(--primary-blue);
            color: white;
            padding: 4px 8px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 0.8em;
            align-self: flex-start;
            margin-top: 4px;
        }}

        .teilbereiche-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 6px;
            margin-top: 8px;
        }}

        .teilbereich-item {{
            background: var(--background-light);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .teilbereich-name {{
            font-weight: bold;
            font-size: 0.8em;
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .teilbereich-zeit {{
            color: var(--primary-blue);
            font-weight: bold;
            font-size: 0.8em;
        }}

        .action-buttons {{
            text-align: center;
            margin-top: 25px;
            padding-top: 15px;
            border-top: 2px solid var(--border-color);
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .btn {{
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
            transition: all 0.3s ease;
            color: white;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}

        .btn-print {{
            background: var(--success);
        }}

        .btn-back {{
            background: var(--gray);
        }}

        @media (min-width: 768px) {{
            body {{ padding: 20px; font-size: 14px; }}
            .report-container {{ max-width: 900px; }}
            .report-title {{ font-size: 1.8em; }}
            .report-subtitle {{ font-size: 1em; }}
            .projekt-header {{ flex-direction: row; justify-content: space-between; align-items: center; }}
            .projekt-gesamt {{ margin-top: 0; }}
            .teilbereiche-grid {{ grid-template-columns: repeat(3, 1fr); gap: 10px; }}
            .btn {{ padding: 15px 30px; font-size: 16px; }}
        }}

        @media (max-width: 768px) {{
            .action-buttons {{ flex-direction: column; align-items: center; gap: 10px; }}
            .btn {{ width: 100%; max-width: 250px; }}
        }}

        @media print {{
            .action-buttons {{ display: none !important; }}
            body {{ background: white !important; padding: 5px !important; font-size: 9px !important; }}
            @page {{ margin: 0.5cm; size: A4; }}
            .report-container {{ transform: scale(0.95); transform-origin: top left; width: 105%; }}
            .projekt-item {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 8px !important; }}
            .report-section {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 12px !important; }}
            .report-title {{ font-size: 1.4em !important; color: black !important; }}
            .report-subtitle {{ font-size: 0.8em !important; }}
            .section-title {{ font-size: 0.9em !important; color: black !important; }}
            .projekt-name {{ font-size: 0.9em !important; color: black !important; }}
            .teilbereiche-grid {{ grid-template-columns: repeat(3, 1fr) !important; gap: 6px !important; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <div class="report-title">📊 Gesamt-Bericht RAUSCH</div>
            <div class="report-subtitle">Zeitraum: {zeitraum_text}</div>
        </div>

        <div class="summary-bar" style="background: var(--primary-blue); color: white; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 20px; font-weight: bold; font-size: 14px;">
            📊 {len(projekte)} Projekt(e) | ⏱️ '''
        
        # ZEIT FORMATIERUNG
        if alle_zeit_minuten < 60:
            html_content += f"{alle_zeit_minuten}min"
        else:
            stunden = alle_zeit_minuten // 60
            minuten = alle_zeit_minuten % 60
            html_content += f"{stunden}h {minuten}min"
        
        html_content += f'''
        </div>

        <div class="report-section">
            <div class="section-title">🏗️ Beendete Projekte ({len(projekte)})</div>
            '''
        
        if projekte:
            for projekt in projekte:
                # GESAMT-ZEIT FÜR DIESES PROJEKT
                gesamt_minuten = (projekt['teilbereiche']['besprechung']['gesamt_minuten'] + 
                                projekt['teilbereiche']['zeichnung']['gesamt_minuten'] + 
                                projekt['teilbereiche']['aufmass']['gesamt_minuten'])
                
                if gesamt_minuten < 60:
                    gesamt_zeit_text = f"{gesamt_minuten}min"
                else:
                    stunden = gesamt_minuten // 60
                    minuten = gesamt_minuten % 60
                    gesamt_zeit_text = f"{stunden}h {minuten}min"
                
                html_content += f'''
                <div class="projekt-item">
                    <div class="projekt-header">
                        <div>
                            <div class="projekt-name">{projekt['name']}</div>
                            <div class="projekt-kunde">👤 {projekt['kunde']}</div>
                        </div>
                        <div class="projekt-gesamt">{gesamt_zeit_text}</div>
                    </div>
                    
                    <div class="teilbereiche-grid">
                        <div class="teilbereich-item">
                            <div class="teilbereich-name">💬 Besprechung</div>
                            <div class="teilbereich-zeit">'''
                
                # BESPRECHUNG ZEIT
                besp_min = projekt['teilbereiche']['besprechung']['gesamt_minuten']
                if besp_min < 60:
                    html_content += f"{besp_min}min"
                else:
                    html_content += f"{besp_min // 60}h {besp_min % 60}min"
                
                html_content += '''</div>
                        </div>
                        <div class="teilbereich-item">
                            <div class="teilbereich-name">📐 Zeichnung</div>
                            <div class="teilbereich-zeit">'''
                
                # ZEICHNUNG ZEIT
                zeich_min = projekt['teilbereiche']['zeichnung']['gesamt_minuten']
                if zeich_min < 60:
                    html_content += f"{zeich_min}min"
                else:
                    html_content += f"{zeich_min // 60}h {zeich_min % 60}min"
                
                html_content += '''</div>
                        </div>
                        <div class="teilbereich-item">
                            <div class="teilbereich-name">📏 Aufmaß</div>
                            <div class="teilbereich-zeit">'''
                
                # AUFMASS ZEIT
                aufm_min = projekt['teilbereiche']['aufmass']['gesamt_minuten']
                if aufm_min < 60:
                    html_content += f"{aufm_min}min"
                else:
                    html_content += f"{aufm_min // 60}h {aufm_min % 60}min"
                
                html_content += '''</div>
                        </div>
                    </div>
                </div>'''
        else:
            html_content += '''
                <div style="text-align: center; padding: 20px; color: var(--text-light); font-style: italic;">
                    📭 Keine beendeten Projekte im gewählten Zeitraum gefunden.
                </div>'''
        
        html_content += '''
        </div>

        <div class="action-buttons">
            <button onclick="window.print()" class="btn btn-print">
                🖨️ Drucken
            </button>
            <button onclick="goBack()" class="btn btn-back">
                ← Zurück
            </button>
        </div>
    </div>

    <script>
        function goBack() {
            if (window.history.length > 1) {
                window.history.back();
            } else {
                window.location.href = '/dashboard';
            }
        }

        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                goBack();
            }
        });

        if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) {
            document.addEventListener('DOMContentLoaded', function() {
                const meta = document.createElement('meta');
                meta.name = 'viewport';
                meta.content = 'width=device-width, initial-scale=0.9';
                document.getElementsByTagName('head')[0].appendChild(meta);
            });
        }
    </script>
</body>
</html>'''
        
        return html_content
        
    except Exception as e:
        print(f"❌ Fehler in gesamt_bericht: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Fehler: {str(e)}</h1><pre>{traceback.format_exc()}</pre>", 500
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)