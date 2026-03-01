from flask import Flask, render_template, session, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
import os  # <-- ADD THIS IMPORT

app = Flask(__name__)
app.secret_key = "giki_coding_secret" 

# --- UPDATE THIS DATABASE CONNECTION BLOCK ---
# It tries to find a live URL first. If it can't, it falls back to your local pgAdmin4 setup.
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:pgadmin4@localhost:5432/Hangman')

# Render sometimes uses 'postgres://' which SQLAlchemy doesn't like, so we fix it automatically:
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
# -------------------------------------------

db = SQLAlchemy(app)

# The updated Model matching your new table
class Word(db.Model):
    __tablename__ = 'words'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)

@app.route('/')
def index():
    if 'word' not in session:
        return render_template('index.html', show_menu=True)

    # Make sure the streak exists in the session
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

    # Check Win/Loss and update the streak
    if "_" not in display_word.replace("&nbsp;", "") and not session['game_over']:
        session['win'] = True
        session['game_over'] = True
        session['last_action'] = 'win' 
        session['streak'] += 1  # <-- INCREASE STREAK
        session.modified = True
    elif session['mistakes'] >= 10 and not session['game_over']:
        session['game_over'] = True
        session['last_action'] = 'lose' 
        session['streak'] = 0   # <-- RESET STREAK
        session.modified = True

    sound_to_play = session.pop('last_action', None)

    return render_template('index.html', 
                           show_menu=False,
                           category=session.get('category'),
                           streak=session['streak'], # <-- PASS STREAK TO HTML
                           display=display_word, 
                           mistakes=session['mistakes'],
                           game_over=session['game_over'],
                           win=session['win'],
                           secret_word=session['word'],
                           guessed_letters=session['guessed'],
                           sound_to_play=sound_to_play)
# NEW ROUTE: Handles the category selection and starts the game
@app.route('/start', methods=['POST'])
def start():
    selected_category = request.form.get('category')
    
    if selected_category:
        # Pull a random word ONLY from the selected category
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
    # Save the current streak before wiping the session
    current_streak = session.get('streak', 0)
    
    session.clear() 
    
    # Put the streak back into the fresh session
    session['streak'] = current_streak
    
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)