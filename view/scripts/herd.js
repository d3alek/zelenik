function configure() {
    configuration_shown = document.getElementById('configuration').style.display === 'block';
    if (configuration_shown) {
        document.getElementById('configuration').style.display = 'none';
    }
    else {
        document.getElementById('configuration').style.display = 'block';
    }
}

AttachEvent(document.getElementById("show-configuration"), "click", configure);

var i;
var plot_image;
var plot;
var thing_names;
var j;
var enchanted;
var senses;
var desired;
var thing_name;
var displayables;

var plots = document.getElementById("plots").children;
for (i = 0; i < plots.length; i += 1) {
    plot = plots[i];
    plot_image = plot.children[0];
    thing_names = plot.classList;
    for (j = 0; j < thing_names.length; j += 1) {
        thing_name = thing_names[j];
        
        enchanted = JSON.parse(document.querySelectorAll("."+thing_name+".enchanted")[0].innerText);
        senses = enchanted.state.senses;
        desired = JSON.parse(document.querySelectorAll("."+thing_name+".desired")[0].textContent);
        displayables = JSON.parse(document.querySelectorAll("."+thing_name+".displayables")[0].innerText);
        initialize_plot(plot, plot_image, senses, desired.mode, enchanted.state.write, displayables, set_active, null, thing_name);
    }
}

var statuses = document.getElementById("statuses").children;
for (i = 0; i < statuses.length; i += 1) {
    s = statuses[i];
    thing_name = s.children[0].textContent;

    enchanted = JSON.parse(document.querySelectorAll("."+thing_name+".enchanted")[0].innerText);

    status_span = s.children[1];
    status_since_span = s.children[2];

    fillStatus(enchanted, status_span, status_since_span);

}

function set_active(e) {
    e = e || window.event;
    var target = e.target || e.srcElement;

    set_active_displayable(target);
}

function set_active_displayable(target) {
    if (!target.classList.contains("displayable")) {
        console.log("Going from " + target + " to parent " + target.parentElement);
        set_active_displayable(target.parentElement);
        return;
    }

    if (window.active) {
        window.active.classList.remove("active");
        if (window.active === target) {
            window.active = null;
            return;
        }
    }

    var classes = target.classList.toString();
    target.setAttribute("class", classes + " active");
    pretty_active_info(document.getElementById("active-info"), target);
    window.active = target;
}

function pretty_active_info(object, html) {
    object.innerHTML = "";
    var thing = html.dataset.thing;
    var text;
    if (html.tagName === "SPAN") {
        text = html.title + ": " + html.innerHTML;
        if (thing) {
            text += '. Повече <a href="/na/' + thing + '">' + thing + '</a>';
        }
        object.innerHTML = text;
    }
    else if (html.tagName === "DIV") {
        var div = document.createElement("div");
        var span = document.createElement("span");
        text = "Стойност: " + html.dataset.actual + " Желана: " + html.dataset.desired + " Автоматично: " + html.dataset.auto;
        span.innerHTML = text;
        div.appendChild(span);
        div.appendChild(switch_button(thing, html.id, "Включи", 1));
        div.appendChild(switch_button(thing, html.id, "Изключи", 0));
        div.appendChild(switch_button(thing,html.id, "Автоматично", "a"));
        object.appendChild(div);
    }
    else {
        object.innerHTML = "Cannot prettify active info for " + html;
    }
}

function switch_button(thing, switch_id, text, state) {
    var button = document.createElement("button");
    button.setAttribute("class", "button");
    button.innerText = text;
    button.setAttribute("data-switch-id", switch_id);
    button.setAttribute("data-state", state);
    button.setAttribute("data-thing", thing);
    AttachEvent(button, "click", post_desired_switch);
    return button;
}


function post_desired_switch(e) {
    e = e || window.event;
    var target = e.target || e.srcElement;

    var switch_id = target.dataset.switchId;
    var state = target.dataset.state;
    thing_name = target.dataset.thing;

    console.log("Setting " + switch_id + " to " + state + " for " + thing_name);

    var desiredInput = document.querySelectorAll("."+thing_name+".desired")[0];
    desired = JSON.parse(desiredInput.textContent);
    desired.mode[switch_id] = state;
    desiredInput.textContent = JSON.stringify(desired, null, 4);

    var desiredForm = document.querySelectorAll("."+thing_name+".desired-form")[0];
    desiredForm.submit();
}
