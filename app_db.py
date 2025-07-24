from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps
import os
import time
import hashlib
import secrets
from database import *
import pytz
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
        
        # Datum validieren und parsen
        try:
            von_datum = datetime.strptime(von_datum_str, '%Y-%m-%d')
            bis_datum = datetime.strptime(bis_datum_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'status': 'error', 
                'message': 'Ungültiges Datumsformat'
            })
        
        # Bis-Datum bis Ende des Tages setzen
        bis_datum = bis_datum.replace(hour=23, minute=59, second=59)
        
        # Validierung: Von-Datum nicht nach Bis-Datum
        if von_datum > bis_datum:
            return jsonify({
                'status': 'error',
                'message': 'Von-Datum darf nicht nach Bis-Datum liegen'
            })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Benutzer-Berechtigung prüfen
        benutzer_email = session['benutzer_email']
        cursor.execute('SELECT team_code_verwendet FROM benutzer WHERE email = %s', (benutzer_email,))
        benutzer_info = cursor.fetchone()
        user_team_code = benutzer_info['team_code_verwendet'] if benutzer_info else None
        
        # Projekte laden mit Sitzungen im Zeitraum
        if user_team_code == TEAM_CODE:
            projekte_query = '''
                SELECT DISTINCT p.* FROM projekte p 
                JOIN sitzungen s ON p.id = s.projekt_id 
                WHERE s.start_zeit >= %s AND s.start_zeit <= %s
                ORDER BY p.name
            '''
            cursor.execute(projekte_query, (von_datum, bis_datum))
        else:
            projekte_query = '''
                SELECT DISTINCT p.* FROM projekte p 
                JOIN sitzungen s ON p.id = s.projekt_id 
                WHERE p.ersteller = %s AND s.start_zeit >= %s AND s.start_zeit <= %s
                ORDER BY p.name
            '''
            cursor.execute(projekte_query, (benutzer_email, von_datum, bis_datum))
        
        projekte_data = []
        gesamt_minuten_periode = 0
        
        for projekt_row in cursor.fetchall():
            projekt = dict(projekt_row)
            
            # Sitzungen für dieses Projekt im Zeitraum laden
            cursor.execute('''
                SELECT mitarbeiter, teilbereich, start_zeit, end_zeit, dauer_minuten 
                FROM sitzungen 
                WHERE projekt_id = %s AND start_zeit >= %s AND start_zeit <= %s
                ORDER BY start_zeit ASC
            ''', (projekt['id'], von_datum, bis_datum))
            
            sitzungen = cursor.fetchall()
            
            if not sitzungen:  # Überspringen wenn keine Sitzungen im Zeitraum
                continue
            
            # Daten nach Mitarbeiter und Tätigkeit gruppieren
            mitarbeiter_stats = {}
            gesamt_minuten_projekt = 0
            
            for sitzung in sitzungen:
                mitarbeiter = sitzung['mitarbeiter']
                taetigkeit = sitzung['teilbereich']
                minuten = sitzung['dauer_minuten']
                
                # Mitarbeiter-Statistiken
                if mitarbeiter not in mitarbeiter_stats:
                    mitarbeiter_stats[mitarbeiter] = {
                        'besprechung': 0,
                        'zeichnung': 0,
                        'aufmass': 0,
                        'gesamt': 0
                    }
                
                mitarbeiter_stats[mitarbeiter][taetigkeit] += minuten
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
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)