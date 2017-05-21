function initialize_plot(plot_image, senses, displayables_config, span_click_event, plot_click_event, thing_name) {
    for (key in senses) {
        var span = document.createElement('span')
        span.setAttribute('id', key)
        span.setAttribute('class', 'displayable')
        span.setAttribute('data-thing', thing_name)

        value = extract_value(senses[key])

        displayable = displayables_config[key]
        if (displayable && displayable['plot'] == 'yes') {
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
            color = displayable['color']
            if (!color) {
                color = 'black' // green
            }

            span.style['border-color'] = color
            if (span_click_event) {
                AttachEvent(span, 'click', span_click_event)
            }

            type = displayable['type']
            value_string = parseFloat(value).toFixed(1)
            if (type == 'percent') {
                value_string = value_string + '%'
            }
            else if (type == 'temp') {
                value_string = value_string + '°'
            }
            span.innerHTML = value_string
            plot.appendChild(span)
        }

    }

    if (plot_click_event) {
        AttachEvent(document.getElementById('plot'),"click", plot_click_event);
    }

    change_plot_positions_btn = document.getElementById("change-plot-positions");
    if (change_plot_positions_btn != null) {
        AttachEvent(change_plot_positions_btn, "click", change_plot_positions);
    }

    makeUnselectable(plot_image)
}

function extract_value(sense) {
    if (isNumeric(sense)) {
        return sense;
    }
    try {
        return sense['value']
    }
    catch (e) {
        console.log("Could not extract value. Expected a dict with element 'value' but got " + sense + "." + e);
        return sense
    }
}

// src: http://stackoverflow.com/a/13407898
function makeUnselectable( target ) {
    target.setAttribute('class', 'unselectable')
    target.setAttribute('unselectable', 'on')
    target.setAttribute('draggable', 'false')
    target.setAttribute('ondragstart', 'return false;')
}
// source: http://stackoverflow.com/a/1830844 
function isNumeric(n) {
  return !isNaN(parseFloat(n)) && isFinite(n);
}
