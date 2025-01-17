from distutils.log import INFO
from commands import *
from threading import Thread
from model import *
from web import *
from parsing import *
from os import makedirs
from os.path import exists
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import time
import json
from mqtt import MQTTClient

socketio = SocketIO(message_queue="redis://127.0.0.1:6379")
r = redis.Redis(charset="utf-8", decode_responses=True)
pubsub = r.pubsub()
pubsub.subscribe("inbox")
mqttclient = None
logs = False

def readSerialBus(serialHandler):
    """
    Read data from the serial bus to build full frame in buffer.
    Serial frames begin with DLE STX and terminate with DLE ETX.
    With the exception of searching for the two start bytes,
    this function only reads one byte to prevent blocking other processes.
    When looking for start of frame, looking_for_start is True.
    When buffer is filled with a full frame and ready to be parseed,
    buffer_full is set to True to signal parseBuffer.
    """
    
    if serialHandler.in_waiting() == 0:  # Check if we have serial data to read
        return
    if (
        serialHandler.buffer_full == True
    ):  # Check if we already have a full frame in buffer
        return
    serChar = serialHandler.read()
    if serialHandler.looking_for_start:
        # We are looking for DLE STX to find beginning of frame
        if serChar == DLE:
            serChar = serialHandler.read()
            if serChar == STX:
                # We have found start (DLE STX)
                serialHandler.buffer.clear()
                serialHandler.buffer += DLE
                serialHandler.buffer += STX
                serialHandler.looking_for_start = False
                return
            else:
                # We have found DLE but not DLE STX
                return
        else:
            # Non-DLE character
            # We are only interested in DLE to find potential start
            return
    else:
        # We have already found the start of the frame
        # We are adding to buffer while looking for DLE ETX
        serialHandler.buffer += serChar
        # Check if we have found DLE ETX
        if (serChar == ETX) and (
            serialHandler.buffer[-2] == int.from_bytes(DLE, "big")
        ):
            # We have found a full frame
            serialHandler.buffer_full = True
            serialHandler.looking_for_start = True
            return


def parseBuffer(poolModel, serialHandler, commandHandler):
    """
    Check if we have full frame in buffer.
    If we have a full frame in buffer, parse it.
    If frame is keep alive, check to see if we are ready to send a command and if so send it.
    """
    if serialHandler.buffer_full:
        frame = serialHandler.buffer
        # Remove any extra x00 after x10
        frame = frame.replace(b"\x10\x00", b"\x10")

        # Ensure no erroneous start/stop within frame
        if b"\x10\x02" in frame[2:-2]:
            logging.error(f"DLE STX in frame: {frame}")
            serialHandler.reset()
            return
        if b"\x10\x03" in frame[2:-2]:
            logging.error(f"DLE ETX in frame: {frame}")
            serialHandler.reset()
            return

        # Compare calculated checksum to frame checksum
        if confirmChecksum(frame) == False:
            # If checksum doesn't match, message is invalid.
            # Clear buffer and don't attempt parsing.
            serialHandler.reset()
            return

        # Extract type and data from frame
        frameType = frame[2:4]
        data = frame[4:-4]

        # Use frame type to determine parsing function
        if frameType == FRAME_TYPE_KEEPALIVE:
            
            # Check to see if we have a command to send
            if serialHandler.ready_to_send == True:
                
                if commandHandler.keep_alive_count == 1:
                    # If this is the second sequential keep alive frame, send command
                    serialHandler.send(commandHandler.full_command)
                    logging.info(
                        f"Sent: {commandHandler.parameter}, {commandHandler.full_command}"
                    )
                    if commandHandler.confirm == False:
                        commandHandler.sending_message = False
                    serialHandler.ready_to_send = False
                else:
                    commandHandler.keep_alive_count = 1
            else:
                commandHandler.keep_alive_count = 0
        else:
            # Message is not keep alive
            commandHandler.keep_alive_count = 0
            if frameType == FRAME_TYPE_DISPLAY:
                parseDisplay(data, poolModel)
            elif frameType == FRAME_TYPE_LEDS:
                parseLEDs(data, poolModel)
            elif frameType == FRAME_TYPE_DISPLAY_SERVICE:
                parseDisplay(data, poolModel)
            elif frameType == FRAME_TYPE_SERVICE_MODE:
                logging.info(f"Service Mode update: {frameType}, {data}")
            # TODO add parsing and logging for local display commands
            # not sent by Pool-Pi (\x00\x02)
            else:
                # logging.info(f"Unkown update: {frameType}, {data}")
                pass
        # Clear buffer and reset flags
        serialHandler.reset()


