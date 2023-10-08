# import os
# import psycopg2
# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
# from flask_migrate import Migrate

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import request, jsonify


app = Flask(__name__)
DATABASE_URI = 'postgresql://postgres:shreya@localhost:5432/postgres'
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
db = SQLAlchemy(app)
migrate = Migrate(app, db)
    

class ReportModel(db.Model):
    __tablename__ = 'reports'

    report_id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer)
    uptime_last_hour = db.Column(db.Integer())
    uptime_last_day = db.Column(db.Integer())
    uptime_last_week = db.Column(db.Integer())
    downtime_last_hour = db.Column(db.Integer())
    downtime_last_day = db.Column(db.Integer())
    downtime_last_week = db.Column(db.Integer())

    def __init__(self, store_id, uptime_last_hour, uptime_last_day, uptime_last_week, downtime_last_hour, downtime_last_day, downtime_last_week ):
        self.store_id = store_id
        self.uptime_last_hour = uptime_last_hour
        self.uptime_last_day = uptime_last_day
        self.uptime_last_week = uptime_last_week
        self.downtime_last_day = downtime_last_day
        self.downtime_last_hour = downtime_last_hour
        self.downtime_last_week = downtime_last_week


    def __repr__(self):
        return f"<Store {self.store_id}>"


# FUNCTIONS
@app.route('/')
def hello_world():
    return 'Hello, Flask!'
    
# handle reports 
@app.route('/trigger_report', methods=['POST', 'GET']) # type: ignore
def trigger_report():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            new_report = ReportModel(
                store_id = data['store_id'],
                uptime_last_hour = data['uptime_last_hour'],
                uptime_last_day = data['uptime_last_day'],
                uptime_last_week = data['uptime_last_week'],
                downtime_last_hour = data['downtime_last_hour'],
                downtime_last_day = data['downtime_last_day'],
                downtime_last_week = data['downtime_last_week'],
                )
           
            db.session.add(new_report)
            db.session.commit()
            return {"message": f"report {new_report.store_id} has been created successfully."}
        else:
            return {"error": "The request payload is not in JSON format"}

    elif request.method == 'GET':
        reports = ReportModel.query.all()
        results = [
            {
                "report_id": report.report_id,
                "store_id" : report.store_id,
                "uptime_last_hour" : report.uptime_last_hour,
                "uptime_last_day" : report.uptime_last_day,
                "uptime_last_week" : report.uptime_last_week,
                "downtime_last_hour" : report.downtime_last_hour,
                "downtime_last_day" : report.downtime_last_day,
                "downtime_last_week" : report.downtime_last_week,
            } for report in reports]

        return {"count": len(results), "reports": results}

@app.route('/get_report/<string:report_id>', methods=[ 'GET']) # type: ignore
def get_report(report_id):
    if request.method != 'GET':
        return {"Invalid request"}
    
    report = ReportModel.query.get(report_id)

    if report:
        result = {
            "report_id": report.report_id,
            "store_id": report.store_id,
            "uptime_last_hour": report.uptime_last_hour,
            "uptime_last_day": report.uptime_last_day,
            "uptime_last_week": report.uptime_last_week,
            "downtime_last_hour": report.downtime_last_hour,
            "downtime_last_day": report.downtime_last_day,
            "downtime_last_week": report.downtime_last_week,
        }
        return jsonify(result)
    else:
        return {"message": "Report not found"}, 404




if __name__ == '__main__':
    app.run(debug=True)


# my_project/
#     app.py
#     config.py
#     requirements.txt
#     static/
#     templates/
#     views/

