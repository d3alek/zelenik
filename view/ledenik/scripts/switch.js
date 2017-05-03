// Reloading
// Modified from: http://stackoverflow.com/a/11405793
var reloading;

function checkReloading() {
    if (window.location.hash=="#noautoreload") {
        document.getElementById("reloadCB").checked=false;
    }
    else {
        reloading=setTimeout("window.location.reload();", 5000);
        document.getElementById("reloadCB").checked=true;
    }
}

function toggleAutoRefresh(cb) {
    if (cb.checked) {
        window.location.replace("#");
        reloading=setTimeout("window.location.reload();", 5000);
    } else {
        window.location.replace("#noautoreload");
        clearTimeout(reloading);
    }
}

checkReloading();

// -Reloading

// Configuration
document.getElementById('configuration').style.display = 'none'

function configure() {
    configuration_shown = 
    document.getElementById('configuration').style.display == 'block'
    if (configuration_shown) {
        document.getElementById('configuration').style.display = 'none'
    }
    else {
        document.getElementById('configuration').style.display = 'block'
    }
}

// -Configuration

// Switches

reported = JSON.parse(document.getElementById('reported').innerText)
write = reported['state']['write']

desiredInput = document.getElementById('desired-input')
desired_mode = JSON.parse(desiredInput.textContent)['mode']

for (output in write) {
    checkbox = document.getElementById(output)
    loading = document.getElementById(output+'-loading')
    reported_checked = write[output]
    desired_checked = desired_mode[output]
    if (reported_checked == desired_checked) {
        checkbox.checked = write[output]
        checkbox.setAttribute("onclick", "postToServer("+output+")")
        loading.style.display = 'none'
    }
    else {
        checkbox.parentElement.style.display = 'none'
    }
}

function postToServer(checkbox) {
    checked = checkbox.checked == true ? 1 : 0
    output = checkbox.id
    console.log("Setting " + output + " to " + checked)
    desiredInput = document.getElementById('desired-input')
    desired = JSON.parse(desiredInput.textContent)
    desired['mode'][output] = checked
    desiredInput.textContent = JSON.stringify(desired, null, 4)

    desiredForm = document.getElementById('desired-form')
    desiredForm.submit()
}

// -Switches

// Stale data warning
reported_utc = new Date(reported['timestamp_utc'] + "Z") // Adding Z so that parse assumes UTC 
reported_millis = reported_utc.getTime() // reported utc time in millis
now_millis = new Date().getTime() // current utc time in millis 

if (now_millis - reported_millis > 1000*60) {
    connection_problem = document.getElementById('connection-problem')
    connection_problem_text = document.getElementById('connection-problem-text')
    connection_problem_text.textContent = connection_problem_text.textContent + " от " + reported_utc.toLocaleString()
    connection_problem.style.display = 'block'
}


// --Stale data warning
