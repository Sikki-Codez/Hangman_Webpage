from flask import Flask, render_template, session, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import os

app = Flask(__name__)
app.secret_key = "giki_coding_secret" 

# --- UPDATED DATABASE CONNECTION BLOCK ---
# Using pg8000 to bypass C++ build tool requirements on Windows
db_url = os.environ.get('DATABASE_URL', 'postgresql+pg8000://postgres:pgadmin4@localhost:5432/Hangman')

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
# -------------------------------------------

db = SQLAlchemy(app)

class Word(db.Model):
    __tablename__ = 'words'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)

@app.route('/')
def index():
    if 'word' not in session:
        return render_template('index.html', show_menu=True)

    if 'streak' not in session:
        session['streak'] = 0

    display_word = ""
    for char in session['word']:
        if char == " ":
            display_word += "&nbsp;&nbsp;" 
        elif char in session['guessed']:
            display_word += char + " "
        else:
            display_word += "_ "

    if "_" not in display_word.replace("&nbsp;", "") and not session['game_over']:
        session['win'] = True
        session['game_over'] = True
        session['last_action'] = 'win' 
        session['streak'] += 1
        session.modified = True
    elif session['mistakes'] >= 10 and not session['game_over']:
        session['game_over'] = True
        session['last_action'] = 'lose' 
        session['streak'] = 0
        session.modified = True

    sound_to_play = session.pop('last_action', None)

    return render_template('index.html', 
                           show_menu=False,
                           category=session.get('category'),
                           streak=session['streak'],
                           display=display_word, 
                           mistakes=session['mistakes'],
                           game_over=session['game_over'],
                           win=session['win'],
                           secret_word=session['word'],
                           guessed_letters=session['guessed'],
                           sound_to_play=sound_to_play)

@app.route('/start', methods=['POST'])
def start():
    selected_category = request.form.get('category')
    
    if selected_category:
        random_word = Word.query.filter_by(category=selected_category).order_by(db.func.random()).first()
        
        if random_word:
            session['word'] = random_word.word.lower()
            session['category'] = selected_category
            session['guessed'] = []
            session['mistakes'] = 0
            session['game_over'] = False 
            session['win'] = False
            
    return redirect(url_for('index'))

@app.route('/guess', methods=['POST'])
def guess():
    if not session.get('game_over'):
        letter = request.form.get('letter').lower()
        
        if letter and letter.isalpha() and letter not in session['guessed']:
            session['guessed'].append(letter)
            
            if letter in session['word']:
                session['last_action'] = 'correct'
            else:
                session['mistakes'] += 1
                session['last_action'] = 'wrong'
                
            session.modified = True 
                
    return redirect(url_for('index'))

@app.route('/reset')
def reset():
    current_streak = session.get('streak', 0)
    session.clear() 
    session['streak'] = current_streak
    
    return redirect(url_for('index'))

# Create the database tables before running the app
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)