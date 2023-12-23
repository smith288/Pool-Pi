var status_filter = false;
var status_pool_spa_spillover = false;
var status_lights = false;
var status_heater1 = false;
var status_airtemp = 0;
var status_pooltemp = 0;
var status_poolchlorinator = 0;
var status_heater1 = false;
var status_saltlevel = 0;
var status_filterspeed = 0;

var toast;

$(document).ready(function() {

    $('#restart_service').click(function() {
        if (confirm('Are you sure you would like to restart the service?')) {
            $.get('/restart', function(data, status) {
                console.log('Restarting');
                setTimeout(function() {
                    location.reload();
                }, 5000);
            });
        }
    });
    toast = bootstrap.Toast.getOrCreateInstance(document.querySelector('#liveToast'));
    // Connect to the Socket.IO server.
    // The connection URL has the following format, relative to the current page:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io();

    // Diconnect callback function
    // This is called by the timeout function if a model hasn't been received recently
    function noConnection() {
        $('#basicModal').modal('show');

        $('#display1').innerHTML = '   NO CONNECTION    ';
        $('#display2').innerHTML = ' FROM HAYWARD  ';
    }

    // Timeout ID for disconnect timer
    var timeoutID;
    var tryCount = 0;

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
        $('#basicModal').modal('hide');

        // console.log('Model', msg);
        // Parse version
        modelVersion = msgObj['version'];
        delete msgObj['version'];

        // Parse display into two lines and blink if necessary
        len = msgObj['display_mask'].length;
        $('#display1').html('');
        $('#display2').html('');

        $('.pool_status').removeClass('d-none');
        $('.pool_conn_status').addClass('d-none');

        var panel_display = String(msgObj['display']).trim();
        console.log('panel_display', panel_display);
        switch (true) {
            case panel_display.indexOf('NO CONNECTION') > -1:
                $('.pool_conn_status').removeClass('d-none');
                $('.pool_status').addClass('d-none');
                break;
            case panel_display.indexOf('Pool Temp') > -1:
                panel_display = panel_display.replace('Pool Temp', '');
                status_pooltemp = panel_display.trim();
                break;
            case panel_display.indexOf('Air Temp') > -1:
                panel_display = panel_display.replace('Air Temp', '');
                status_airtemp = panel_display.trim();
                break;
            case panel_display.indexOf('Pool Chlorinator') > -1:
                panel_display = panel_display.replace('Pool Chlorinator', '');
                status_poolchlorinator = panel_display.trim();
                break;
            case panel_display.indexOf('Salt Level') > -1:
                panel_display = panel_display.replace('Salt Level', '');
                status_saltlevel = panel_display.trim();
                break;
            case panel_display.indexOf('Filter Speed') > -1:
                panel_display = panel_display.replace('Filter Speed', '');
                status_filterspeed = panel_display.trim();
                break;
            case panel_display.indexOf('Heater1') > -1:
                panel_display = panel_display.replace('Heater1', '');
                status_heater1 = panel_display.trim();
                break;
            default:
                break;
        }

        // console.log('status_pooltemp', status_pooltemp);
        // console.log('status_airtemp', status_airtemp);
        // console.log('status_poolchlorinator', status_poolchlorinator);
        // console.log('status_saltlevel', status_saltlevel);
        // console.log('status_filterspeed', status_filterspeed);

        $('#status_pooltemp').text(status_pooltemp);
        $('#status_airtemp').text(status_airtemp);
        $('#status_poolchlorinator').text(status_poolchlorinator);
        $('#status_saltlevel').text(status_saltlevel);
        $('#status_filterspeed').text(status_filterspeed);
        $('#status_heater1').text(status_heater1);

        // Parse top row of display
        for (var i = 0; i < len / 2; ++i) {
            if (msgObj['display_mask'][i] == '1') {
                $('#display1').html($('#display1').html() + '<span class=' + 'blinkingText' + '>' + msgObj['display'].charAt(i) + '</span>');
            } else {
                $('#display1').html($('#display1').html() + msgObj['display'].charAt(i));
            }
        }
        // Parse bottom row of display
        for (var i = len / 2; i < len; ++i) {
            if (msgObj['display_mask'][i] == '1') {
                $('#display1').html($('#display1').html() + '<span class=' + 'blinkingText' + '>' + msgObj['display'].charAt(i) + '</span>');
            } else {
                $('#display1').html($('#display1').html() + msgObj['display'].charAt(i));
            }
        }
        delete msgObj['display'];
        delete msgObj['display_mask'];

        setGlobals(msgObj);

        // Parse every item in json message
        for (var i = 0, len = Object.keys(msgObj).length; i < len; ++i) {
            attributeName = Object.keys(msgObj)[i];
            // Parse sending_message flag (no version)
            if (attributeName == 'sending_message') {
                if (msgObj[attributeName] == true) {
                    $('#basicModal').modal('show');
                } else {
                    $('#basicModal').modal('hide');
                }
                continue
            }

            // Parse service
            else if (attributeName == 'service') {
                try {

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
                } catch (err) {
                    // console.log(err);
                }
            }

            // Parse pool/spa/spillover
            else if ((attributeName == 'pool') || (attributeName == 'spa') || (attributeName == 'spillover')) {
                try {

                    if (msgObj[attributeName].state == 'ON') {
                        // Using jQuery, get the element that has the 
                        if (attributeName == 'pool') {
                            $('#pool_spa_spillover').attr('checked', 'checked');
                            $('#led-poolspa').removeClass('fa-hot-tub-person').addClass('fa-person-swimming');
                        } else if (attributeName == 'spa') {
                            $('#pool_spa_spillover').removeAttr('checked');
                            $('#led-poolspa').removeClass('fa-person-swimming').addClass('fa-hot-tub-person');
                        }
                    } else {

                    }

                } catch (err) {
                    // console.log(err);
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
                try {

                    if (msgObj[attributeName].state == 'ON') {
                        $('#' + attributeName).attr('checked', 'checked');
                    } else {
                        // using jQuery: get the parent of the button, then get the children of the parent with class 'led'
                        $('#' + attributeName).attr('checked', null);
                    }
                } catch (err) {
                    // console.log(err, attributeName);
                }
            }
        }
    });

    function setGlobals(modelVals) {
        try {
            console.log('Lights: ' + modelVals['lights'].state);
            status_lights = modelVals['lights'].state == 'ON';
            status_filter = modelVals['filter'].state == 'ON';
            status_heater1 = modelVals['heater1'].state == 'ON';
            status_pool_spa_spillover = modelVals['pool'].state == 'ON';
        } catch (err) {

        }
    }

    function showStatus(str, buttonID, intendedVal) {

        var dtStart = new Date();
        $('#display3').text(str);
        toast.show();

        var checkInterval = setInterval(function() {
            tryCount++;
            var dtNow = new Date();
            var dtDiff = dtNow - dtStart;
            // Set the text of $('#toasttime') to the elapsed time in seconds
            $('#toasttime').text(`${Math.round(dtDiff / 1000)} seconds`);
            console.log('185', eval('status_' + buttonID), intendedVal);
            if (eval('status_' + buttonID) === intendedVal) {
                console.log('We did it!')
                toast.hide();
                clearInterval(checkInterval);
                dtStart = null;
            }
            if (tryCount > 60) {
                console.log('Failed to change state');
                toast.hide();
                alert('Failed to change state.  Try again.');
                clearInterval(checkInterval);
                dtStart = null;
                tryCount = 0;
            }
        }, 1000);
    }

    // Handler for menu buttons
    document.querySelectorAll('.button-menu').forEach(element => element.addEventListener('click', function() {
        buttonID = this.getAttribute('id');
        socket.emit('webCommand', { 'id': buttonID, 'modelVersion': modelVersion });
    }));

    // Handler for toggle buttons
    document.querySelectorAll('.button-toggle').forEach(element => element.addEventListener('click', function() {
        console.log('Clicked', this.getAttribute('checked'), $(this).val());
        buttonID = this.getAttribute('id');
        showStatus('Updating... Please wait for the request to complete.', buttonID, $(this).val() == "on");

        buttonID = this.getAttribute('id');
        if (buttonID == 'pool_spa_spillover') {
            buttonID = 'pool-spa-spillover';
        }
        socket.emit('webCommand', { 'id': buttonID, 'modelVersion': modelVersion });
        console.log('Toggled ' + buttonID);
    }));
});