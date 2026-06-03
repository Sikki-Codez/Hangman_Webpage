from flask import Flask, render_template, session, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from google import genai 
import random
import os
import json

# Load environment variables from the .env file
load_dotenv()

App = Flask(__name__)
App.secret_key = "giki_coding_secret" 

# Configure the NEW Gemini Client
try:
    Client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
except Exception as ErrorMsg:
    print(f"Failed to initialize Gemini Client: {ErrorMsg}. Check your .env file!")
    Client = None

# Database Configuration
DbUrl = os.environ.get('DATABASE_URL', 'postgresql+pg8000://postgres:pgadmin4@localhost:5432/Hangman')
if DbUrl.startswith("postgres://"):
    DbUrl = DbUrl.replace("postgres://", "postgresql+pg8000://", 1)

App.config['SQLALCHEMY_DATABASE_URI'] = DbUrl
Db = SQLAlchemy(App)

class Word(Db.Model):
    __tablename__ = 'words'
    Id = Db.Column(Db.Integer, primary_key=True)
    TargetWord = Db.Column(Db.String(100), nullable=False)
    Category = Db.Column(Db.String(50), nullable=False)

@App.route('/')
def Index():
    if 'word' not in session:
        AvailableCategories = [Cat[0] for Cat in Db.session.query(Word.Category).distinct().all()]
        return render_template('index.html', show_menu=True, available_categories=AvailableCategories)

    if 'streak' not in session:
        session['streak'] = 0

    DisplayWord = ""
    for Char in session['word']:
        if Char == " ":
            DisplayWord += "&nbsp;&nbsp;" 
        elif Char in session['guessed']:
            DisplayWord += Char + " "
        else:
            DisplayWord += "_ "

    if "_" not in DisplayWord.replace("&nbsp;", "") and not session['game_over']:
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

    SoundToPlay = session.pop('last_action', None)

    return render_template('index.html', 
                           show_menu=False,
                           category=session.get('category'),
                           streak=session['streak'],
                           display=DisplayWord, 
                           mistakes=session['mistakes'],
                           game_over=session['game_over'],
                           win=session['win'],
                           secret_word=session['word'],
                           guessed_letters=session['guessed'],
                           sound_to_play=SoundToPlay)

@App.route('/generate', methods=['POST'])
def Generate():
    CategoryName = request.form.get('category_name').strip().title()
    WordCount = int(request.form.get('word_count') or 100)
    MinLen = int(request.form.get('min_len') or 5)
    MaxLen = int(request.form.get('max_len') or 20)

    if not CategoryName or not Client:
        return redirect(url_for('Index'))

    ExistingWord = Word.query.filter_by(Category=CategoryName).first()
    
    if not ExistingWord:
        try:
            PromptText = f"""
            Provide exactly {WordCount} unique words related to the category '{CategoryName}'. 
            Rules:
            1. Every word must be between {MinLen} and {MaxLen} letters long.
            2. Only use alphabetical characters (no numbers, spaces, or hyphens).
            3. Output NOTHING EXCEPT a raw JSON array of strings. Do not use markdown blocks.
            Example: ["wordone", "wordtwo", "wordthree"]
            """
            
            # Using the NEW SDK syntax and the active model
            ResponseData = Client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=PromptText
            )
            RawText = ResponseData.text.strip()
            
            # Robust JSON extraction
            StartIdx = RawText.find('[')
            EndIdx = RawText.rfind(']') + 1
            
            if StartIdx != -1 and EndIdx != 0:
                JsonString = RawText[StartIdx:EndIdx]
                GeneratedWords = json.loads(JsonString)
            else:
                GeneratedWords = json.loads(RawText)

            ValidWords = []
            for SingleWord in GeneratedWords:
                SingleWord = str(SingleWord).lower().strip()
                if SingleWord.isalpha() and MinLen <= len(SingleWord) <= MaxLen:
                    ValidWords.append(Word(TargetWord=SingleWord, Category=CategoryName))
            
            if ValidWords:
                Db.session.bulk_save_objects(ValidWords)
                Db.session.commit()
            else:
                print("AI failed to generate valid words.")
                return redirect(url_for('Index'))

        except Exception as ErrorMsg:
            print(f"Error generating words: {ErrorMsg}")
            return str(ErrorMsg), 500

    RandomWord = Word.query.filter_by(Category=CategoryName).order_by(Db.func.random()).first()
    
    if RandomWord:
        session['word'] = RandomWord.TargetWord.lower()
        session['category'] = CategoryName
        session['guessed'] = []
        session['mistakes'] = 0
        session['game_over'] = False 
        session['win'] = False

    return redirect(url_for('Index'))

@App.route('/delete_category/<CategoryName>', methods=['POST'])
def DeleteCategory(CategoryName):
    Word.query.filter_by(Category=CategoryName).delete()
    Db.session.commit()
    return redirect(url_for('Index'))

@App.route('/start', methods=['POST'])
def Start():
    SelectedCategory = request.form.get('category')
    if SelectedCategory:
        RandomWord = Word.query.filter_by(Category=SelectedCategory).order_by(Db.func.random()).first()
        if RandomWord:
            session['word'] = RandomWord.TargetWord.lower()
            session['category'] = SelectedCategory
            session['guessed'] = []
            session['mistakes'] = 0
            session['game_over'] = False 
            session['win'] = False
            
    return redirect(url_for('Index'))

@App.route('/guess', methods=['POST'])
def Guess():
    if not session.get('game_over'):
        GuessedLetter = request.form.get('letter').lower()
        if GuessedLetter and GuessedLetter.isalpha() and GuessedLetter not in session['guessed']:
            session['guessed'].append(GuessedLetter)
            if GuessedLetter in session['word']:
                session['last_action'] = 'correct'
            else:
                session['mistakes'] += 1
                session['last_action'] = 'wrong'
            session.modified = True 
    return redirect(url_for('Index'))

@App.route('/reset')
def Reset():
    CurrentStreak = session.get('streak', 0)
    session.clear() 
    session['streak'] = CurrentStreak
    return redirect(url_for('Index'))

with App.app_context():
    Db.create_all()

if __name__ == '__main__':
    App.run(debug=True)