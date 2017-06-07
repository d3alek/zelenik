function initialize_plot(plot_image, senses, desired_modes, reported_writes, displayables_config, span_click_event, plot_click_event, thing_name) {
    for (key in senses) {
        if (key === 'time') {
            continue;
        }
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

    for (key in desired_modes) {
        var div = document.createElement('div')
        div.setAttribute('id', key)
        div.setAttribute('class', 'displayable switch')
        div.setAttribute('data-thing', thing_name)

        displayable = displayables_config[key]
        if (displayable && displayable['plot'] == 'yes') {
            p = displayable['position']
            if (p) {
                spl = p.split(',')
                t = spl[0]; l = spl[1]
                div.style = 'top:' + t + 'px;left:' + l +  'px;'
            }
            alias = displayable['alias']

            if (!alias) {
                alias = key
            }

            div.setAttribute('title', alias);
            color = displayable['color']
            if (!color) {
                color = 'black' // green
            }

            div.style['border-color'] = color
            
            if (span_click_event) {
                AttachEvent(div, 'click', span_click_event)
            }

            type = displayable['type']
            value_string = parseFloat(value).toFixed(1)
            desired_value = extract_value(desired_modes[key])
            actual_value = extract_value(reported_writes[key])
            auto = desired_value == 'a'

            checked_or_nothing = actual_value == 1 ? "checked" : ""
            div.setAttribute('data-desired', desired_value)
            div.setAttribute('data-actual', actual_value)
            div.setAttribute('data-auto', auto)

            if (type == 'switch') {
                if (auto || parseInt(desired_value) == actual_value) {
                if (auto) {
                    hidden_or_nothing = ''
                }
                else {
                    hidden_or_nothing = 'hidden'
                }
                value_string = `
                    <div class="onoffswitch">
                        <input type="checkbox" name="onoffswitch" class="onoffswitch-checkbox `+key+ `"` + checked_or_nothing + `/>
                        <label class="onoffswitch-label" for="`+key+`">
                            <span class="onoffswitch-inner"></span>
                            <span class="onoffswitch-switch"></span>
                        </label>
                        <span class="switch-auto-text `+hidden_or_nothing+`">A</span>
                    </div>`
                }
                else {
                    value_string =`<i id="`+key+`-loading" class="icon-spin animate-spin"></i>
                        `;
                }
            }
            div.innerHTML = value_string
            plot.appendChild(div)
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

function extract_value(raw_value) {
    if (isNumeric(raw_value) || raw_value == "a") {
        return raw_value;
    }
    try {
        if ('normalized' in raw_value) {
            return raw_value['normalized'];
        }
        if ('value' in raw_value) {
            return raw_value['value'];
        }
        if ('expected' in raw_value) { 
            return raw_value['expected'];
        }
    }
    catch (e) {
        console.log("Exception: " + e);
    }
    console.log("Could not extract value. Expected a dict with element 'value' or 'expected' but got " + raw_value);
    return raw_value;
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
