import os
import whisper
import subprocess
import uuid 
import math
from datetime import datetime # NEW IMPORTS
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
import soundfile as sf
import noisereduce as nr
from gtts import gTTS 
import functools
import google.generativeai as genai
import stripe
from itsdangerous import URLSafeTimedSerializer

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_that_you_should_change'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURATION ---
stripe.api_key = "sk_test_YOUR_STRIPE_SECRET_KEY" 
YOUR_DOMAIN = 'http://127.0.0.1:5000'
GEMINI_API_KEY = "AIzaSyB57cj-I9aVGJKlp_0pzyW3R4wpl5_aDDM" 

UPLOAD_FOLDER = 'uploads'
DUBBED_FOLDER = 'dubbed' 
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(DUBBED_FOLDER): os.makedirs(DUBBED_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DUBBED_FOLDER'] = DUBBED_FOLDER

GOGGLE_TTS_SUPPORTED_LANGS = {
    'en', 'hi', 'bn', 'gu', 'kn', 'ml', 'mr', 'ta', 'te', 'ur', 
    'fr', 'es', 'de', 'it', 'ja', 'ko', 'pt', 'ru', 'zh-CN'
}

# --- Init Gemini ---
if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    print("WARNING: GEMINI_API_KEY is not set.")
    gemini_chat_session = None; gemini_model_pro = None
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        CHATBOT_SYSTEM_PROMPT = "You are 'Dubify Helper'. Help users understand how to use this site. Be concise."
        gemini_model_chat = genai.GenerativeModel('models/gemini-flash-latest', system_instruction=CHATBOT_SYSTEM_PROMPT)
        gemini_chat_session = gemini_model_chat.start_chat(history=[])
        gemini_model_pro = genai.GenerativeModel('models/gemini-pro-latest')
        print("Gemini models initialized.")
    except Exception as e:
        print(f"Error initializing Gemini: {e}")
        gemini_chat_session = None; gemini_model_pro = None

# --- Init Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_pro = db.Column(db.Boolean, default=False)
    # Relationship to Projects
    projects = db.relationship('Project', backref='author', lazy=True)

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)
    def get_reset_token(self, expires_sec=1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')
    @staticmethod
    def verify_reset_token(token):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try: user_id = s.loads(token, salt='password-reset-salt', max_age=1800)['user_id']
        except: return None
        return db.session.get(User, user_id)

# NEW: Project Model for History
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    original_filename = db.Column(db.String(100), nullable=False)
    dubbed_filename = db.Column(db.String(100), nullable=True) # Nullable if dub fails
    subtitle_filename = db.Column(db.String(100), nullable=False)
    source_lang = db.Column(db.String(10), nullable=False)
    target_lang = db.Column(db.String(10), nullable=False)
    file_type = db.Column(db.String(10), nullable=False) # 'video' or 'audio'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

# --- Forms ---
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')
    def validate_username(self, u): 
        if User.query.filter_by(username=u.data).first(): raise ValidationError('Username taken.')
    def validate_email(self, e): 
        if User.query.filter_by(email=e.data).first(): raise ValidationError('Email used.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')
    def validate_email(self, e):
        if User.query.filter_by(email=e.data).first() is None: raise ValidationError('No account with that email.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Update Password')

# --- Load Whisper ---
try:
    transcription_model = whisper.load_model("medium")
    print("Whisper loaded.")
except Exception as e: print(f"Error loading Whisper: {e}")

# ================= ROUTES =================

@app.route('/')
@login_required 
def index(): return render_template('index.html', title='Home')

# NEW: Dashboard Route
@app.route('/dashboard')
@login_required
def dashboard():
    # Get all projects for current user, newest first
    user_projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.date_posted.desc()).all()
    return render_template('dashboard.html', title='My Dashboard', projects=user_projects)

@app.route('/live')
@login_required
def live(): return render_template('live.html', title='Live Translate')

@app.route('/features')
def features(): return render_template('features.html', title='Features')
@app.route('/pricing')
def pricing(): return render_template('pricing.html', title='Pricing')
@app.route('/contact')
def contact(): return render_template('contact.html', title='Contact')

