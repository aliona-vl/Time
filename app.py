from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import hashlib
import secrets
import io
import time
# In app.py ganz oben nach den imports:
import pytz


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ✅ LOGIN REQUIRED DECORATOR
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'benutzer_email' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ✅ Team-Code Definition
TEAM_CODE = 'RAUSCH2025'

# Dateien
BENUTZER_FILE = 'benutzer.json'
PROJEKTE_FILE = 'projekte.json'
MITARBEITER_FILE = 'mitarbeiter.json'
KUNDEN_FILE = 'kunden.json'

TEILBEREICHE = ['besprechung', 'zeichnung', 'aufmass']
STANDARD_MITARBEITER = ['Andreas', 'Mark', 'Fritz', 'Sabine', 'Thomas']
STANDARD_KUNDEN = [
    'Bosch Lollar',
    'Buderus Guss GmbH',
    'Duktus',
    'Fritz Winter',
    'Geissler',
    'Hasenclever',
    'Herborner Pumpenfabrik',
    'Nowakowski'
]

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {} if filename == BENUTZER_FILE else []

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_mitarbeiter():
    if os.path.exists(MITARBEITER_FILE):
        with open(MITARBEITER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        save_data(MITARBEITER_FILE, STANDARD_MITARBEITER)
        return STANDARD_MITARBEITER

def load_kunden():
    if os.path.exists(KUNDEN_FILE):
        with open(KUNDEN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        save_data(KUNDEN_FILE, STANDARD_KUNDEN)
        return STANDARD_KUNDEN

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

def erstelle_projekt_bericht(projekt):
    """Erstellt einen detaillierten Projektbericht"""
    # Gesamt-Minuten berechnen
    gesamt_minuten = 0
    mitarbeiter_stats = {}
    teilbereich_stats = {}
    
    # Durch alle Teilbereiche iterieren
    for teilbereich_name, teilbereich_data in projekt['teilbereiche'].items():
        teilbereich_minuten = teilbereich_data.get('gesamt_minuten', 0)
        gesamt_minuten += teilbereich_minuten
        
        # Teilbereich-Statistiken
        teilbereich_stats[teilbereich_name] = {
            'gesamt_minuten': teilbereich_minuten,
            'gesamt_zeit': berechne_dauer_text(teilbereich_minuten),
            'anzahl_sitzungen': len(teilbereich_data.get('sitzungen', []))
        }
        
        # Mitarbeiter-Statistiken sammeln
        for sitzung in teilbereich_data.get('sitzungen', []):
            mitarbeiter = sitzung.get('mitarbeiter', 'Unbekannt')
            
            if mitarbeiter not in mitarbeiter_stats:
                mitarbeiter_stats[mitarbeiter] = {
                    'besprechung': 0,
                    'zeichnung': 0,
                    'aufmass': 0,
                    'gesamt_minuten': 0
                }
            
            sitzung_minuten = sitzung.get('dauer_minuten', 0)
            mitarbeiter_stats[mitarbeiter][teilbereich_name] += sitzung_minuten
            mitarbeiter_stats[mitarbeiter]['gesamt_minuten'] += sitzung_minuten
    
    # Mitarbeiter-Zeiten formatieren
    for mitarbeiter, stats in mitarbeiter_stats.items():
        stats['gesamt_zeit'] = berechne_dauer_text(stats['gesamt_minuten'])
        stats['teilbereiche'] = {
            'besprechung': berechne_dauer_text(stats['besprechung']),
            'zeichnung': berechne_dauer_text(stats['zeichnung']),
            'aufmass': berechne_dauer_text(stats['aufmass'])
        }
    
    # ✅ KALENDERTAGE BERECHNEN
    alle_arbeitsdaten = []
    
    for teilbereich_name, teilbereich_data in projekt['teilbereiche'].items():
        for sitzung in teilbereich_data.get('sitzungen', []):
            start_datum = sitzung['start'][:10]
            alle_arbeitsdaten.append(start_datum)
    
    if alle_arbeitsdaten:
        alle_arbeitsdaten.sort()
        erstes_datum = datetime.strptime(alle_arbeitsdaten[0], '%Y-%m-%d')
        letztes_datum = datetime.strptime(alle_arbeitsdaten[-1], '%Y-%m-%d')
        kalendertage = (letztes_datum - erstes_datum).days + 1
    else:
        kalendertage = 0
    
    # ✅ GESAMT-SITZUNGEN BERECHNEN
    gesamt_sitzungen = sum(len(data.get('sitzungen', [])) for data in projekt['teilbereiche'].values())
    
    return {
        'projekt_name': projekt['name'],
        'gesamt_arbeitszeit': berechne_dauer_text(gesamt_minuten),
        'gesamt_minuten': gesamt_minuten,
        'kalendertage': kalendertage,  # ✅ KALENDERTAGE STATT projekt_dauer_tage
        'gesamt_sitzungen': gesamt_sitzungen,  # ✅ KORREKTE SITZUNGEN-BERECHNUNG
        'teilbereiche': teilbereich_stats,
        'mitarbeiter': mitarbeiter_stats
    }


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

    benutzer = load_data(BENUTZER_FILE)

    if email in benutzer:
        return jsonify({'status': 'error', 'message': 'E-Mail bereits registriert'})

    # ✅ Team-Code prüfen
    if not team_code:
        return jsonify({'status': 'error', 'message': 'Team-Code ist erforderlich'})

    if team_code != TEAM_CODE:
        return jsonify({'status': 'error', 'message': 'Ungültiger Team-Code'})

    # ✅ Benutzer erstellen
    benutzer[email] = {
        'password_hash': hash_password(password),
        'registriert_am': datetime.now().isoformat(),
        'name': email.split('@')[0].title(),
        'team_code_verwendet': team_code
    }

    save_data(BENUTZER_FILE, benutzer)

    # ✅ Automatisch anmelden bei gültigem Team-Code
    session['benutzer_email'] = email
    session['benutzer_name'] = benutzer[email]['name']

    return jsonify({
        'status': 'success',
        'sofort_zugriff': True,
        'message': 'Willkommen im Team!'
    })

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip().lower()
    password = request.form['password']

    benutzer = load_data(BENUTZER_FILE)

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
def dashboard():
    if 'benutzer_email' not in session:
        return redirect('/')

    alle_projekte = load_data(PROJEKTE_FILE)
    benutzer_email = session['benutzer_email']

    # ✅ TEAM-CODE PRÜFEN UND TEAM-PROJEKTE ANZEIGEN
    benutzer_data = load_data(BENUTZER_FILE)
    benutzer_info = benutzer_data.get(benutzer_email, {})
    team_code = benutzer_info.get('team_code_verwendet')
    
    if team_code == TEAM_CODE:
        # ✅ TEAM-MITGLIED → ALLE PROJEKTE SEHEN
        projekte = alle_projekte
    else:
        # ❌ KEIN TEAM-MITGLIED → NUR EIGENE PROJEKTE
        projekte = [p for p in alle_projekte if p.get('ersteller') == benutzer_email]

    # ✅ ERWEITERTE SORTIERUNG
    def erweiterte_sortierung(projekt):
        status_prioritäten = {
            'laufend': 2,
            'pausiert': 3,
            'gestoppt': 1,
            'beendet': 4
        }

        status_prio = status_prioritäten.get(projekt['status'], 5)

        if projekt['status'] == 'beendet':
            beendet_am = projekt.get('beendet_am', '2000-01-01')
            return (status_prio, beendet_am)
        else:
            erstellt_am = projekt.get('erstellt_am', '2000-01-01')
            return (status_prio, erstellt_am)

    projekte = sorted(projekte, key=erweiterte_sortierung)
    mitarbeiter = load_mitarbeiter()
    kunden = load_kunden()

    return render_template('dashboard.html',
                         projekte=projekte,
                         teilbereiche=TEILBEREICHE,
                         mitarbeiter=mitarbeiter,
                         kunden=kunden,
                         benutzer_name=session['benutzer_name'])

@app.route('/projekt/neu', methods=['POST'])
def neues_projekt():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    name = request.form['name'].strip()
    kunde = request.form['kunde'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Projektname erforderlich'})
    if not kunde:
        return jsonify({'status': 'error', 'message': 'Kunde erforderlich'})

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt_id = max([p['id'] for p in alle_projekte], default=0) + 1

    jetzt = datetime.now().isoformat()

    projekt = {
        'id': projekt_id,
        'name': name,
        'kunde': kunde,
        'ersteller': session['benutzer_email'],
        'benutzer_email': session['benutzer_email'],
        'status': 'gestoppt',
        'erstellt_am': jetzt,  # ✅ WIRD NIE GEÄNDERT
        'erster_start': None,  # ✅ NEU: Wird beim ersten Start gesetzt
        'letzter_start': None,  # ✅ NEU: Wird bei jedem Start aktualisiert
        'beendet_am': None,
        'aktive_sitzungen': {},
        'teilbereiche': {
            'besprechung': {'sitzungen': [], 'gesamt_minuten': 0},
            'zeichnung': {'sitzungen': [], 'gesamt_minuten': 0},
            'aufmass': {'sitzungen': [], 'gesamt_minuten': 0}
        }
    }

    alle_projekte.append(projekt)
    save_data(PROJEKTE_FILE, alle_projekte)
    return jsonify({'status': 'success', 'projekt_id': projekt_id})

@app.route('/projekt/<int:projekt_id>')
def projekt_details(projekt_id):
    if 'benutzer_email' not in session:
        return redirect(url_for('index'))

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt = next((p for p in alle_projekte if p['id'] == projekt_id), None)

    if not projekt:
        return "Projekt nicht gefunden", 404

    # ✅ TEAM-BERECHTIGUNG PRÜFEN
    benutzer_email = session['benutzer_email']
    benutzer_data = load_data(BENUTZER_FILE)
    benutzer_info = benutzer_data.get(benutzer_email, {})
    user_team_code = benutzer_info.get('team_code_verwendet')
    
    projekt_ersteller = projekt.get('ersteller')
    
    # ✅ ZUGRIFF PRÜFEN
    if user_team_code == TEAM_CODE:
        # Team-Mitglied hat Zugriff auf alle Projekte
        pass
    elif projekt_ersteller == benutzer_email:
        # Eigenes Projekt
        pass
    else:
        return "Keine Berechtigung für dieses Projekt", 403

    mitarbeiter = load_mitarbeiter()
    return render_template('projekt_details.html',
                         projekt=projekt,
                         teilbereiche=TEILBEREICHE,
                         mitarbeiter=mitarbeiter,
                         benutzer_name=session['benutzer_name'])

@app.route('/projekt/<int:projekt_id>/aktivität/starten', methods=['POST'])
def aktivität_starten(projekt_id):
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    mitarbeiter = request.form['mitarbeiter']
    teilbereich = request.form['teilbereich']

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt = next((p for p in alle_projekte if p['id'] == projekt_id), None)

    if not projekt:
        return jsonify({'status': 'error', 'message': 'Projekt nicht gefunden'})

    if mitarbeiter in projekt.get('aktive_sitzungen', {}):
        return jsonify({'status': 'error', 'message': f'{mitarbeiter} arbeitet bereits'})

    jetzt = datetime.now().isoformat()
    
    # ✅ ERSTER START MERKEN
    if projekt.get('erster_start') is None:
        projekt['erster_start'] = jetzt
    
    # ✅ LETZTEN START MERKEN
    projekt['letzter_start'] = jetzt

    projekt['aktive_sitzungen'][mitarbeiter] = {
        'teilbereich': teilbereich,
        'start': jetzt
    }

    projekt['status'] = 'laufend'
    save_data(PROJEKTE_FILE, alle_projekte)

    return jsonify({'status': 'success'})

@app.route('/projekt/<int:projekt_id>/aktivität/beenden', methods=['POST'])
def aktivität_beenden(projekt_id):
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    mitarbeiter = request.form['mitarbeiter']

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt = next((p for p in alle_projekte if p['id'] == projekt_id), None)

    if not projekt or mitarbeiter not in projekt.get('aktive_sitzungen', {}):
        return jsonify({'status': 'error', 'message': 'Keine aktive Sitzung'})

    aktive_sitzung = projekt['aktive_sitzungen'][mitarbeiter]
    start_zeit = datetime.fromisoformat(aktive_sitzung['start'])
    end_zeit = datetime.now()
    dauer_minuten = int((end_zeit - start_zeit).total_seconds() / 60)

    teilbereich = aktive_sitzung['teilbereich']

    sitzung = {
        'mitarbeiter': mitarbeiter,
        'start': aktive_sitzung['start'],
        'end': end_zeit.isoformat(),
        'dauer_minuten': dauer_minuten
    }

    projekt['teilbereiche'][teilbereich]['sitzungen'].append(sitzung)
    projekt['teilbereiche'][teilbereich]['gesamt_minuten'] += dauer_minuten

    del projekt['aktive_sitzungen'][mitarbeiter]

    if not projekt['aktive_sitzungen']:
        projekt['status'] = 'pausiert'

    save_data(PROJEKTE_FILE, alle_projekte)

    return jsonify({
        'status': 'success',
        'dauer_text': berechne_dauer_text(dauer_minuten)
    })

@app.route('/projekt/<int:projekt_id>/beenden', methods=['POST'])
def projekt_beenden(projekt_id):
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt = next((p for p in alle_projekte if p['id'] == projekt_id), None)

    if not projekt:
        return jsonify({'status': 'error', 'message': 'Projekt nicht gefunden'})

    # Alle aktiven Sitzungen beenden
    for mitarbeiter in list(projekt.get('aktive_sitzungen', {}).keys()):
        aktive_sitzung = projekt['aktive_sitzungen'][mitarbeiter]
        start_zeit = datetime.fromisoformat(aktive_sitzung['start'])
        end_zeit = datetime.now()
        dauer_minuten = int((end_zeit - start_zeit).total_seconds() / 60)

        teilbereich = aktive_sitzung['teilbereich']

        sitzung = {
            'mitarbeiter': mitarbeiter,
            'start': aktive_sitzung['start'],
            'end': end_zeit.isoformat(),
            'dauer_minuten': dauer_minuten
        }

        projekt['teilbereiche'][teilbereich]['sitzungen'].append(sitzung)
        projekt['teilbereiche'][teilbereich]['gesamt_minuten'] += dauer_minuten

    projekt['status'] = 'beendet'
    projekt['beendet_am'] = datetime.now().isoformat()
    projekt['aktive_sitzungen'] = {}

    save_data(PROJEKTE_FILE, alle_projekte)
    return jsonify({'status': 'success'})

@app.route('/projekte/löschen', methods=['POST'])
def projekte_löschen():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    projekt_ids = request.json.get('projekt_ids', [])

    alle_projekte = load_data(PROJEKTE_FILE)
    neue_projekte = []

    for projekt in alle_projekte:
        if projekt['id'] not in projekt_ids:
            neue_projekte.append(projekt)

    save_data(PROJEKTE_FILE, neue_projekte)
    return jsonify({'status': 'success'})

@app.route('/projekt/<int:projekt_id>/bericht')
def projekt_bericht(projekt_id):
    if 'benutzer_email' not in session:
        return redirect(url_for('index'))

    alle_projekte = load_data(PROJEKTE_FILE)
    projekt = next((p for p in alle_projekte if p['id'] == projekt_id), None)

    if not projekt:
        return "Projekt nicht gefunden", 404

    if projekt['status'] != 'beendet':
        return "Projekt ist noch nicht beendet", 400

    bericht = erstelle_projekt_bericht(projekt)
    return render_template('bericht.html', bericht=bericht, projekt=projekt)

@app.route('/gesamt_bericht')
def gesamt_bericht():
    if 'benutzer_email' not in session:
        return redirect(url_for('index'))
    
    von_datum = request.args.get('von', '2025-01-01')
    bis_datum = request.args.get('bis', '2025-12-31')
    
    alle_projekte_data = load_data(PROJEKTE_FILE)
    benutzer_email = session['benutzer_email']
    
    # ✅ TEAM-CODE PRÜFEN
    benutzer_data = load_data(BENUTZER_FILE)
    benutzer_info = benutzer_data.get(benutzer_email, {})
    user_team_code = benutzer_info.get('team_code_verwendet')
    
    beendete_projekte = []
    gesamt_zeit_beendete = 0
    
    for projekt in alle_projekte_data:
        # ✅ TEAM-BERECHTIGUNG PRÜFEN
        if user_team_code == TEAM_CODE:
            # Team-Mitglied sieht alle beendeten Projekte
            pass
        elif projekt.get('ersteller') == benutzer_email:
            # Nicht-Team-Mitglied sieht nur eigene
            pass
        else:
            continue
            
        if projekt.get('status') != 'beendet':
            continue
            
        created_date = projekt.get('erstellt_am', '2025-01-01')[:10]
        if not (von_datum <= created_date <= bis_datum):
            continue
        
        projekt_zeit = 0
        teilbereiche_data = {}
        
        for tb_name in ['besprechung', 'zeichnung', 'aufmass']:
            tb_data = projekt.get('teilbereiche', {}).get(tb_name, {})
            tb_minuten = tb_data.get('gesamt_minuten', 0)
            
            teilbereiche_data[tb_name] = {
                'gesamt_minuten': tb_minuten,
                'sitzungen': tb_data.get('sitzungen', [])
            }
            projekt_zeit += tb_minuten
        
        gesamt_zeit_beendete += projekt_zeit
        
        beendete_projekte.append({
            'id': projekt['id'],
            'name': projekt.get('name', f'Projekt {projekt["id"]}'),
            'kunde': projekt.get('kunde', 'Unbekannt'),
            'status': projekt.get('status', 'beendet'),
            'erstellt_am': projekt.get('erstellt_am', ''),
            'teilbereiche': teilbereiche_data
        })
    
    return render_template('gesamt_bericht.html', 
                         projekte=beendete_projekte,
                         gesamt_zeit_alle=gesamt_zeit_beendete,
                         von_datum=von_datum,
                         bis_datum=bis_datum)        

# ✅ EXPORT FUNKTIONEN MIT DETAILLIERTEN ZEITEN
@app.route('/export/vorschau', methods=['POST'])
def export_vorschau():
    """Zeigt Vorschau der zu exportierenden Projekte mit detaillierten Zeiten"""
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    data = request.get_json()
    von_datum = data.get('von_datum')
    bis_datum = data.get('bis_datum')

    if not von_datum or not bis_datum:
        return jsonify({'status': 'error', 'message': 'Datum erforderlich'})

    # ✅ TEAM-BERECHTIGUNG PRÜFEN
    benutzer_email = session['benutzer_email']
    benutzer_data = load_data(BENUTZER_FILE)
    benutzer_info = benutzer_data.get(benutzer_email, {})
    user_team_code = benutzer_info.get('team_code_verwendet')

    # ✅ Alle beendeten Projekte finden
    alle_projekte = load_data(PROJEKTE_FILE)
    gefundene_projekte = []
    gesamt_minuten = 0
    
    # ✅ GESAMT-ZEITEN FÜR ALLE TEILBEREICHE
    gesamt_besprechung = 0
    gesamt_zeichnung = 0
    gesamt_aufmass = 0

    # ✅ ZEIT FORMATIEREN FUNKTION
    def format_zeit(minuten):
        if minuten == 0:
            return "0min"
        elif minuten < 60:
            return f"{minuten}min"
        else:
            stunden = minuten // 60
            rest_min = minuten % 60
            if rest_min == 0:
                return f"{stunden}h"
            else:
                return f"{stunden}h {rest_min}min"

    for projekt in alle_projekte:
        # ✅ TEAM-BERECHTIGUNG PRÜFEN
        if user_team_code == TEAM_CODE:
            # Team-Mitglied sieht alle beendeten Projekte
            pass
        elif projekt.get('ersteller') == benutzer_email:
            # Nicht-Team-Mitglied sieht nur eigene
            pass
        else:
            continue
            
        if projekt['status'] == 'beendet':
            # ✅ DETAILLIERTE ZEIT-BERECHNUNG
            besprechung_min = projekt['teilbereiche']['besprechung']['gesamt_minuten']
            zeichnung_min = projekt['teilbereiche']['zeichnung']['gesamt_minuten']
            aufmass_min = projekt['teilbereiche']['aufmass']['gesamt_minuten']
            projekt_gesamt = besprechung_min + zeichnung_min + aufmass_min

            # ✅ GESAMT-SUMMEN
            gesamt_minuten += projekt_gesamt
            gesamt_besprechung += besprechung_min
            gesamt_zeichnung += zeichnung_min
            gesamt_aufmass += aufmass_min

            gefundene_projekte.append({
                'name': projekt['name'],
                'kunde': projekt['kunde'],
                'status': projekt['status'],
                'erstellt_datum': projekt.get('erstellt_am', '2024-01-01')[:10],
                'beendet_datum': projekt.get('beendet_am', '2024-12-31')[:10],
                'gesamt_zeit': format_zeit(projekt_gesamt),
                'besprechung_zeit': format_zeit(besprechung_min),
                'zeichnung_zeit': format_zeit(zeichnung_min),
                'aufmass_zeit': format_zeit(aufmass_min)
            })

    return jsonify({
        'status': 'success',
        'projekte': gefundene_projekte,
        'gesamt_zeit': format_zeit(gesamt_minuten),
        'gesamt_besprechung': format_zeit(gesamt_besprechung),
        'gesamt_zeichnung': format_zeit(gesamt_zeichnung),
        'gesamt_aufmass': format_zeit(gesamt_aufmass)
    })

@app.route('/export/pdf')
def export_pdf():
    """Generiert PDF-Bericht für den gewählten Zeitraum"""
    if 'benutzer_email' not in session:
        return redirect(url_for('index'))

    von_datum = request.args.get('von', '2025-01-01')
    bis_datum = request.args.get('bis', '2025-12-31')

    # ✅ TEAM-BERECHTIGUNG PRÜFEN
    benutzer_email = session['benutzer_email']
    benutzer_data = load_data(BENUTZER_FILE)
    benutzer_info = benutzer_data.get(benutzer_email, {})
    user_team_code = benutzer_info.get('team_code_verwendet')

    # ✅ SAMMLE ALLE BEENDETEN PROJEKTE IM ZEITRAUM
    alle_projekte_data = load_data(PROJEKTE_FILE)
    beendete_projekte = []

    for projekt in alle_projekte_data:
        # ✅ TEAM-BERECHTIGUNG PRÜFEN
        if user_team_code == TEAM_CODE:
            # Team-Mitglied sieht alle beendeten Projekte
            pass
        elif projekt.get('ersteller') == benutzer_email:
            # Nicht-Team-Mitglied sieht nur eigene
            pass
        else:
            continue
            
        # ✅ PRÜFE OB BEENDET
        if projekt.get('status') == 'beendet':
            # ✅ ERSTELLE KORREKTE DATENSTRUKTUR FÜR gesamt_bericht.html
            teilbereiche_data = {}
            
            for tb_name in ['besprechung', 'zeichnung', 'aufmass']:
                tb_data = projekt.get('teilbereiche', {}).get(tb_name, {})
                teilbereiche_data[tb_name] = {
                    'gesamt_minuten': tb_data.get('gesamt_minuten', 0),
                    'sitzungen': tb_data.get('sitzungen', [])
                }
            
            beendete_projekte.append({
                'name': projekt.get('name', f'Projekt {projekt["id"]}'),
                'kunde': projekt.get('kunde', 'Unbekannt'),
                'id': projekt['id'],
                'status': projekt.get('status', 'beendet'),
                'erstellt_am': projekt.get('erstellt_am', ''),
                'teilbereiche': teilbereiche_data
            })

    # ✅ VERWENDE gesamt_bericht.html
    return render_template('gesamt_bericht.html',
                         projekte=beendete_projekte,
                         von_datum=von_datum,
                         bis_datum=bis_datum)

@app.route('/export/vorschau-pdf')
def export_vorschau_pdf():
    if 'benutzer_email' not in session:
        return redirect(url_for('index'))
        
    von_datum = request.args.get('von')
    bis_datum = request.args.get('bis')
    
    if not von_datum or not bis_datum:
        return "Datum fehlt", 400
    
    try:
        # ✅ TEAM-BERECHTIGUNG PRÜFEN
        benutzer_email = session['benutzer_email']
        benutzer_data = load_data(BENUTZER_FILE)
        benutzer_info = benutzer_data.get(benutzer_email, {})
        user_team_code = benutzer_info.get('team_code_verwendet')
        
        # ✅ RICHTIGES DATEN-LADEN
        alle_projekte = load_data(PROJEKTE_FILE)
        projekte = []
        
        # ✅ ZEIT FORMATIEREN FUNKTION
        def format_zeit(minuten):
            if minuten == 0:
                return "0min"
            elif minuten < 60:
                return f"{minuten}min"
            else:
                stunden = minuten // 60
                rest_min = minuten % 60
                if rest_min == 0:
                    return f"{stunden}h"
                else:
                    return f"{stunden}h {rest_min}min"
        
        gesamt_alle = 0
        gesamt_besprechung = 0
        gesamt_zeichnung = 0
        gesamt_aufmass = 0
        
        for projekt_data in alle_projekte:
            # ✅ TEAM-BERECHTIGUNG PRÜFEN
            if user_team_code == TEAM_CODE:
                # Team-Mitglied sieht alle beendeten Projekte
                pass
            elif projekt_data.get('ersteller') == benutzer_email:
                # Nicht-Team-Mitglied sieht nur eigene
                pass
            else:
                continue
                
            if projekt_data.get('status') == 'beendet':
                # ✅ BERECHNE ZEITEN
                besprechung_min = projekt_data['teilbereiche']['besprechung']['gesamt_minuten']
                zeichnung_min = projekt_data['teilbereiche']['zeichnung']['gesamt_minuten']
                aufmass_min = projekt_data['teilbereiche']['aufmass']['gesamt_minuten']
                projekt_gesamt = besprechung_min + zeichnung_min + aufmass_min
                
                gesamt_alle += projekt_gesamt
                gesamt_besprechung += besprechung_min
                gesamt_zeichnung += zeichnung_min
                gesamt_aufmass += aufmass_min
                
                projekte.append({
                    'name': projekt_data['name'],
                    'kunde': projekt_data['kunde'],
                    'status': projekt_data['status'],
                    'erstellt_datum': projekt_data.get('erstellt_am', '2025-01-01')[:10],
                    'gesamt_zeit': format_zeit(projekt_gesamt),
                    'besprechung_zeit': format_zeit(besprechung_min),
                    'zeichnung_zeit': format_zeit(zeichnung_min),
                    'aufmass_zeit': format_zeit(aufmass_min)
                })
        
        # ✅ HTML MIT DETAILLIERTEN ZEITEN
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>RAUSCH Bericht</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .projekt {{ 
                    background: #f8f9fa; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-left: 3px solid #3498db; 
                    border-radius: 5px;
                }}
                .projekt-name {{ font-weight: bold; font-size: 16px; margin-bottom: 5px; }}
                .projekt-details {{ font-size: 12px; color: #666; line-height: 1.4; }}
                .gesamt-box {{ 
                    background: #3498db; 
                    color: white; 
                    padding: 20px; 
                    border-radius: 8px; 
                    margin: 20px 0;
                    text-align: center;
                }}
                @media print {{
                    body {{ margin: 0; }}
                    .no-print {{ display: none; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 RAUSCH - Projektbericht</h1>
                <p>📅 Zeitraum: {von_datum} bis {bis_datum}</p>
            </div>
            
            <h2>Beendete Projekte:</h2>
        """
        
        for projekt in projekte:
            html_content += f"""
            <div class="projekt">
                <div class="projekt-name">{projekt['name']}</div>
                <div class="projekt-details">
                    👤 {projekt['kunde']} | 📅 {projekt['erstellt_datum']} | ⏱️ {projekt['gesamt_zeit']}<br>
                    📋 Besprechung: {projekt['besprechung_zeit']} | 
                    ✏️ Zeichnung: {projekt['zeichnung_zeit']} | 
                    📏 Aufmaß: {projekt['aufmass_zeit']}
                </div>
            </div>
            """
        
        html_content += f"""
            <div class="gesamt-box">
                <h3>📊 GESAMT-ZUSAMMENFASSUNG</h3>
                <div style="font-size: 18px; margin: 10px 0;">
                    ⏱️ Gesamtzeit: {format_zeit(gesamt_alle)}
                </div>
                <div style="font-size: 14px;">
                    📋 Besprechung: {format_zeit(gesamt_besprechung)} | 
                    ✏️ Zeichnung: {format_zeit(gesamt_zeichnung)} | 
                    📏 Aufmaß: {format_zeit(gesamt_aufmass)}
                </div>
                <div style="margin-top: 10px; font-size: 16px;">
                    📊 Anzahl Projekte: {len(projekte)}
                </div>
            </div>
            
            <div style="margin-top: 30px; text-align: center; font-size: 12px; color: #6c757d;">
                Erstellt am: {datetime.now().strftime('%d.%m.%Y um %H:%M')}
            </div>
            
            <script>
                window.onload = function() {{
                    setTimeout(function() {{
                        window.print();
                    }}, 500);
                }}
            </script>
        </body>
        </html>
        """
        
        return html_content
        
    except Exception as e:
        return f"Fehler: {str(e)}", 500

# ✅ MANAGEMENT FUNKTIONEN
@app.route('/mitarbeiter/hinzufügen', methods=['POST'])
def mitarbeiter_hinzufügen():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    name = request.form['name'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name ist erforderlich'})

    mitarbeiter = load_mitarbeiter()
    if name in mitarbeiter:
        return jsonify({'status': 'error', 'message': 'Mitarbeiter existiert bereits'})

    mitarbeiter.append(name)
    save_data(MITARBEITER_FILE, mitarbeiter)
    return jsonify({'status': 'success'})

@app.route('/mitarbeiter/löschen', methods=['POST'])
def mitarbeiter_löschen():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    name = request.form['name']
    mitarbeiter = load_mitarbeiter()

    if name in mitarbeiter:
        mitarbeiter.remove(name)
        save_data(MITARBEITER_FILE, mitarbeiter)

    return jsonify({'status': 'success'})

@app.route('/kunde/hinzufügen', methods=['POST'])
def kunde_hinzufügen():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    name = request.form['name'].strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name ist erforderlich'})

    kunden = load_kunden()
    if name in kunden:
        return jsonify({'status': 'error', 'message': 'Kunde existiert bereits'})

    kunden.append(name)
    save_data(KUNDEN_FILE, kunden)
    return jsonify({'status': 'success'})

@app.route('/kunde/löschen', methods=['POST'])
def kunde_löschen():
    if 'benutzer_email' not in session:
        return jsonify({'status': 'error', 'message': 'Nicht angemeldet'})

    name = request.form['name']
    kunden = load_kunden()

    if name in kunden:
        kunden.remove(name)
        save_data(KUNDEN_FILE, kunden)

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)