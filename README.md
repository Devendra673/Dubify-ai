🎬 Dubify AI
Dubify AI is an intelligent video and audio dubbing platform that leverages AI to transcribe, translate, and dub content across multiple languages. Built with Flask, Whisper, and Google's Gemini AI, it provides both batch processing and real-time translation capabilities.

✨ Features
🎯 Core Functionality
Batch Video/Audio Dubbing: Upload videos or audio files and get them dubbed in your target language
Real-Time Translation: Live voice translation with audio playback
AI-Powered Transcription: Automatic speech-to-text using OpenAI's Whisper (medium model)
Smart Translation: Powered by Google Gemini AI for accurate translations
Subtitle Generation: Automatic SRT subtitle file creation with precise timestamps
Noise Reduction: Audio preprocessing for better transcription accuracy
🌍 Language Support
Supports 19+ languages including:

English (en)
Hindi (hi), Bengali (bn), Gujarati (gu), Kannada (kn)
Malayalam (ml), Marathi (mr), Tamil (ta), Telugu (te), Urdu (ur)
French (fr), Spanish (es), German (de), Italian (it)
Japanese (ja), Korean (ko), Portuguese (pt), Russian (ru), Chinese (zh-CN)
👤 User Management
User registration and authentication
Password reset functionality
User dashboard with project history
Pro membership integration via Stripe
💬 AI Assistant
Built-in chatbot ("Dubify Helper") powered by Gemini Flash
Context-aware help and guidance
🛠️ Technology Stack
Backend: Flask (Python)
AI/ML:
OpenAI Whisper (transcription)
Google Gemini AI (translation & chat)
Google Text-to-Speech (gTTS)
Database: SQLAlchemy with SQLite
Audio Processing:
FFmpeg
soundfile
noisereduce
Authentication: Flask-Login
Payment: Stripe
Forms: Flask-WTF, WTForms
📋 Prerequisites
Python 3.8+
FFmpeg installed and accessible in PATH
Google Gemini API key
Stripe API keys (for payment processing)
🚀 Installation
Clone the repository
git clone https://github.com/Devendra673/Dubify-ai.git
cd Dubify-ai
Install dependencies
pip install flask flask-sqlalchemy flask-login flask-wtf
pip install openai-whisper soundfile noisereduce gtts
pip install google-generativeai stripe itsdangerous
Install FFmpeg

Windows: Download from ffmpeg.org or use the included ffmpeg.exe
Linux: sudo apt install ffmpeg
macOS: brew install ffmpeg
Configure API Keys

Edit app.py and replace the placeholder values:

# Line 29: Add your Stripe secret key
stripe.api_key = "sk_test_YOUR_STRIPE_SECRET_KEY"

# Line 31: Add your Gemini API key
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# Line 24: Change the secret key
app.config['SECRET_KEY'] = 'your_unique_secret_key'
Initialize the database
python app.py
The database will be automatically created on first run.

🎮 Usage
Starting the Server
python app.py
The application will run on http://127.0.0.1:5000

Workflow
Sign Up/Login: Create an account or log in
Upload Media: Navigate to the home page and upload your video/audio file
Select Languages: Choose source and target languages
Process: Click to transcribe, translate, and dub
Download: Get your dubbed file and subtitles
View History: Check your past projects in the dashboard
Real-Time Translation
Go to the Live Translate page
Allow microphone access
Select target language
Speak into your microphone
Get instant translation with audio playback
📁 Project Structure
Dubify-ai/
├── app.py                  # Main application file
├── check_models.py         # Model verification utility
├── ffmpeg.exe             # FFmpeg executable (Windows)
├── .gitignore
├── templates/             # HTML templates
│   ├── _base. html         # Base template
│   ├── index.html         # Main dubbing interface
│   ├── live.html          # Live translation interface
│   ├── dashboard.html     # User dashboard
│   ├── login.html         # Login page
│   ├── signup.html        # Registration page
│   └── ...                # Other templates
├── static/                # Static files (CSS, JS, images)
├── uploads/               # Temporary upload storage
├── dubbed/                # Processed output files
└── instance/              # Database files
    └── users. db           # SQLite database
🔒 Security Notes
⚠️ Important: Before deploying to production:

Change the SECRET_KEY in app.py
Use environment variables for API keys
Enable HTTPS
Use a production-grade database (PostgreSQL, MySQL)
Set debug=False in production
Implement proper error handling and logging
Add rate limiting and input validation
📊 Database Models
User
id: Primary key
username: Unique username
email: Unique email
password_hash: Hashed password
is_pro: Pro membership status
Project
id: Primary key
date_posted: Timestamp
original_filename: Uploaded file name
dubbed_filename: Output dubbed file
subtitle_filename: Generated SRT file
source_lang: Source language code
target_lang: Target language code
file_type: video/audio/subtitle_only
user_id: Foreign key to User
🌐 API Endpoints
Endpoint	Method	Description
/api/transcribe	POST	Transcribe audio/video
/api/translate	POST	Translate text
/api/dub	POST	Generate dubbed video/audio
/api/live	POST	Real-time voice translation
/api/chat	POST	AI chatbot interaction
/download/<filename>	GET	Download processed files
🎯 Features Roadmap
 Support for more languages
 Voice cloning for better dubbing
 Batch processing for multiple files
 Advanced subtitle customization
 API access for developers
 Mobile app integration
🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

📝 License
This project is currently unlicensed. Please add a LICENSE file to specify terms of use.

🐛 Known Issues
API keys are hardcoded (should use environment variables)
Limited error handling in some routes
No file size limits implemented
Temporary files cleanup could be improved

GitHub: @Devendra673
🙏 Acknowledgments
OpenAI Whisper for transcription
Google Gemini AI for translation
Flask community for excellent documentation
All open-source contributors
Note: This is a development version. Make sure to properly configure all API keys and security settings before deploying to production.
