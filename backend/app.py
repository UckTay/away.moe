import os
import uuid
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.datastructures import FileStorage

from sql_db import SQLiteDatabase
from database import PythonDatabase, Database

app = Flask(__name__, static_folder="../frontend/build", static_url_path="/")
db: Database = SQLiteDatabase()
# db: Database = PythonDatabase()
CORS(app)

@app.route("/")
def serve_react(self):
    """Serve the React app."""
    return app.send_static_file("index.html")


@app.route("/api/upload/<unique_id>", methods=["POST"])
def upload(unique_id: str):
    """API to upload a file and / or text."""
    file = None
    print("got upload")
    if "file" in request.files:
        file = request.files["file"]
        print(f"got file {file}")
    text = request.form.get("text")
    if text is None and file is None:
        return jsonify({"error": "No file or text uploaded"}), 400

    expiration_str = request.form.get("ttl")
    expiration_unix, instant_expire = get_future_timestamp(expiration_str)
    if expiration_unix is None:
        return jsonify({"error": "Invalid expiration time given"}), 400

    if db.entry_present(unique_id) and not db.check_expired(unique_id):
        return jsonify({"message": "Entry already exists"}), 400

    db.add_to_database(unique_id, file.filename if file is not None else None, file, text, expiration_unix, instant_expire)
    return jsonify({"message": "File uploaded successfully"}), 200


@app.route("/api/fetch_info/<unique_id>", methods=["GET"])
def fetch_info(unique_id: str):
    json_response = {"unique_id": unique_id}
    if db.entry_present(unique_id) and not db.check_expired(unique_id):
        json_response["id_present"] = True
        json_response["text"] = db.retrieve_text(unique_id)
        if db.file_present(unique_id):
            json_response["filename"] = db.retrieve_file_name(unique_id)
        elif db.get_instant_expire(unique_id):
            db.delete_from_database(unique_id)
        return jsonify(json_response)

    else:
        json_response["id_present"] = False
        return jsonify(json_response), 200


@app.route("/api/download/<unique_id>", methods=["GET"])
def download(unique_id: str):
    if not db.file_present(unique_id) or db.check_expired(unique_id):
        return jsonify({"message": "File does not exist"}), 400
    path = db.retrieve_file_path(unique_id)
    filename = db.retrieve_file_name(unique_id)
    print(f"{path=} {filename=}")
    return send_from_directory("",
                               str(path),
                               as_attachment=True,
                               download_name=filename)


def get_future_timestamp(expiration_str: str) -> tuple[int, bool] | tuple[None, None]:
    """Gets the unix timestamp of the expiration time for the corresponding string"""
    current_time = datetime.now()

    # Mapping of time units to timedelta
    time_deltas = {
        "1m": timedelta(minutes=1),
        "10m": timedelta(minutes=10),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
    }
    is_instant_expire = expiration_str == "-1"

    print(f"got expiration time {expiration_str}")
    # Check if the expiration time is valid
    if not is_instant_expire and expiration_str not in time_deltas:
        print("got none damn")
        return None, None

    expiration_key = "1w" if is_instant_expire else expiration_str
    expiration_datetime = current_time + time_deltas[expiration_key]
    return int(expiration_datetime.timestamp()), is_instant_expire

if __name__ == '__main__':
    app.run(debug=True)
