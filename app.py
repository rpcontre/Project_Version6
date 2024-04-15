from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime
from sqlalchemy import func


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = '34kjgoer0fw9'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

    #this didn't work , 
    #credits = db.Column(db.Integer, default=500)  # Start with 500 free coins

# Function to fetch fixture data from the provided website
def fetch_fixture_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to retrieve fixture data")
        return None
# Function to play the guessing game
def play_guessing_game(fixture_data, user_prediction):
    match = user_prediction['match']
    prediction = user_prediction['prediction']
    # to extract the match number from the selected match
    match_number = int(match.split()[-1]) - 1
    if isinstance(fixture_data, list):
        match_data = fixture_data[match_number]
        home_score = match_data["HomeTeamScore"]
        away_score = match_data["AwayTeamScore"]
        # to see if the result is available
        if home_score is None or away_score is None:
            match_date = datetime.strptime(match_data["DateUtc"], "%Y-%m-%d %H:%M:%S%z").date()
            return f"The result for this match will be available on {match_date}. Please try again later."
        if home_score > away_score:
            actual_result = "Home Win"
        elif home_score < away_score:
            actual_result = "Away Win"
        else:
            actual_result = "Draw"
        if prediction.lower() == actual_result.lower():
            result = "Correct!"
        else:
            result = f"Incorrect! Correct choice: {actual_result}"
    else:
        result = "Error: Could not process the match data."
    return result



def handle_bet(bet_amount, game_result):
    if session.get('credits', 0) < bet_amount:
        return "Not enough credits to place the bet."
    session['credits'] -= bet_amount  # Deduct the bet amount
    if game_result == "Correct!":
        session['credits'] += bet_amount * 2  # Double the bet amount for correct predictions
    return game_result



@app.route('/')
def index():
    """Render the welcome page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # to avoid case sensitive username: 
        username = request.form['username'].lower()
        hashed_password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        
        # Check if the username already exists in a case-insensitive manner
        existing_user = User.query.filter(func.lower(User.username) == func.lower(username)).first()
        if existing_user:
            return "This username is already taken. Please choose a different one."
        
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # not sure if i need lowercase here but it works so far...
        username = request.form['username'].lower()
        user = User.query.filter(func.lower(User.username) == func.lower(username)).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            # Initialize credits for the session only if they don't exist
            if 'credits' not in session:
                session['credits'] = 500
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid username or password'
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        # Set the initial credits to 500 when the user accesses the dashboard
        if 'credits' not in session:
            session['credits'] = 500

        url = "https://fixturedownload.com/feed/json/epl-2023"
        fixture_data = fetch_fixture_data(url)
        if fixture_data:
            fixtures = {f"Round {match['RoundNumber']} Match {i+1}": f"{match['HomeTeam']} vs {match['AwayTeam']}" for i, match in enumerate(fixture_data)}
            # here pass the credits from the session to the template
            return render_template('game.html', fixtures=fixtures, credits=session['credits'])
        else:
            return "Failed to fetch fixture data"
    else:
        return redirect(url_for('login'))


@app.route('/play_game', methods=['POST'])
def play_game():
    # Retrieve the user's prediction and bet amount from the form submission
    user_prediction = {
        'match': request.form['match'],
        'prediction': request.form['prediction']
    }
    bet_amount = int(request.form['bet'])  # 

    # to fetch the fixture data 
    url = "https://fixturedownload.com/feed/json/epl-2023"
    fixture_data = fetch_fixture_data(url)

    # Check if fixture data is available
    if fixture_data:
        
        game_result = play_guessing_game(fixture_data, user_prediction)

        # Handle the bet and update the user's credits
        feedback = handle_bet(bet_amount, game_result)  # 

        
        return render_template('feedback.html', feedback=feedback, credits=session.get('credits', 0))
    else:
        
        return "Failed to fetch fixture data"


@app.route('/logout')
def logout():
    # Clear the user's session, which includes the credits
    session.clear()
    # Redirect to the welcome page or login page
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
