import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import csv
import io
from functools import wraps
# import sqlite3  <-- Plus nécessaire

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'votre_cle_secrete')

# Configuration de la base de données pour PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://encaissement_user:JwxoKC6AgNPx2GYdjmSo13R0zKacCWRi@dpg-cuqrghdumphs73evdis0-a.oregon-postgres.render.com/encaissement')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Encaissement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)  # Format YYYY-MM-DD
    produit = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Veuillez vous connecter", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# La fonction get_db_connection() n'est plus nécessaire avec SQLAlchemy
# def get_db_connection():
#     conn = sqlite3.connect("encaissement.db")
#     conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par leur nom
#     return conn

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # Récupération des données du formulaire
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = float(request.form['montant'])
        # Création d'une instance du modèle Encaissement
        new_enc = Encaissement(date=date_encaissement, produit=produit, montant=montant)
        db.session.add(new_enc)
        db.session.commit()
        flash("Encaissement ajouté", "success")
        return redirect(url_for('index'))
    
    # Pour GET, récupération des paramètres de filtrage (dates)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        limit = 20

    # Construction de la requête SQLAlchemy en fonction des filtres
    query = Encaissement.query
    if start_date:
        query = query.filter(Encaissement.date >= start_date)
    if end_date:
        query = query.filter(Encaissement.date <= end_date)
    encaissements = query.order_by(Encaissement.date.desc()).limit(limit).all()
    
    current_date = date.today().strftime("%Y-%m-%d")
    return render_template('index.html',
                           current_date=current_date,
                           encaissement=encaissements,
                           start_date=start_date,
                           end_date=end_date,
                           selected_limit=limit)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    enc = Encaissement.query.get(id)
    if enc is None:
        flash("Encaissement non trouvé", "danger")
        return redirect(url_for('index'))
    if request.method == 'POST':
        enc.date = request.form['date']
        enc.produit = request.form['produit']
        enc.montant = float(request.form['montant'])
        db.session.commit()
        flash("Encaissement modifié", "success")
        return redirect(url_for('index'))
    return render_template('edit.html', encaissement=enc)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    enc = Encaissement.query.get(id)
    if enc:
        db.session.delete(enc)
        db.session.commit()
        flash("Encaissement supprimé", "info")
    return redirect(url_for('index'))

@app.route('/totaux', methods=['GET'])
def totaux():
    mois = request.args.get('mois', date.today().strftime("%Y-%m"))
    total = db.session.query(db.func.sum(Encaissement.montant)).filter(Encaissement.date.like(mois + '%')).scalar() or 0.0
    return render_template('totaux.html', total=total, mois=mois)

@app.route('/export', methods=['GET'])
def export():
    encaissements = Encaissement.query.order_by(Encaissement.date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Produit', 'Montant'])
    for enc in encaissements:
        writer.writerow([enc.date, enc.produit, "%.2f" % enc.montant])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=encaissement.csv"})

# Routes de connexion/déconnexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password':
            session['logged_in'] = True
            flash("Connexion réussie", "success")
            return redirect(url_for('index'))
        else:
            flash("Identifiants incorrects", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Déconnexion réussie", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