# --- Auth Routes ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data); db.session.add(user); db.session.commit()
        flash('Account created!', 'success'); return redirect(url_for('login'))
    return render_template('signup.html', title='Sign Up', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next = request.args.get('next'); return redirect(next) if next else redirect(url_for('index'))
        else: flash('Login failed.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        token = user.get_reset_token()
        print(f"\n=== RESET LINK: {url_for('reset_token', token=token, _external=True)} ===\n")
        flash('Check terminal for reset link.', 'info'); return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated: return redirect(url_for('index'))
    user = User.verify_reset_token(token)
    if not user: flash('Invalid token', 'warning'); return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data); db.session.commit()
        flash('Password updated!', 'success'); return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data): flash('Incorrect password', 'danger')
        else:
            current_user.set_password(form.new_password.data); db.session.commit()
            flash('Password changed.', 'success'); return redirect(url_for('index'))
    return render_template('change_password.html', title='Change Password', form=form)

# --- Payment ---
@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': 'Dubify Pro'}, 'unit_amount': 1000}, 'quantity': 1}],
            mode='payment', success_url=YOUR_DOMAIN+'/success', cancel_url=YOUR_DOMAIN+'/cancel',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e: return str(e)

@app.route('/success')
@login_required
def success(): current_user.is_pro = True; db.session.commit(); return render_template('success.html', title='Success')
@app.route('/cancel')
def cancel(): return render_template('cancel.html', title='Cancelled')

# ================= APIs =================

# 1. Chat
@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    if not gemini_chat_session: return jsonify({"error": "Chatbot unavailable"}), 500
    data = request.get_json(); msg = data.get('message')
    if not msg: return jsonify({"error": "No message"}), 400
    try: return jsonify({"reply": gemini_chat_session.send_message(msg).text})
    except Exception as e: return jsonify({"error": str(e)}), 500

# 2. Live Translate (RTVT)
@app.route('/api/live', methods=['POST'])
@login_required
def live_translate():
    if 'audio' not in request.files: return jsonify({"error": "No audio"}), 400
    audio = request.files['audio']
    tgt_name = request.form.get('target_lang_name', 'Hindi')
    tgt_code = request.form.get('target_lang_code', 'hi')

    temp_webm = os.path.join(app.config['UPLOAD_FOLDER'], f"live_{uuid.uuid4()}.webm")
    wav_path = os.path.join(app.config['UPLOAD_FOLDER'], f"live_{uuid.uuid4()}.wav")
    audio.save(temp_webm)

    try:
        subprocess.run(["ffmpeg", "-i", temp_webm, "-ac", "1", "-ar", "16000", "-y", wav_path], check=True, capture_output=True)
        result = transcription_model.transcribe(wav_path, fp16=False)
        orig_text = result['text'].strip()
        if not orig_text: return jsonify({"original": "", "translated": "No speech."})

        if not gemini_model_pro: raise Exception("Gemini unavailable")
        prompt = f"Translate to {tgt_name}. Return ONLY translation:\n\n{orig_text}"
        trans_text = gemini_model_pro.generate_content(prompt).text.strip()

        audio_url = None
        gtts_code = tgt_code.split('-')[0]
        if gtts_code in GOGGLE_TTS_SUPPORTED_LANGS:
            tts_name = f"tts_live_{uuid.uuid4()}.mp3"
            tts_path = os.path.join(app.config['DUBBED_FOLDER'], tts_name)
            gTTS(trans_text, lang=gtts_code).save(tts_path)
            audio_url = f"/download/{tts_name}"

        if os.path.exists(temp_webm): os.remove(temp_webm)
        if os.path.exists(wav_path): os.remove(wav_path)
        
        return jsonify({"original": orig_text, "translated": trans_text, "audio_url": audio_url})
    except Exception as e: return jsonify({"error": str(e)}), 500

# 3. Batch Transcribe
@app.route('/api/transcribe', methods=['POST'])
@login_required
def transcribe_audio():
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No file"}), 400
    if file:
        ext = os.path.splitext(file.filename)[1]
        unique = f"{uuid.uuid4()}{ext}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], unique)
        file.save(path)
        try:
            std_path = os.path.join(app.config['UPLOAD_FOLDER'], f"std_{uuid.uuid4()}.wav")
            clean_path = os.path.join(app.config['UPLOAD_FOLDER'], f"clean_{uuid.uuid4()}.wav")
            subprocess.run(["ffmpeg", "-i", path, "-ac", "1", "-ar", "16000", "-y", std_path], check=True, capture_output=True)
            data, rate = sf.read(std_path)
            reduced = nr.reduce_noise(y=data, sr=rate)
            sf.write(clean_path, reduced, rate)
            
            res = transcription_model.transcribe(clean_path, fp16=False)
            os.remove(std_path); os.remove(clean_path)
            return jsonify({"transcription": res['text'], "original_filename": unique, "detected_language": res['language'], "segments": res['segments']})
        except Exception as e: return jsonify({"error": str(e)}), 500

