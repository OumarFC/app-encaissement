import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from datetime import date
import csv
import io

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'votre_cle_secrete')

DATABASE = 'encaissements.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Accès aux colonnes par nom
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS encaissements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            produit TEXT NOT NULL,
            montant REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    if request.method == 'POST':
        # Récupération des données du formulaire
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = request.form['montant']
        conn.execute(
            'INSERT INTO encaissements (date, produit, montant) VALUES (?, ?, ?)',
            (date_encaissement, produit, montant)
        )
        conn.commit()
        flash("Encaissement ajouté", "success")
        return redirect(url_for('index'))
    encaissements = conn.execute('SELECT * FROM encaissements ORDER BY date DESC').fetchall()
    conn.close()
    # Date du jour au format YYYY-MM-DD pour le champ date
    current_date = date.today().strftime("%Y-%m-%d")
    return render_template('index.html', current_date=current_date, encaissements=encaissements)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = get_db_connection()
    encaissement = conn.execute('SELECT * FROM encaissements WHERE id = ?', (id,)).fetchone()
    if encaissement is None:
        flash("Encaissement non trouvé", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = request.form['montant']
        conn.execute(
            'UPDATE encaissements SET date = ?, produit = ?, montant = ? WHERE id = ?',
            (date_encaissement, produit, montant, id)
        )
        conn.commit()
        conn.close()
        flash("Encaissement modifié", "success")
        return redirect(url_for('index'))
    conn.close()
    return render_template('edit.html', encaissement=encaissement)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM encaissements WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Encaissement supprimé", "info")
    return redirect(url_for('index'))

@app.route('/totaux', methods=['GET'])
def totaux():
    # Par défaut, le mois courant au format "YYYY-MM"
    mois = request.args.get('mois', date.today().strftime("%Y-%m"))
    conn = get_db_connection()
    total_row = conn.execute(
        "SELECT SUM(montant) AS total FROM encaissements WHERE date LIKE ?",
        (mois + '%',)
    ).fetchone()
    conn.close()
    total = total_row["total"] if total_row["total"] is not None else 0.0
    return render_template('totaux.html', total=total, mois=mois)

@app.route('/export', methods=['GET'])
def export():
    conn = get_db_connection()
    rows = conn.execute("SELECT date, produit, montant FROM encaissements ORDER BY date DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Produit', 'Montant'])
    for row in rows:
        writer.writerow([row['date'], row['produit'], "%.2f" % row['montant']])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=encaissements.csv"})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
