plots = document.getElementById('plots').children
for (i = 0; i < plots.length; ++i) {
    plot = plots[i]
    plot_image = plot.children[0]
    thing_names = plot.classList
    for (j = 0; j < thing_names.length; ++j) {
        thing_name = thing_names[j]
        
        reported = JSON.parse(document.querySelectorAll('.'+thing_name+'.reported')[0].innerText)
        senses = reported['state']['senses']
        displayables = JSON.parse(document.querySelectorAll('.'+thing_name+'.displayables')[0].innerText)
        initialize_plot(plot_image, senses, displayables, set_active, null, thing_name)
    }
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
    active_info = target.title + ": " + target.innerHTML 

    thing_name = target.getAttribute('data-thing')
    active_info += " Повече: " + '<a href="/na/' + thing_name + '">' + thing_name + '</a>'

    document.getElementById('active-info').innerHTML = active_info
    window.active = target
}



