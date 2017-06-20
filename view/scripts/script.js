var INITIAL = "initial";
var MOVE_DISPLAYABLES = "move-displayables";

window.state = INITIAL;

var enchanted = JSON.parse(document.getElementById("enchanted").innerText);
var senses = enchanted.state.senses;

var desired = JSON.parse(document.getElementById("desired-input").textContent);

var displayables_config = JSON.parse(document.getElementById("displayables-input").textContent);

document.getElementById("change-plot").style.display = "none";

var plot = document.getElementById("plot");
var plot_image = document.getElementsByClassName("plot-image")[0];

AttachEvent(document.getElementById("plot-input"), "change", function() {
    document.getElementById("change-plot").style.display = "initial";
    plot_image.src = plot_image.src + "?refresh=yes";
});

fill_graphable_checkboxes(senses, document.getElementById("graphable-checkboxes"));

if (!plot_image.complete) {
    AttachEvent(plot_image, "load", initialize_or_hide_plot);
}
else {
    initialize_or_hide_plot();
}

function initialize_or_hide_plot() {
    if (imageOk(plot_image)) {
        initialize_plot(plot, plot_image, senses, desired.mode, enchanted.state.write, displayables_config, set_active, move_to_click_position);
    }
    else {
        plot.style.display = "none";
        document.getElementById("change-plot-positions").style.display = "none";
    }
}

// src http://stackoverflow.com/a/1977898;
function imageOk(img) {
    // During the onload event, IE correctly identifies any images that
    // weren’t downloaded as not complete. Others should too. Gecko-based
    // browsers act like NS4 in that they report this incorrectly.
    if (!img.complete) {
        return false;
    }

    // However, they do have two very useful properties: naturalWidth and
    // naturalHeight. These give the true size of the image. If it failed
    // to load, either of these should be zero.;

    if (img.naturalWidth === undefined && img.naturalWidth === 0) {
        return false;
    }

    // No other way of checking: assume it’s ok.
    return true;
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
    if (html.tagName === "SPAN") {
        object.innerHTML = html.title + ": " + html.innerHTML;
    }
    else if (html.tagName === "DIV") {
        var div = document.createElement("div");
        var span = document.createElement("span");
        text = "Стойност: " + html.dataset.actual + " Желана: " + html.dataset.desired + " Автоматично: " + html.dataset.auto;
        span.innerHTML = text;
        div.appendChild(span);
        div.appendChild(switch_button(html.id, "Включи", 1));
        div.appendChild(switch_button(html.id, "Изключи", 0));
        div.appendChild(switch_button(html.id, "Автоматично", "a"));
        object.appendChild(div);
    }
    else {
        object.innerHTML = "Cannot prettify active info for " + html;
    }
}

function switch_button(switch_id, text, state) {
    var button = document.createElement("button");
    button.setAttribute("class", "button");
    button.innerText = text;
    button.setAttribute("data-switch-id", switch_id);
    button.setAttribute("data-state", state);
    AttachEvent(button, "click", post_desired_switch);
    return button;
}

function move_to_click_position(e) {
    if (window.state !== MOVE_DISPLAYABLES) {
        return;
    }
    e = e || window.event;
    var target = e.currentTarget || e.srcElement;

    if (window.active) {
        var theThing = window.active;
        var parentPosition = getPosition(target);
        var xPosition = e.clientX - parentPosition.x - (theThing.clientWidth / 2);
        var yPosition = e.clientY - parentPosition.y - (theThing.clientHeight / 2);

        theThing.style.left = xPosition + "px";
        theThing.style.top = yPosition + "px";
    }
}

function getPosition(el) {
    var xPos = 0;
    var yPos = 0;

    while (el) {
        if (el.tagName === "BODY") {
            // deal with browser quirks with body/window/document and page scroll
            var xScroll = el.scrollLeft || document.documentElement.scrollLeft;
            var yScroll = el.scrollTop || document.documentElement.scrollTop;

            xPos += (el.offsetLeft - xScroll + el.clientLeft);
            yPos += (el.offsetTop - yScroll + el.clientTop);
        } else {
            // for all other non-BODY elements;
            xPos += (el.offsetLeft - el.scrollLeft + el.clientLeft);
            yPos += (el.offsetTop - el.scrollTop + el.clientTop);
        }

        el = el.offsetParent;
    }
    return {
        x: xPos,
        y: yPos
    };
}

function change_plot_positions(e) {
    e = e || window.event;
    var target = e.target || e.srcElement;

    if (target.textContent === "Премести") {
        window.state = MOVE_DISPLAYABLES;

        target.textContent = "Запази";
    }
    else if (target.textContent === "Запази") {
        window.state = INITIAL;
        var displayables = document.getElementsByClassName("displayable");
        displayables_config = JSON.parse(document.getElementById("displayables-input").textContent);
        var i;
        for (i = 0; i < displayables.length; i += 1) {
            var displayable = displayables[i];
            var key = displayable.id;
            var displayable_config = displayables_config[key];
            if (displayable_config) {
                var t = displayable.style.top;
                if (t.endsWith("px")) {
                    t = t.substring(0, t.length-2);
                }

                var l = displayable.style.left;
                if (l.endsWith("px")) {
                    l = l.substring(0, l.length-2);
                }
                displayables_config[key].position = t + "," + l;
            }
        }

        post_displayables(displayables_config);
    }
    else {
        console.log("Ignoring click as unexpected textContent of", target);
    }
}

function post_displayables(displayables_config) {
    var displayables_input = document.getElementById("displayables-input");
    displayables_input.textContent = JSON.stringify(displayables_config, null, 4);
    var displayables_form = document.getElementById("displayables-form");
    displayables_form.submit();
}

function post_desired_switch(e) {
    e = e || window.event;
    var target = e.target || e.srcElement;

    var switch_id = target.dataset.switchId;
    var state = target.dataset.state;

    console.log("Setting " + switch_id + " to " + state);
    var desiredInput = document.getElementById("desired-input");
    desired = JSON.parse(desiredInput.textContent);
    desired.mode[switch_id] = state;
    desiredInput.textContent = JSON.stringify(desired, null, 4);

    var desiredForm = document.getElementById("desired-form");
    desiredForm.submit();
}
