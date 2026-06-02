from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import google.generativeai as genai
import random
import os
import json

# Load environment variables from the .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = "giki_coding_secret" 

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'postgresql+pg8000://postgres:pgadmin4@localhost:5432/Hangman')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
db = SQLAlchemy(app)

class Word(db.Model):
    __tablename__ = 'words'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)

@app.route('/')
def index():
    if 'word' not in session:
        # Fetch all unique categories currently in the database to display
        available_categories = [cat[0] for cat in db.session.query(Word.category).distinct().all()]
        return render_template('index.html', show_menu=True, available_categories=available_categories)

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

@app.route('/generate', methods=['POST'])
def generate():
    category_name = request.form.get('category_name').strip().title()
    word_count = int(request.form.get('word_count') or 100)
    min_len = int(request.form.get('min_len') or 5)
    max_len = int(request.form.get('max_len') or 20)

    if not category_name:
        return redirect(url_for('index'))

    # CHECK 1: Does this category already exist in the database?
    existing_word = Word.query.filter_by(category=category_name).first()
    
    if not existing_word:
        # If it doesn't exist, call the AI to generate it
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            Provide exactly {word_count} unique words related to the category '{category_name}'. 
            Rules:
            1. Every word must be between {min_len} and {max_len} letters long.
            2. Only use alphabetical characters (no numbers, spaces, or hyphens).
            3. Output NOTHING EXCEPT a raw JSON array of strings. Do not use markdown blocks.
            Example: ["wordone", "wordtwo", "wordthree"]
            """
            
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Clean up markdown if the AI hallucinated it
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()

            generated_words = json.loads(raw_text)

            # Clean the data and save to the database
            valid_words = []
            for w in generated_words:
                w = w.lower().strip()
                if w.isalpha() and min_len <= len(w) <= max_len:
                    valid_words.append(Word(word=w, category=category_name))
            
            if valid_words:
                db.session.bulk_save_objects(valid_words)
                db.session.commit()
            else:
                print("AI failed to generate valid words.")
                return redirect(url_for('index'))

        except Exception as e:
            print(f"Error generating words: {e}")
            return redirect(url_for('index'))

    # Start the game with the newly generated (or previously existing) category
    random_word = Word.query.filter_by(category=category_name).order_by(db.func.random()).first()
    
    if random_word:
        session['word'] = random_word.word.lower()
        session['category'] = category_name
        session['guessed'] = []
        session['mistakes'] = 0
        session['game_over'] = False 
        session['win'] = False

    return redirect(url_for('index'))

@app.route('/delete_category/<category_name>', methods=['POST'])
def delete_category(category_name):
    Word.query.filter_by(category=category_name).delete()
    db.session.commit()
    return redirect(url_for('index'))

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

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)