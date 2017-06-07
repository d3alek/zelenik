function fill_graphable_checkboxes(senses, container) {
    var sense;
    var to_graph;
    var alias;
    var key;
    var keys;
    var ul;
    var graphable;
    var li;
    var input;
    var i;
    var label;
    var header;
    for (key in senses) {
        // We can have sense value, expected, ssd, from
        
        sense = senses[key];
        to_graph = [];
        alias = key;

        if (key === "time") {
            continue;
        }
        if (isNumeric(sense)) {
            // sense is just a single value 
            to_graph = to_graph.concat("value");
        }
        else {
            keys = Object.keys(sense);
            if ("alias" in senses[key]) {
                alias = senses[key].alias;
                keys.splice( keys.indexOf("alias"), 1 );
            } 
            if (keys.indexOf("value") === -1) {
                to_graph = to_graph.concat("value"); // always give option to graph value 
            }
            if (keys.indexOf("wrong") === -1) {
                to_graph = to_graph.concat("wrong"); // always give option to graph wrong 
            }
            to_graph = to_graph.concat(keys);
        }

        ul = document.createElement("ul");
        ul.setAttribute("class", "graphable-list float-left");
        header = document.createElement("span");
        header.setAttribute("class", "graphable-list-header");
        header.textContent = alias;
        ul.appendChild(header);
        for (i = 0; i < to_graph.length; i += 1) {
            graphable = to_graph[i];
            li = document.createElement("li");
            input = document.createElement("input");
            input.setAttribute("type", "checkbox");
            input.setAttribute("name", "graphable");
            input.setAttribute("value", key + "/" + graphable);
            input.setAttribute("id", key+"-"+graphable);
            label = document.createElement("label");
            label.setAttribute("for", key+"-"+graphable);
            label.appendChild(input);
            label.appendChild(document.createTextNode(graphable));
            li.appendChild(label);
            ul.appendChild(li);
        }
        container.appendChild(ul);
    }
}
