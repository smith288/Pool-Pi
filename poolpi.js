document.addEventListener("DOMContentLoaded", function() {
    // Connect to the Socket.IO server.
    // The connection URL has the following format, relative to the current page:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io();

    // Diconnect callback function
    // This is called by the timeout function if a model hasn't been received recently
    function noConnection() {
        document.getElementsByClassName('overlay')[0].style.display = 'flex';
        document.getElementById('display1').innerHTML = '   NO CONNECTION    ';
        document.getElementById('display2').innerHTML = ' FROM RASPBERRY PI  ';
    }

    // Timeout ID for disconnect timer
    var timeoutID;

    // Disconnect timer function to notify user if connection has been lost
    // Reset when the model update is received
    function resetTimeout() {
        clearTimeout(timeoutID)
        timeoutID = window.setTimeout(
            function() {
                noConnection();
            }, 8000);
    }

    // Model version
    var modelVersion;
    socket.on("message", function(msg) {
        console.log("Message", msg);
    });

    socket.on("connect", function() {
        console.log("Connected");
    });

    socket.on("disconnect", function() {
        console.log("Disconnected");
    });

    // Handler for the model update
    socket.on('model', function(msg) {
        resetTimeout();
        msgObj = JSON.parse(msg["data"]);
        document.getElementsByClassName('overlay')[0].style.display = 'none';

        // Parse version
        modelVersion = msgObj['version'];
        delete msgObj['version'];

        // Parse display into two lines and blink if necessary
        len = msgObj['display_mask'].length;
        document.getElementById('display1').innerHTML = '';
        document.getElementById('display2').innerHTML = '';

        // Parse top row of display
        for (var i = 0; i < len / 2; ++i) {
            if (msgObj['display_mask'][i] == '1') {
                document.getElementById('display1').innerHTML += '<span class=' + 'blinkingText' + '>' + msgObj['display'].charAt(i) + '</span>';
            } else {
                document.getElementById('display1').innerHTML += msgObj['display'].charAt(i);
            }
        }
        // Parse bottom row of display
        for (var i = len / 2; i < len; ++i) {
            if (msgObj['display_mask'][i] == '1') {
                document.getElementById('display2').innerHTML += '<span class=' + 'blinkingText' + '>' + msgObj['display'].charAt(i) + '</span>';
            } else {
                document.getElementById('display2').innerHTML += msgObj['display'].charAt(i);
            }
        }
        delete msgObj['display'];
        delete msgObj['display_mask'];

        // TODO can this be cleaned up?

        // Parse every item in json message
        for (var i = 0, len = Object.keys(msgObj).length; i < len; ++i) {
            attributeName = Object.keys(msgObj)[i];

            // Parse sending_message flag (no version)
            if (attributeName == 'sending_message') {
                if (msgObj[attributeName] == true) {
                    document.getElementsByClassName('overlay')[0].style.display = 'none'
                } else {
                    document.getElementsByClassName('overlay')[0].style.display = 'none'
                }
                continue
            }

            // Parse service
            else if (attributeName == 'service') {
                if (msgObj['service'].state == 'ON') {
                    $('#led-service').removeClass('off').addClass('red');
                    // document.getElementById('service').parentElement.children['led'].className = 'LED red' + ' toggle-element';
                } else if (msgObj['service'].state == 'OFF') {
                    $('#led-service').removeClass('red').addClass('off');
                    // document.getElementById('service').parentElement.children['led'].className = 'LED off' + ' toggle-element';
                } else if (msgObj['service'].state == 'BLINK') {
                    $('#led-service').removeClass('off').addClass('red blink');
                    // document.getElementById('service').parentElement.children['led'].className = 'LED red blink' + ' toggle-element';
                } else if (msgObj['service'].state == 'INIT') {
                    $('#led-service').removeClass('red blink').addClass('off');
                    // document.getElementById('service').parentElement.children['led'].className = 'LED off' + ' toggle-element';
                }
            }

            // Parse pool/spa/spillover
            else if ((attributeName == 'pool') || (attributeName == 'spa') || (attributeName == 'spillover')) {
                if (msgObj[attributeName].state == 'ON') {
                    // Using jQuery, get the element that has the 
                    $('#led-' + attributeName).removeClass('off').addClass('green');
                    //document.getElementById(attributeName).children['led'].className = 'LED green' + ' toggle-element';
                } else {
                    $('#led-' + attributeName).removeClass('green').addClass('off');
                    // document.getElementById(attributeName).children['led'].className = 'LED off' + ' toggle-element';
                }
            }

            // Parse check system
            else if (attributeName == 'checksystem') {
                if (msgObj['checksystem'] == 'ON') {
                    $('#checksystem').className = 'LED orange';
                } else {
                    $('#checksystem').className = 'LED off';
                }
            }

            // Parse other buttons
            else {
                if (msgObj[attributeName].state == 'ON') {
                    $('#led-' + attributeName).removeClass('off').addClass('green');
                    //document.getElementById(attributeName).parentElement.children['led'].className = 'LED green' + ' toggle-element';
                } else {
                    // using jQuery: get the parent of the button, then get the children of the parent with class 'led'
                    $('#led-' + attributeName).removeClass('green').addClass('off');
                    //$('#'+attributeName).parents.children['led'].className = 'LED off' + ' toggle-element';
                }
            }
        }
    });

    // Handler for menu buttons
    document.querySelectorAll('.button-menu').forEach(element => element.addEventListener('click', function() {
        buttonID = this.getAttribute('id');
        socket.emit('webCommand', { 'id': buttonID, 'modelVersion': modelVersion });
    }));

    // Handler for toggle buttons
    document.querySelectorAll('.button-toggle').forEach(element => element.addEventListener('click', function() {
        // Double check that overlay is not present
        if (document.getElementsByClassName('overlay')[0].style.display != 'none') {
            return
        }
        document.getElementsByClassName('overlay')[0].style.display = 'flex';
        buttonID = this.getAttribute('id');
        socket.emit('webCommand', { 'id': buttonID, 'modelVersion': modelVersion });
        console.log('Toggled ' + buttonID);
    }));
});