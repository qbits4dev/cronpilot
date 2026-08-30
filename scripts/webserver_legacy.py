from flask import Flask, render_template, redirect, url_for, Response
import csv
import io
import os

app = Flask(__name__)


def find_log_file():
    candidates = [
        "app.log",
        "server.log",
        "log_server.log",
        os.path.join("logs", "app.log"),
        os.path.join("logs", "server.log"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


@app.route("/")
def index():
    endpoints = [
        {"path": url_for("show_log"), "label": "/log", "desc": "View logs"},
        {"path": url_for("show_numbers"), "label": "/numbers", "desc": "View consolidated mobile numbers"},
        {"path": url_for("download_google_contacts"), "label": "/download_google_contacts", "desc": "Download Google Contacts CSV"},
    ]
    return render_template("index.html", endpoints=endpoints)


@app.route("/log")
def show_log():
    log_path = find_log_file()
    source = None
    lines = []
    if log_path:
        source = log_path
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                lines = all_lines[-500:]
        except Exception as e:
            lines = [f"Could not read {log_path}: {e}"]
    else:
        # Fallback: show the `log_server.py` source if no runtime log found
        fallback = "log_server.py"
        if os.path.exists(fallback):
            source = fallback
            with open(fallback, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        else:
            lines = ["No log file found and no log_server.py source available."]

    return render_template("log.html", source=source, lines=lines)


@app.route("/numbers")
def show_numbers():
    csv_path = "consolidated_mobile_numbers.csv"
    if not os.path.exists(csv_path):
        # try nested path used in repo
        csv_path = os.path.join("mobile numbers", "Ramarao", "consolidated_mobile_numbers.csv")

    headers = []
    rows = []
    if os.path.exists(csv_path):
        try:
            with open(csv_path, newline='', encoding='utf-8', errors='replace') as csvfile:
                reader = csv.reader(csvfile)
                for i, r in enumerate(reader):
                    if i == 0:
                        headers = r
                    else:
                        rows.append(r)
        except Exception as e:
            headers = []
            rows = [[f"Error reading CSV: {e}"]]
    else:
        rows = [["CSV file not found: consolidated_mobile_numbers.csv"]]

    return render_template("numbers.html", headers=headers, rows=rows)


def generate_google_contacts_csv(csv_path):
    out = io.StringIO()
    writer = csv.writer(out)

    # Google Contacts minimal columns
    header = [
        "Name",
        "Given Name",
        "Family Name",
        "Phone 1 - Type",
        "Phone 1 - Value",
    ]
    writer.writerow(header)

    # heuristics to find phone and name columns
    if not os.path.exists(csv_path):
        return out.getvalue()

    with open(csv_path, newline='', encoding='utf-8', errors='replace') as csvfile:
        reader = csv.reader(csvfile)
        headers = None
        for i, row in enumerate(reader):
            if i == 0:
                headers = [h.strip().lower() for h in row]
                # find phone column
                phone_idx = None
                name_idx = None
                for idx, h in enumerate(headers):
                    if any(k in h for k in ("phone", "mobile", "number", "contact")) and phone_idx is None:
                        phone_idx = idx
                    if any(k in h for k in ("name", "first", "given")) and name_idx is None:
                        name_idx = idx
                # fallback defaults
                if phone_idx is None:
                    phone_idx = 0
            else:
                # pick name and phone using indices
                try:
                    phone = row[phone_idx].strip()
                except Exception:
                    phone = ""
                try:
                    name = row[name_idx].strip() if name_idx is not None else ""
                except Exception:
                    name = ""

                if not name:
                    name = phone

                writer.writerow([name, "", "", "Mobile", phone])

    return out.getvalue()


@app.route("/download_google_contacts")
def download_google_contacts():
    csv_path = "consolidated_mobile_numbers.csv"
    if not os.path.exists(csv_path):
        csv_path = os.path.join("mobile numbers", "Ramarao", "consolidated_mobile_numbers.csv")

    csv_text = generate_google_contacts_csv(csv_path)
    resp = Response(csv_text, mimetype='text/csv')
    resp.headers.set("Content-Disposition", "attachment", filename="google_contacts.csv")
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