def checkCommand(poolModel, serialHandler, commandHandler):
    """
    If we are trying to send a message, wait for a new pool model to get pool states
    If necessary, queue message to be sent after second keep alive
    """
    if commandHandler.sending_message == False:
        # We aren't trying to send a command, nothing to do
        return

    if serialHandler.ready_to_send == True:
        # We are already ready to send, awaiting keep alive
        return

    if poolModel.timestamp >= commandHandler.last_model_timestamp_seen:
        # We have a new poolModel
        if (
            poolModel.getParameterState(commandHandler.parameter)
            == commandHandler.target_state
        ):
            # Model matches, command was successful.
            # Reset sending state.
            logging.info(f"Command success.")
            commandHandler.sending_message = False
            poolModel.sending_message = False
            poolModel.flag_data_changed = True
        else:
            logging.debug(
                f"Command not yet successful: {commandHandler.parameter} {commandHandler.target_state}"
            )
            # New poolModel doesn't match, command not successful.
            if commandHandler.sendAttemptsRemain() == True:
                commandHandler.last_model_timestamp_seen = time.time()
                serialHandler.ready_to_send = True


def getCommand(poolModel, serialHandler, commandHandler):
    """
    If we're not currently sending a command, check if there are new commands.
    Get new command from command_queue, validate, and initiate send with commandHandler.
    """
    if commandHandler.sending_message == True:
        # We are currently trying to send a command, don't check for others.
        return
    message = pubsub.get_message()
    if message and (message["type"] == "message"):
        logging.info(f"Received command from web: {message}")
        print(f"Received command from web: {message}")
        messageData = json.loads(message["data"])
        # Extract command info
        commandID = messageData["id"]
        # check if MQTT is a property of the message and true
        if "MQTT" in messageData and messageData["MQTT"] == True:
            frontEndVersion = poolModel.version
        else:
            frontEndVersion = messageData["modelVersion"]

        if frontEndVersion != poolModel.version:
            logging.error(f"Invalid command: Back end version is {poolModel.version} but front end version is {frontEndVersion}.")

        if commandID == "pool-spa-spillover":
            commandID = "pool"

        # Determine if command requires confirmation
        if (commandID in button_toggle) or (commandID == "pool"):
            commandConfirm = True
        elif commandID in buttons_menu:
            commandConfirm = False
        else:
            # commandID has no match in commands.py
            logging.error(f"Invalid command: Error parsing command: {commandID}")
            return

        if commandConfirm == True:
            # Command is not a menu button.
            # Confirmation if command was successful is needed

            # Pool spa spillover is single button- need to get individual commandID
            if commandID == "pool-spa-spillover":
                if poolModel.getParameterState("pool") == "ON":
                    commandID = "pool"
                elif poolModel.getParameterState("spa") == "ON":
                    commandID = "spa"
                else:
                    commandID = "spillover"

            # Check we aren't in INIT state
            if poolModel.getParameterState(commandID) == "INIT":
                logging.error(f"Invalid command: Target parameter {commandID} is in INIT state.")

            # Determine next desired state
            currentState = poolModel.getParameterState(commandID)
            # Service tristate ON->BLINK->OFF
            if commandID == "service":
                if currentState == "ON":
                    desiredState = "BLINK"
                elif currentState == "BLINK":
                    desiredState = "OFF"
                else:
                    desiredState = "ON"
            # All other buttons
            else:
                if currentState == "ON":
                    desiredState = "OFF"
                else:
                    desiredState = "ON"

            logging.info(f"Valid command: {commandID} {desiredState}, version {frontEndVersion}")
            # Push to command handler
            commandHandler.initiateSend(commandID, desiredState, commandConfirm)
            poolModel.sending_message = True

        else:
            # Command is a menu button
            # No confirmation needed. Only send once.
            # Immediately load for sending.
            commandHandler.initiateSend(commandID, "NA", commandConfirm)
            serialHandler.ready_to_send = True
    return


