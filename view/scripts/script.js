INITIAL = 'initial'
MOVE_DISPLAYABLES = 'move-displayables'

window.state = INITIAL

reported = JSON.parse(document.getElementById('reported').innerText)
senses = reported['state']['senses']

displayables_config = JSON.parse(document.getElementById('displayables-input').textContent)

plot = document.getElementById('plot')

document.getElementById('change-plot').style.display = 'none'


plot_image = document.getElementsByClassName('plot-image')[0]

AttachEvent(document.getElementById('plot-input'), 'change', function() { 
    document.getElementById('change-plot').style.display = 'initial';
    plot_image.src = plot_image.src + '?refresh=yes'
});


if (!plot_image.complete) {
    AttachEvent(plot_image, 'load', initialize_or_hide_plot)
}
else {
    initialize_or_hide_plot()
}

function initialize_or_hide_plot() {
    if (imageOk(plot_image)) {
        initialize_plot(plot_image, senses, displayables_config, set_active, move_to_click_position);
    }
    else {
        plot.style.display = 'none'
        document.getElementById('change-plot-positions').style.display = 'none'
    }
}

// src http://stackoverflow.com/a/1977898
function imageOk(img) {
    // During the onload event, IE correctly identifies any images that
    // weren’t downloaded as not complete. Others should too. Gecko-based
    // browsers act like NS4 in that they report this incorrectly.
    if (!img.complete) {
        return false;
    }

    // However, they do have two very useful properties: naturalWidth and
    // naturalHeight. These give the true size of the image. If it failed
    // to load, either of these should be zero.

    if (typeof img.naturalWidth !== "undefined" && img.naturalWidth === 0) {
        return false;
    }

    // No other way of checking: assume it’s ok.
    return true;
}

function set_active(e) {
    e = e || window.event
    var target = e.target || e.srcElement;

    if (window.active) {
        window.active.setAttribute('class', 'displayable')
        if (window.active === target) {
            window.active = null;
            return;
        }
    }
    target.setAttribute('class', 'active displayable')
    document.getElementById('active-info').textContent = target.title + ": " + target.innerHTML
    window.active = target
}

function move_to_click_position(e) {
    if (window.state != MOVE_DISPLAYABLES) {
        return
    }
	e = e || window.event;
	var target = e.currentTarget || e.srcElement;

    if (window.active) {
        theThing = window.active
        parentPosition = getPosition(target)
        xPosition = e.clientX - parentPosition.x - (theThing.clientWidth / 2)
        yPosition = e.clientY - parentPosition.y - (theThing.clientHeight / 2)

        theThing.style.left = xPosition + "px";
        theThing.style.top = yPosition + "px";
    }
}

function getPosition(el) {
    var xPos = 0;
    var yPos = 0;

    while (el) {
        if (el.tagName == "BODY") {
            // deal with browser quirks with body/window/document and page scroll
            var xScroll = el.scrollLeft || document.documentElement.scrollLeft;
            var yScroll = el.scrollTop || document.documentElement.scrollTop;

            xPos += (el.offsetLeft - xScroll + el.clientLeft);
            yPos += (el.offsetTop - yScroll + el.clientTop);
        } else {
            // for all other non-BODY elements
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

    if (target.textContent == 'Премести') {
        window.state = MOVE_DISPLAYABLES

        target.textContent = 'Запази'
    }
    else if (target.textContent == 'Запази') {
        window.state = INITIAL
        displayables = document.getElementsByClassName('displayable')
        displayables_config = JSON.parse(document.getElementById('displayables-input').textContent)

        for (i = 0; i < displayables.length; ++i) {
            displayable = displayables[i]
            key = displayable.id
            displayable_config = displayables_config[key]
            if (displayable_config) {
                t = displayable.style.top
                if (t.endsWith('px')) {
                    t = t.substring(0, t.length-2)
                }

                l = displayable.style.left
                if (l.endsWith('px')) {
                    l = l.substring(0, l.length-2)
                }
                displayables_config[key]['position']=t + "," + l
            }
        }

        post_displayables(displayables_config)
    }
    else {
        console.log('Ignoring click as unexpected textContent of', target)
    }
}

function post_displayables(displayables_config) {
    displayables_input = document.getElementById('displayables-input')
    displayables_input.textContent = JSON.stringify(displayables_config, null, 4)
    displayables_form = document.getElementById('displayables-form') 
    displayables_form.submit()
}
