# import os
# import psycopg2
# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
# from flask_migrate import Migrate
import os
import csv
import time
from threading import Thread
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import request, jsonify, send_file, Response
import pandas as pd
import io
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DATABASE_URI = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# chunksize = 1000

DAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


class ReportModel(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer)
    uptime_last_hour = db.Column(db.Integer())
    uptime_last_day = db.Column(db.Integer())
    uptime_last_week = db.Column(db.Integer())
    downtime_last_hour = db.Column(db.Integer())
    downtime_last_day = db.Column(db.Integer())
    downtime_last_week = db.Column(db.Integer())
    status = db.Column(db.String())

    def __init__(
        self,
        store_id,
        uptime_last_hour,
        uptime_last_day,
        uptime_last_week,
        downtime_last_hour,
        downtime_last_day,
        downtime_last_week,
        status,
    ):
        self.store_id = store_id
        self.uptime_last_hour = uptime_last_hour
        self.uptime_last_day = uptime_last_day
        self.uptime_last_week = uptime_last_week
        self.downtime_last_day = downtime_last_day
        self.downtime_last_hour = downtime_last_hour
        self.downtime_last_week = downtime_last_week
        self.status = status

    def __repr__(self):
        return f"<Store {self.store_id}>"


# FUNCTIONS
menu_file = "./menu_hours.csv"
menu_df = pd.read_csv(menu_file)

store_file = "./store_status.csv"
store_df = pd.read_csv(store_file)


def convert_local_time_to_utc(local_time_str, local_timezone_str):
    try:
        local_timezone = pytz.timezone(local_timezone_str)
        utc_timezone = pytz.UTC

        # Create a datetime object from the local time string and localize it
        local_time = local_timezone.localize(
            datetime.strptime(local_time_str, "%Y-%m-%d %H:%M:%S")
        )

        # Convert to UTC time
        utc_time = local_time.astimezone(utc_timezone)

        # Format as a string
        utc_time_str = utc_time.strftime("%Y-%m-%d %H:%M:%S")

        return utc_time_str
    except ValueError:
        return None


def convert_utc_to_local_time(local_time_str, local_timezone_str):
    try:
        utc_timezone = pytz.UTC
        utc_datetime = datetime.strptime(
            local_time_str, "%Y-%m-%d %H:%M:%S.%f UTC")
        utc_time = utc_timezone.localize(utc_datetime)
        local_timezone = pytz.timezone(local_timezone_str)
        local_time = utc_time.astimezone(local_timezone)
        day_of_week = local_time.strftime("%A")
        local_time_str = local_time.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
        return local_time_str, DAYS[day_of_week]
    except Exception as e:
        print(e)
        return None


# Example usage:
local_time_str = "2023-10-06 15:30:00"
local_timezone_str = "America/New_York"  # Replace with your local timezone
utc_time_str = convert_local_time_to_utc(local_time_str, local_timezone_str)
print(utc_time_str, "utc time str")


def processStore(store_id, timestamp_str):
    with app.app_context():
        matching_rows = store_df[store_df["store_id"] == int(store_id)]
        for index, row in matching_rows.iterrows():
            print(
                convert_utc_to_local_time(row["timestamp_utc"], timestamp_str),
            )


def threaded_task(report):
    with app.app_context():
        # Write your code here
        bq_results_path = "./bq_results.csv"

        try:
            with open(bq_results_path, mode="r", newline="") as csv_file:
                csv_reader = csv.reader(csv_file)
                count = 0
                for row in csv_reader:
                    # Process the row here (e.g., print or perform some operation)
                    if count == 1:
                        processStore(row[0], row[1])
                    count += 1

        except FileNotFoundError:
            return {"message": "CSV file not found"}, 404
        report = ReportModel.query.get(report.report_id)
        if report:
            report.status = "Completed"
        db.session.commit()


# handle reports
@app.route("/trigger_report", methods=["POST", "GET"])  # type: ignore
def trigger_report():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            new_report = ReportModel(
                store_id=data["store_id"],
                uptime_last_hour=data["uptime_last_hour"],
                uptime_last_day=data["uptime_last_day"],
                uptime_last_week=data["uptime_last_week"],
                downtime_last_hour=data["downtime_last_hour"],
                downtime_last_day=data["downtime_last_day"],
                downtime_last_week=data["downtime_last_week"],
                status="Running",
            )

            db.session.add(new_report)
            db.session.commit()

            thread = Thread(target=threaded_task, args=(new_report,))
            thread.daemon = True
            thread.start()

            return {
                "message": f"report {new_report.report_id} has been created successfully."
            }
        else:
            return {"error": "The request payload is not in JSON format"}

    elif request.method == "GET":
        reports = ReportModel.query.all()
        results = [
            {
                "report_id": report.report_id,
                "store_id": report.store_id,
                "uptime_last_hour": report.uptime_last_hour,
                "uptime_last_day": report.uptime_last_day,
                "uptime_last_week": report.uptime_last_week,
                "downtime_last_hour": report.downtime_last_hour,
                "downtime_last_day": report.downtime_last_day,
                "downtime_last_week": report.downtime_last_week,
                "status": report.status,
            }
            for report in reports
        ]

        return {"count": len(results), "reports": results}


@app.route("/get_report/<string:report_id>", methods=["GET"])  # type: ignore
def get_report(report_id):
    if request.method != "GET":
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
            "status": report.status,
        }
        return jsonify(result)
    else:
        return {"message": "Report not found"}, 404


if __name__ == "__main__":
    app.run(port=8000, debug=True)

# my_project/
#     app.py
#     config.py
#     requirements.txt
#     static/
#     templates/
#     views/