# 4. Batch Translate
@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text():
    if not gemini_model_pro: return jsonify({"error": "Translation unavailable"}), 500
    data = request.get_json()
    text = data.get('text'); src = data.get('source_lang_name'); tgt = data.get('target_lang_name')
    if not text: return jsonify({"error": "No text"}), 400
    if src.lower() == tgt.lower(): return jsonify({"translated_text": text})
    try:
        prompt = f"Translate from {src} to {tgt}. Return ONLY translation:\n\n{text}"
        return jsonify({"translated_text": gemini_model_pro.generate_content(prompt).text.strip()})
    except Exception as e: return jsonify({"error": str(e)}), 500

# 5. Batch Dubbing (UPDATED to Save to Database)
def format_time(s):
    h = math.floor(s / 3600); s %= 3600; m = math.floor(s / 60); s %= 60; ms = round((s - math.floor(s)) * 1000); s = math.floor(s)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

@app.route('/api/dub', methods=['POST'])
@login_required
def dub_video():
    data = request.get_json()
    text = data.get('text'); fname = data.get('filename'); tgt = data.get('target_lang_code')
    src_code = data.get('source_lang_code', 'Unknown') # NEW: Get source code for DB
    
    if not text or not fname or not tgt: return jsonify({"error": "Missing data"}), 400
    
    gtts_code = tgt.split('-')[0]
    base_uuid = uuid.uuid4()
    orig_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    sub_name = f"sub_{base_uuid}.srt"; sub_path = os.path.join(app.config['DUBBED_FOLDER'], sub_name)
    dub_name = None; ftype = "none"

    try:
        if gtts_code in GOGGLE_TTS_SUPPORTED_LANGS:
            tts_path = os.path.join(app.config['UPLOAD_FOLDER'], f"tts_{base_uuid}.mp3")
            gTTS(text, lang=gtts_code).save(tts_path)
            res = transcription_model.transcribe(tts_path, language=gtts_code, fp16=False)
            srt = ""
            for i, s in enumerate(res['segments']):
                srt += f"{i+1}\n{format_time(s['start'])} --> {format_time(s['end'])}\n{s['text'].strip()}\n\n"
            with open(sub_path, 'w', encoding='utf-8') as f: f.write(srt)
            
            ext = os.path.splitext(fname)[1].lower()
            if ext in ['.mp4', '.mkv', '.mov', '.avi']:
                dub_name = f"dub_{base_uuid}.mp4"; dub_path = os.path.join(app.config['DUBBED_FOLDER'], dub_name)
                subprocess.run(["ffmpeg", "-i", orig_path, "-i", tts_path, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", dub_path], check=True)
                ftype = "video"
            else:
                dub_name = f"dub_{base_uuid}.mp3"; dub_path = os.path.join(app.config['DUBBED_FOLDER'], dub_name)
                os.rename(tts_path, dub_path)
                ftype = "audio"
            
            if ftype == "video" and os.path.exists(tts_path): os.remove(tts_path)
        else:
            with open(sub_path, 'w', encoding='utf-8') as f: f.write(f"1\n00:00:01,000 --> 00:00:10,000\n{text}")
            # We continue to save the Project record even if audio fails
            ftype = "subtitle_only"
            
        # NEW: Save to Database
        new_project = Project(
            original_filename=fname,
            dubbed_filename=dub_name,
            subtitle_filename=sub_name,
            source_lang=src_code,
            target_lang=tgt,
            file_type=ftype,
            author=current_user
        )
        db.session.add(new_project)
        db.session.commit()
            
        os.remove(orig_path)
        return jsonify({"dubbed_filename": dub_name, "subtitle_filename": sub_name, "file_type": ftype})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
@login_required
def download_file(filename): return send_from_directory(app.config['DUBBED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, port=5000)