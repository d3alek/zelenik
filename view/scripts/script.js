reported = JSON.parse(document.getElementById('reported').innerText)
senses = reported['state']['senses']

displayables = JSON.parse(document.getElementById('displayables-input').textContent)

plot = document.getElementById('plot')

function extract_value(sense) {
    if (typeof sense == 'object') {
        value = sense['value']
        if (value) {
            return value
        }
    }

    return sense 
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

function print_click_position(e) {
    if (window.active) {
        theThing = window.active
        parentPosition = getPosition(e.currentTarget)
        xPosition = e.clientX - parentPosition.x - (theThing.clientWidth / 2)
        yPosition = e.clientY - parentPosition.y - (theThing.clientHeight / 2)

        console.log(xPosition, yPosition)
        theThing.style.left = xPosition + "px";
        theThing.style.top = yPosition + "px";
    }
}

function set_active(sense) {
    if (window.active) {
        window.active.setAttribute('class', 'sense')
    }
    sense.setAttribute('class', 'active sense')
    window.active = sense
}

for (key in senses) {
    var span = document.createElement('span')
    span.setAttribute('id', key)
    span.setAttribute('class', 'sense')

    value = extract_value(senses[key])

    displayable = displayables[key]
    if (displayable) {
        p = displayable['position']
        if (p) {
            spl = p.split(',')
            t = spl[0]; l = spl[1]
            span.style = 'top:' + t + 'px;left:' + l +  'px;'
        }
        alias = displayable['alias']

        if (!alias) {
            alias = key
        }

        span.setAttribute('title', alias);
        span.setAttribute('onclick', "set_active("+key+")")

        type = displayable['type']
        if (type == 'percent') {
            value = value + '%'
        }
        else if (type == 'temp') {
            value = value + '°'
        }
    }

    span.innerHTML = value
    plot.appendChild(span)
}

document.getElementById('plot').addEventListener("click", print_click_position, false);
