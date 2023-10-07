import os
import psycopg2
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'DATABASE_URI'

db = SQLAlchemy(app)


# FUNCTIONS
@app.route('/')
def hello_world():
    return 'Hello, Flask!'

@app.route('/trigger_report')
def trigger_report():
    return 'Trigger Report'

@app.route('/get_report')
def get_report():
    return 'Get Report'

if __name__ == '__main__':
    app.run(debug=True)
