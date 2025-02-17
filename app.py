from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import sqlite3
from datetime import date
import csv
import io
from functools import wraps
import os

app = Flask(__name__, template_folder="templates")
app.secret_key = 'votre_cle_secrete'  # Remplacez par une clé sécurisée

# Configuration d'authentification (identifiants hardcodés pour la démonstration)
USERNAME = 'admin'
PASSWORD = 'password'

def init_db():
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS encaissements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            produit TEXT,
            montant REAL
        )
    ''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            flash("Connexion réussie.", "success")
            return redirect(url_for('index'))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Déconnexion réussie.", "info")
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    if request.method == 'POST':
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = float(request.form['montant'])
        c.execute("INSERT INTO encaissements (date, produit, montant) VALUES (?, ?, ?)",
                  (date_encaissement, produit, montant))
        conn.commit()
        flash("Encaissement ajouté.", "success")
        return redirect(url_for('index'))
    c.execute("SELECT id, date, produit, montant FROM encaissements ORDER BY date DESC")
    encaissements = c.fetchall()
    conn.close()
    return render_template('index.html', encaissements=encaissements)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    if request.method == 'POST':
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = float(request.form['montant'])
        c.execute("UPDATE encaissements SET date=?, produit=?, montant=? WHERE id=?",
                  (date_encaissement, produit, montant, id))
        conn.commit()
        conn.close()
        flash("Encaissement modifié.", "success")
        return redirect(url_for('index'))
    c.execute("SELECT id, date, produit, montant FROM encaissements WHERE id=?", (id,))
    encaissement = c.fetchone()
    conn.close()
    if encaissement is None:
        flash("Encaissement non trouvé.", "danger")
        return redirect(url_for('index'))
    return render_template('edit.html', encaissement=encaissement)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    c.execute("DELETE FROM encaissements WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Encaissement supprimé.", "info")
    return redirect(url_for('index'))

@app.route('/totaux', methods=['GET'])
@login_required
def totaux():
    mois = request.args.get('mois', date.today().strftime('%Y-%m'))
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    c.execute("SELECT SUM(montant) FROM encaissements WHERE date LIKE ?", (mois + '%',))
    total = c.fetchone()[0] or 0
    conn.close()
    return render_template('totaux.html', total=total, mois=mois)

@app.route('/export', methods=['GET'])
@login_required
def export():
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    c.execute("SELECT date, produit, montant FROM encaissements ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Produit', 'Montant'])
    writer.writerows(rows)
    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=encaissements.csv"})

@app.route('/clear', methods=['POST'])
@login_required
def clear():
    # Récupération du mois envoyé par le formulaire (format 'YYYY-MM')
    mois = request.form.get('mois', date.today().strftime('%Y-%m'))
    conn = sqlite3.connect('encaissements.db')
    c = conn.cursor()
    # Suppression des enregistrements dont la date commence par le mois sélectionné
    c.execute("DELETE FROM encaissements WHERE date LIKE ?", (mois + '%',))
    conn.commit()
    conn.close()
    flash(f"Historique des ventes du mois {mois} vidé.", "info")
    return redirect(url_for('totaux', mois=mois))

@app.errorhandler(500)
def internal_error(error):
    app.logger.error('Erreur interne: %s', error)
    return "Une erreur est survenue, consultez les logs pour plus de détails.", 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)