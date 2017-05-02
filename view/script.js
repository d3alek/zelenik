reported = JSON.parse(document.getElementById('reported').innerText)
senses = reported['state']['senses']

displayables = JSON.parse(document.getElementById('displayables-input').textContent)

plot = document.getElementById('plot')

for (key in senses) {
    // add a span element with id sense key and value sense value
    var span = document.createElement('span')
    span.setAttribute('id', key)
    span.setAttribute('class', 'sense')
    console.log(key)
    displayable = displayables[key]
    if (displayable) {
        p = displayable['position']
        if (p) {
            spl = p.split(',')
            t = spl[0]; l = spl[1]
            span.style = 'top:' + t + 'px;left:' + l +  'px;'
        }
    }
    value = senses[key]
    span.innerHTML = value
    plot.appendChild(span)
}

