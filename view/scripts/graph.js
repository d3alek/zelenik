function fill_graphable_checkboxes(senses, container) {
    for (var key in senses) {
        // We can have sense value, expected, ssd, from
        
        var sense = senses[key];
        var to_graph = [];
        var alias = key;

        if (key === 'time') {
            continue;
        }
        if (isNumeric(sense)) {
            // sense is just a single value 
            to_graph = to_graph.concat('value');
        }
        else {
            var keys = Object.keys(sense);
            keys.splice( keys.indexOf('alias'), 1 );
            to_graph = to_graph.concat(keys);
            if (senses[key]['alias']) {
                alias = senses[key]['alias'];
            } 
        }

        var ul = document.createElement('ul');
        ul.setAttribute('class', 'graphable-list float-left');
        header = document.createElement("span");
        header.setAttribute('class', 'graphable-list-header');
        header.textContent = alias;
        ul.appendChild(header);
        for (var i = 0; i < to_graph.length; ++i) {
            var graphable = to_graph[i];
            var li = document.createElement('li');
            var input = document.createElement('input');
            input.setAttribute('type', 'checkbox');
            input.setAttribute('name', 'graphable');
            input.setAttribute('value', key + "/" + graphable);
            input.setAttribute('id', key+'-'+graphable);
            var label = document.createElement('label');
            label.setAttribute('for', key+'-'+graphable);
            label.appendChild(input);
            label.appendChild(document.createTextNode(graphable));
            li.appendChild(label);
            ul.appendChild(li);
        }
        container.appendChild(ul);
    }
}
