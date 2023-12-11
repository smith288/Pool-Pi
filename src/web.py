from flask import Flask, render_template, session, request, redirect, url_for, make_response
from flask_socketio import SocketIO, emit
from threading import Lock
import uuid
import logging
import datetime

# import eventlet
import redis
import json

# eventlet.monkey_patch()
async_mode = None
app = Flask(__name__)
app.config["SECRET_KEY"] = uuid.uuid4().hex
socketio = SocketIO(app, async_mode=async_mode)

r = redis.Redis(charset="utf-8", decode_responses=True)


@socketio.event
def connect():
    logging.info(f"Client connected.")


@app.route("/")
def index():
    if request.cookies.get("authenticated") is None or request.cookies.get("authenticated") != "True":
        print ("Not Authenticated")
        # Do a 201 redirect to login page
        return redirect(url_for("login"))
    else:
        print("authenticated")
        return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Set a cookie to identify the user
        if request.form["username"] == "admin" and request.form["password"] == "admin":
            response = make_response(redirect("/"))
            expires = datetime.datetime.now() + datetime.timedelta(days=365)
            response.set_cookie('authenticated', 'True', expires=expires)
            return response
        else:
            return render_template("login.html?invalid=1")
    else:  
        return render_template("login.html")

@socketio.event
def webCommand(message):
    """
    Publish command from front end to redis channel.
    """
    logging.info(f"Received command from web: {message}")
    r.publish("inbox", json.dumps(message))


def checkOutbox():
    logging.info(f"Starting checkOutbox")
    """
    Subscribe to redis channel for messages to relay to front end.
    Used for sending pool model showing current state of the pool.
    """
    pubsub = r.pubsub()
    pubsub.subscribe("outbox")
    while True:
        message = pubsub.get_message()
        if message and (message["type"] == "message"):
            socketio.emit("model", message)
        socketio.sleep(0.01)


def webBackendMain():
    logging.info(f"Starting web backend.")
    socketio.start_background_task(checkOutbox)
    socketio.run(app, host="0.0.0.0")
