from flask import Flask, render_template, request, redirect, flash, send_from_directory, session, url_for
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "supersecretkey"

# Upload directory setup
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# MongoDB Atlas connection
client = MongoClient("mongodb+srv://securevault:sai@cluster0.sy8yc5v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['securevault']
files_collection = db['files']
texts_collection = db['texts']
vaults_collection = db['vaults']

# ✅ Ensure TTL Index (30 Days = 2592000 seconds)
files_collection.create_index([("createdAt", 1)], expireAfterSeconds=2592000)
texts_collection.create_index([("createdAt", 1)], expireAfterSeconds=2592000)

# =========================== Routes ===========================

@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pin = request.form.get('vault_password')
        if not pin:
            flash("PIN is required.")
            return redirect(url_for('login'))

        vault = vaults_collection.find_one({'pin': pin})
        if not vault:
            vaults_collection.insert_one({'pin': pin})
            flash("New vault created!")

        session['authenticated'] = True
        session['pin'] = pin
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('pin', None)
    flash("Logged out successfully.")
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload():
    if not session.get('authenticated'):
        return redirect(url_for('login'))

    pin = session.get('pin')
    file = request.files.get('file')
    code = request.form.get('code')

    existing_vault = vaults_collection.find_one({'pin': pin})
    if not existing_vault:
        vaults_collection.insert_one({'pin': pin})

    if file and file.filename != '':
        filename = secure_filename(f"{pin}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not files_collection.find_one({'pin': pin, 'filename': filename}):
            file.save(filepath)
            files_collection.insert_one({
                'pin': pin,
                'filename': filename,
                'createdAt': datetime.utcnow()  # ✅ TTL field
            })
            flash("File uploaded successfully!")
        else:
            flash("This file already exists in the vault.")

    if code.strip():
        texts_collection.insert_one({
            'pin': pin,
            'content': code,
            'createdAt': datetime.utcnow()  # ✅ TTL field
        })
        flash("Code saved to vault!")

    return redirect('/')

@app.route('/view')
def view():
    if not session.get('authenticated'):
        return redirect(url_for('login'))

    pin = session.get('pin')
    existing_vault = vaults_collection.find_one({'pin': pin})
    if not existing_vault:
        flash('PIN not found. Create it first by uploading.')
        return redirect('/')

    files = files_collection.find({'pin': pin})
    texts = texts_collection.find({'pin': pin})
    file_list = [f['filename'] for f in files]
    code_list = [t['content'] for t in texts]

    return render_template('view.html', files=file_list, pin=pin, code="\n\n---\n\n".join(code_list))

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete_file/<filename>')
def delete_file(filename):
    pin = session.get('pin')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if files_collection.find_one({'pin': pin, 'filename': filename}):
        try:
            os.remove(file_path)
        except:
            pass
        files_collection.delete_one({'pin': pin, 'filename': filename})
        flash("File deleted successfully.")
    else:
        flash("File not found in database.")
    return redirect(url_for('view'))

@app.route('/update_note', methods=['POST'])
def update_note():
    pin = session.get('pin')
    updated_code = request.form.get('updated_code')
    texts_collection.delete_many({'pin': pin})
    texts_collection.insert_one({
        'pin': pin,
        'content': updated_code,
        'createdAt': datetime.utcnow()  # ✅ TTL field
    })
    flash("Notes updated successfully.")
    return redirect(url_for('view'))

@app.route('/delete_note', methods=['POST'])
def delete_note():
    pin = session.get('pin')
    texts_collection.delete_many({'pin': pin})
    flash("Notes deleted successfully.")
    return redirect(url_for('view'))

# ✅ About Page
@app.route('/about')
def about():
    return render_template('about.html')

# ============================ Run App ============================
if __name__ == '__main__':
    app.run(debug=True)
