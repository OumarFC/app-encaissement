import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import csv
import io
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate


app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'votre_cle_secrete')

# Configuration de la base de données pour PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://encaissement_user:JwxoKC6AgNPx2GYdjmSo13R0zKacCWRi@dpg-cuqrghdumphs73evdis0-a.oregon-postgres.render.com/encaissement')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Modèle pour les encaissements
class Encaissement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)  # Format YYYY-MM-DD
    produit = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    created_by = db.Column(db.String(50), nullable=True)  # Stocke l'identifiant de l'utilisateur

# Nouveau modèle pour le fond de caisse
class FondCaisse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fond = db.Column(db.Float, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Décorateur pour protéger les routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Veuillez vous connecter", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
    
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    # Récupérer l'utilisateur courant depuis la table User en fonction de la session
    current_username = session.get('username')
    user = User.query.filter_by(username=current_username).first()
    
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not user.check_password(current_password):
            flash("Le mot de passe actuel est incorrect.", "danger")
            return redirect(url_for('change_password'))
        if new_password != confirm_password:
            flash("Les nouveaux mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('change_password'))
        
        # Mise à jour du mot de passe
        user.set_password(new_password)
        db.session.commit()
        flash("Mot de passe modifié avec succès.", "success")
        return redirect(url_for('index'))
    
    return render_template('change_password.html')

# Route principale
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # Ajout d'un nouvel encaissement
        date_encaissement = request.form['date']
        produit = request.form['produit']
        montant = float(request.form['montant'])
        new_enc = Encaissement(date=date_encaissement, produit=produit, montant=montant, created_by=session.get('username') )
        db.session.add(new_enc)
        db.session.commit()
        flash("Encaissement ajouté", "success")
        return redirect(url_for('index'))
    
    # Pour GET, définir par défaut le filtre sur la date du jour
    current_date = date.today().strftime("%Y-%m-%d")
    start_date = request.args.get('start_date', current_date)
    end_date = request.args.get('end_date', current_date)
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        limit = 20

    # Construction de la requête avec SQLAlchemy en fonction des filtres
    query = Encaissement.query.filter(Encaissement.date >= start_date,
                                       Encaissement.date <= end_date)
    # Tri par ID décroissant pour afficher les nouveaux en tête
    encaissements = query.order_by(Encaissement.id.desc()).limit(limit).all()
    
    return render_template('index.html',
                           current_date=current_date,
                           encaissement=encaissements,
                           start_date=start_date,
                           end_date=end_date,
                           selected_limit=limit)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    # Vérifier si l'utilisateur connecté est l'admin
    if session.get('username') != 'admin':
        flash("Accès refusé : seul l'administrateur peut modifier les enregistrements.", "danger")
        return redirect(url_for('index'))
    
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
@login_required
def delete(id):
    # Vérifier si l'utilisateur connecté est l'admin
    if session.get('username') != 'admin':
        flash("Accès refusé : seul l'administrateur peut supprimer les enregistrements.", "danger")
        return redirect(url_for('index'))
    
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

# Nouvelle route pour le Total Journalier et gestion du fond de caisse
@app.route('/journalier', methods=['GET', 'POST'])
@login_required
def journalier():
    current_date = date.today().strftime("%Y-%m-%d")
    today_total = db.session.query(db.func.sum(Encaissement.montant)).filter(Encaissement.date == current_date).scalar() or 0.0

    # Récupérer (ou créer) le fond de caisse
    fond_record = FondCaisse.query.first()
    if not fond_record:
        fond_record = FondCaisse(fond=0.0)
        db.session.add(fond_record)
        db.session.commit()

    if request.method == 'POST':
        # Seul l'admin peut modifier le fond de caisse
        if session.get('username') == 'admin':
            try:
                new_fond = float(request.form.get('fond_caisse'))
            except ValueError:
                new_fond = fond_record.fond
            fond_record.fond = new_fond
            db.session.commit()
            flash("Fond de caisse mis à jour", "success")
        else:
            flash("Accès refusé : seuls les administrateurs peuvent modifier le fond de caisse", "danger")
        return redirect(url_for('journalier'))
    
    return render_template('journalier.html', current_date=current_date, today_total=today_total, fond=fond_record.fond)

# Routes de connexion/déconnexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Vérification pour le compte admin (hardcodé)
        if username == 'admin' and password == 'Dyste1989$':
            session['logged_in'] = True
            session['username'] = username  # Stocker le nom d'utilisateur pour vérification ultérieure
            flash("Connexion réussie (admin)", "success")
            return redirect(url_for('index'))
        
        # Vérification dans la base de données pour un utilisateur enregistré
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = user.username
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        if not username or not password or not password_confirm:
            flash("Tous les champs sont obligatoires", "danger")
            return redirect(url_for('register'))
        if password != password_confirm:
            flash("Les mots de passe ne correspondent pas", "danger")
            return redirect(url_for('register'))
        # Vérifier si le nom d'utilisateur existe déjà
        if User.query.filter_by(username=username).first():
            flash("Ce nom d'utilisateur est déjà pris", "danger")
            return redirect(url_for('register'))
        # Créer le nouvel utilisateur
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Compte créé, vous pouvez maintenant vous connecter", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


if __name__ == '__main__':
    # Créez les tables si elles n'existent pas
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