def sendModel(poolModel):
    """
    Check if we have new model for the front end. If so, send JSON data to redis.
    """

    if poolModel.flag_data_changed == True:

        r.publish("outbox", poolModel.toJSON())
        socketio.emit("model", poolModel.toJSON())

        # Only send one message to MQTT broker per 5 seconds
        if (time.time() - mqttclient.last_publish_time) > 5:
            mqttclient.last_publish_time = time.time()
            mqttclient.publish(poolModel.toJSON())
            #logging.debug("Published model to MQTT broker.")
        else:
            #logging.debug("Not publishing to MQTT broker.")
            pass
        #logging.debug("Published model to outbox.")
        poolModel.flag_data_changed = False

    return

def mqttCallback(topic, msg):
    """
    Callback function for MQTT message handling.

    Args:
        topic (str): The topic on which the message was received.
        msg (str): The message received.

    Returns:
        None
    """
    # Convert msg to dictionary
    print(f"Received message on topic: {msg}")
    msg_dict = json.loads(msg)

    # Add new property
    msg_dict['MQTT'] = True

    # Convert dictionary back to string
    msg = json.dumps(msg_dict)

    print(f"Received message on topic {topic}: {msg}")
    r.publish("inbox", msg)

def serialBackendMain(serial_port, socket_ip, socket_port):
    poolModel = PoolModel()
    
    if serial_port:
        serialHandler = SerialHandler(serial_port)
    else:
        serialHandler = SocketHandler(socket_ip, socket_port)
    
    commandHandler = CommandHandler()
    while True:
        # Read Serial Bus
        # If new serial data is available, read from the buffer
        readSerialBus(serialHandler)

        # Parse Buffer
        # If a full serial frame has been found, decode it and update model.
        # If we have a command ready to be sent, send.
        parseBuffer(poolModel, serialHandler, commandHandler)

        # If we are sending a command, check if command needs to be sent.
        # Check model for updates to see if command was accepted.
        checkCommand(poolModel, serialHandler, commandHandler)

        # Send updates to front end.
        sendModel(poolModel)

        # If we're not sending, check for new commands from front end.
        getCommand(poolModel, serialHandler, commandHandler)


if __name__ == "__main__":
    
    serial_port = None
    socket_ip = None
    socket_port = None

    if len(sys.argv) == 2:
        print('Connecting to {}...'.format(sys.argv[1]))
        if sys.argv[1].startswith('/'):
            serial_port = sys.argv[1]
        else:
            print('Incorrect serial port format. It should look something like /dev/ttyUSB0 or /dev/SERIAL0')
            quit()
        serial_port = sys.argv[1]
    elif len(sys.argv) == 3:
        print('Connecting to {}:{}...'.format(sys.argv[1], sys.argv[2]))
        socket_ip = sys.argv[1]
        socket_port = sys.argv[2]
    else:
        print('Usage: pool-pi [host] [port]')
        print('           [serial port]')
        quit()
       
    # Create log file directory if not already existing
    if logs == True:
        if not exists("logs"):
            makedirs("logs")
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = TimedRotatingFileHandler(
            "logs/pool-pi.log", when="midnight", backupCount=60
        )
        handler.suffix = "%Y-%m-%d_%H-%M-%S"
        handler.setFormatter(formatter)
        logging.getLogger().handlers.clear()
        logging.getLogger().addHandler(handler)
        
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Started pool-pi.py")

    thread_web = Thread(target=webBackendMain, daemon=True)
    thread_web.start()

    mqttclient = MQTTClient(callback=mqttCallback)
    mqttclient.run()
    serialBackendMain(serial_port, socket_ip, socket_port)