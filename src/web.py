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
        session.is_authenticated = False
        # Do a 201 redirect to login page
        return redirect(url_for("login"))
    else:
        print("authenticated")
        session.is_authenticated = True
        return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Set a cookie to identify the user
        if "username" in request.form and "password" in request.form and request.form["username"] == "admin" and request.form["password"] == "admin":
            response = make_response(redirect("/"))
            expires = datetime.datetime.now() + datetime.timedelta(days=365)
            
            if "remember" in request.form:
                response.set_cookie('uname', request.form["username"], expires=expires)
                response.set_cookie('remember', 'True', expires=expires)
            else:
                 response.set_cookie('uname', 'False', expires=0)
                 response.set_cookie('remember', 'False', expires=0)

            response.set_cookie('authenticated', 'True', expires=expires)
            return response
        else:
            return render_template("login.html?invalid=1")
    else:
        if request.cookies.get("uname") is not None:
            uname = request.cookies.get("uname")
            remember = request.cookies.get("remember")
        else:
            uname = ""
            remember = "False"
        return render_template("login.html", uname=uname, remember=remember)

@app.route("/logout")
def logout():
    response = make_response(redirect("/login"))
    response.set_cookie('authenticated', '', expires=0)
    return response

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
    socketio.run(app, host="0.0.0.0", allow_unsafe_werkzeug=True)
