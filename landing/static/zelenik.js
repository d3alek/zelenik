var summary = document.getElementById('summary');

function parseThingSummary(thing_summary) {
    var summary = JSON.parse(thing_summary);
    var summary_up = document.querySelector('#summary .up')
    var summary_down = document.querySelector('#summary .down')
    var summary_error = document.querySelector('#summary .error')
    console.log(JSON.stringify(summary));
    up_text = "живи";
    down_text = "неизвестни";
    error_text = "грешки";
    summary_up.innerHTML = up_text.substr(1) + " " + summary['up'].length
    summary_down.innerHTML = down_text.substr(1) + " " + summary['down'].length
    summary_error.innerHTML = error_text.substr(1) + " " + summary['error'].length
}

function fillThingSummary() {
    var xmlhttp = new XMLHttpRequest();

    xmlhttp.onreadystatechange = function() {
        if (xmlhttp.readyState == XMLHttpRequest.DONE ) {
            if (xmlhttp.status == 200) {
                parseThingSummary(xmlhttp.responseText);
            }
            else {
                console.log("error " + xmlhttp.status + " while getting thing-summary.json")
            }
        }
    };

    // Assumest blog runs on same host as zelenik portal
    xmlhttp.open("GET", "/thing-summary.json", true);
    xmlhttp.send();
}

fillThingSummary();
