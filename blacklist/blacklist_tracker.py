import os
import psycopg2
import json
from dotenv import load_dotenv

# Path absolut ke folder root (di mana .env berada)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

class BlacklistTracker:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=os.getenv("DB_PORT", "5442"),
            dbname=os.getenv("DB_NAME", "biosecurity-boot"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "ZKTeco##123")
        )

    def run(self):
        data = {"data": []}
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM acc_person WHERE disabled = 't'")
                acc_persons = cur.fetchall()

                for acc in acc_persons:
                    person_id = acc[17]  # index ke-17 = acc_person.person_id

                    cur.execute("SELECT * FROM pers_person WHERE id = %s", (person_id,))
                    person = cur.fetchone()
                    if not person:
                        continue

                    cur.execute("SELECT * FROM pers_attribute_ext WHERE person_id = %s", (person[0],))
                    attribute = cur.fetchone()

                    cur.execute("SELECT * FROM att_person WHERE pers_person_pin = %s", (person[34],))
                    attendance = cur.fetchone()

                    gender = "Male" if person[19] == "M" else "Female"
                    nipeg = attribute[19] if attribute and attribute[19] else ""
                    
                    data["data"].append({
                        "site": "PT. PLN Indonesia Power",
                        "dept": attendance[17] if attendance else "",
                        "foto": "",
                        "name": attendance[24] if attendance else "",
                        "time": gender,
                        "id": attendance[25] if attendance else "",
                        "nipeg": nipeg
                    })

        except Exception as e:
            return {"error": str(e)}

        return data