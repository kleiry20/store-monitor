import io
import os
import csv
import pytz
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import request, jsonify, Response
from threading import Thread

load_dotenv()

app = Flask(__name__)
DATABASE_URI = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
db = SQLAlchemy(app)
migrate = Migrate(app, db)

DAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

menu_file = "./menu_hours.csv"
menu_df = pd.read_csv(menu_file)

store_file = "./store_status.csv"
store_df = pd.read_csv(store_file)

csv_file_path = "./data.csv"

timestamp = "2023-01-25 18:15:22.47922 UTC"


class ReportModel(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String())

    def __init__(
        self,
        status,
    ):
        self.status = status

    def __repr__(self):
        return f"<Store {self.report_id}>"


def convert_utc_to_local_time(local_time_str, local_timezone_str):
    try:
        utc_time = local_time_str
        local_timezone = pytz.timezone(local_timezone_str)
        local_time = utc_time.astimezone(local_timezone)
        day_of_week = local_time.strftime("%A")
        return local_time, DAYS[day_of_week]
    except Exception as e:
        print(e)
        return None

# to calculate the minutes for uptime and downtime


def getTimeDifference(store_time, last_timestamp):
    date2_str = datetime.strftime(
        store_time, "%Y-%m-%d %H:%M:%S.%f %Z")
    date2_str = date2_str.replace(' UTC', '')
    return abs(
        datetime.fromisoformat(datetime.strftime(last_timestamp, "%Y-%m-%d %H:%M:%S.%f")) -
        datetime.fromisoformat(date2_str)).total_seconds() / 60

# process a single store


def processStore(store_id, timestamp_str):
    with app.app_context():
        try:
            current_timestamp = datetime.strptime(
                timestamp, "%Y-%m-%d %H:%M:%S.%f %Z")
            last_hour_timestamp = current_timestamp - timedelta(hours=1)
            last_day_timestamp = current_timestamp - timedelta(days=1)
            last_week_timestamp = current_timestamp - timedelta(weeks=1)
            uptime_last_hour = 0
            uptime_last_day = 0
            uptime_last_week = 0
            downtime_last_hour = 0
            downtime_last_day = 0
            downtime_last_week = 0
            last_timestamp = current_timestamp

            matching_rows = store_df[store_df["store_id"] == int(store_id)]
            matching_rows['timestamp_utc'] = pd.to_datetime(
                matching_rows['timestamp_utc'])
            matching_rows = matching_rows.sort_values(by='timestamp_utc')
            for index, store in matching_rows.iterrows():
                local_time, day_int = convert_utc_to_local_time(
                    store["timestamp_utc"], timestamp_str)
                menu_rows = menu_df[(menu_df["store_id"] ==
                                    int(store_id)) & (menu_df["day"] == day_int)]
                for index, menu in menu_rows.iterrows():
                    today = datetime.today()
                    start_time = datetime.strptime(today.strftime(
                        "%Y-%m-%d ") + menu["start_time_local"], "%Y-%m-%d %H:%M:%S")
                    end_time = datetime.strptime(today.strftime(
                        "%Y-%m-%d ") + menu["end_time_local"], "%Y-%m-%d %H:%M:%S")

                    given_time = local_time.time()

                    if start_time.time() <= given_time <= end_time.time():
                        if store["timestamp_utc"].day != last_timestamp.day:
                            store_time = store["timestamp_utc"].strftime(
                                "%Y-%m-%d %H:%M:%S.%f %Z")
                            date_component = store_time.split()[0]
                            new_time = menu["end_time_local"]
                            new_datetime_str = f'{date_component} {new_time}.000001 UTC'
                            last_timestamp = datetime.strptime(
                                new_datetime_str, '%Y-%m-%d %H:%M:%S.%f %Z')
                        if store["status"] == 'active':
                            time_difference = getTimeDifference(
                                store["timestamp_utc"], last_timestamp)
                            uptime_last_hour += time_difference
                            uptime_last_day += time_difference
                            uptime_last_day += time_difference
                            last_timestamp = store["timestamp_utc"]
                        elif store["status"] == 'inactive':
                            time_difference = getTimeDifference(
                                store["timestamp_utc"], last_timestamp)
                            downtime_last_hour += time_difference
                            downtime_last_day += time_difference
                            downtime_last_week += time_difference
                            last_timestamp = store["timestamp_utc"]

            return uptime_last_hour, uptime_last_day, uptime_last_week, downtime_last_hour, downtime_last_day, downtime_last_week
        except Exception as ex:
            print(ex)
            return 0, 0, 0, 0, 0, 0

# background task to run after creating report id


def threaded_task(report):
    with app.app_context():

        bq_results_path = "./bq_results.csv"

        try:
            with open('data.csv', 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["store_id", "uptime_last_hour", "uptime_last_day",
                                        "uptime_last_week", "downtime_last_hour", "downtime_last_day", "downtime_last_week"])
                writer.writeheader()
                with open(bq_results_path, mode="r", newline="") as csv_file:
                    csv_reader = csv.reader(csv_file)
                    count = 0
                    for row in csv_reader:
                        # Process the rest of the row data here
                        if count >= 1:
                            uptime_last_hour, uptime_last_day, uptime_last_week, downtime_last_hour, downtime_last_day, downtime_last_week = processStore(
                                row[0], row[1])
                            writer.writerow({
                                "store_id": row[0],
                                "uptime_last_hour": uptime_last_hour,
                                "uptime_last_day": uptime_last_day,
                                "uptime_last_week": uptime_last_week,
                                "downtime_last_hour": downtime_last_hour,
                                "downtime_last_day": downtime_last_day,
                                "downtime_last_week": downtime_last_week})
                        count += 1

        except FileNotFoundError:
            return {"message": "CSV file not found"}, 404
        report = ReportModel.query.get(report.report_id)
        if report:
            report.status = "Completed"
        db.session.commit()


@app.route("/")
def home():
    return "Store Monitor App"


@app.route("/trigger_report", methods=["POST", "GET"])  # type: ignore
def trigger_report():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            new_report = ReportModel(
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

    if report.status == "Completed":
        updated_df = pd.read_csv(csv_file_path)
        updated_csv_data = io.StringIO()
        updated_df.to_csv(updated_csv_data, index=False)
        return Response(
            updated_csv_data.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=updated_data.csv'}
        )
    else:
        result = {
            "report_id": report.report_id,
            "status": report.status
        }
        return jsonify(result)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
