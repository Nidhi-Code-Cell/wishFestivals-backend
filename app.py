from flask import Flask, request, jsonify
from flask_cors import CORS
from pywebpush import webpush, WebPushException
from apscheduler.schedulers.background import BackgroundScheduler
import psycopg2
import json
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

# -------------------- CONFIG --------------------

VAPID_PRIVATE_KEY = "GaEBoiq7FVQApNnhEk--xi25ou3D4If7YKcvWsCDhgQ"
VAPID_CLAIMS = {
    "sub": "mailto:nidhi.singh706577@gmail.com"
}

# -------------------- DB CONNECTION --------------------

def get_db_connection():
    # db_url = os.getenv("DATABASE_URL")
    db_url = "postgresql://user1:2gRx405HQau4j5IVGL0N1Ay11LFKk61N@dpg-d580k063jp1c73b8cr80-a.singapore-postgres.render.com/db1_82rt"

    if db_url:
        return psycopg2.connect(db_url, sslmode="require")

    # fallback for local dev
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )


# -------------------- ROUTES --------------------

@app.route("/")
def home():
    return "Backend is running 🚀"

# -------------------- SUBSCRIBE --------------------

@app.route("/subscribe", methods=["POST"])
def subscribe():
    subscription = request.get_json()

    if not subscription:
        return jsonify({"error": "No subscription provided"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Insert subscription (avoid duplicates)
        cur.execute(
            """
            INSERT INTO push_subscriptions (subscription)
            VALUES (%s)
            ON CONFLICT DO NOTHING
            """,
            [json.dumps(subscription)]
        )

        # Always fetch subscription_id safely
        cur.execute(
            "SELECT id FROM push_subscriptions WHERE subscription = %s",
            [json.dumps(subscription)]
        )
        subscription_id = cur.fetchone()[0]

        # Auto-create schedules (safe against duplicates)
        cur.execute(
            """
            INSERT INTO notification_schedule (subscription_id, message, scheduled_time)
            VALUES
            (%s, %s, %s),
            (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                subscription_id,
                "🌸 Happy weekend! Check my app cutie 💖",
                "2025-12-27 15:00:00",

                subscription_id,
                "🎆 Happy New Year! Open the app — your surprise awaits 🥰",
                "2025-12-31 23:59:00"
            )
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Subscription stored & schedules created"}), 201

    except Exception as e:
        print("🔥 ERROR in /subscribe:", e)
        return jsonify({"error": str(e)}), 500

# -------------------- TEST PUSH --------------------

@app.route("/send-test-push", methods=["POST"])
def send_test_push():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT subscription FROM push_subscriptions")
        subscriptions = cur.fetchall()

        for (subscription_info,) in subscriptions:
            webpush(
                subscription_info=subscription_info,
                data="🎄 Your Festive Surprise is ready 💖",
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )

        cur.close()
        conn.close()

        return jsonify({"message": "Test push sent!"})

    except WebPushException as e:
        print("❌ Push failed:", e)
        return jsonify({"error": str(e)}), 500

# -------------------- SCHEDULED NOTIFICATIONS --------------------

def check_and_send_notifications():
    print("🔍 Checking scheduled notifications...")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT ns.id, ps.subscription, ns.message
        FROM notification_schedule ns
        JOIN push_subscriptions ps
        ON ns.subscription_id = ps.id
        WHERE ns.sent = false
        AND ns.scheduled_time <= NOW()
        """
    )

    rows = cur.fetchall()

    for schedule_id, subscription_info, message in rows:
        try:
            webpush(
                subscription_info=subscription_info,
                data=message,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )

            cur.execute(
                "UPDATE notification_schedule SET sent = true WHERE id = %s",
                (schedule_id,)
            )
            conn.commit()

            print(f"✅ Notification {schedule_id} sent")

        except WebPushException as e:
            print("❌ Push failed:", e)

    cur.close()
    conn.close()

# -------------------- START SCHEDULER --------------------

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_and_send_notifications,
        trigger="interval",
        seconds=30
    )
    scheduler.start()

    print("⏰ Notification scheduler started")
    # app.run(debug=True)
    port=os.environ["PORT"]
    app.run(
        host="0.0.0.0",   # VERY IMPORTANT
        port=port,        # VERY IMPORTANT
        debug=False       # MUST be False in production
    )
