margin = {top: 20, right: 80, bottom: 100, left: 80};
width = 960 - margin.left - margin.right,
  height = 500 - margin.top - margin.bottom;

var x = d3.scaleTime().range([0, width]),
    numbers_y = d3.scaleLinear().range([height/2, 0]),
    percents_y = d3.scaleLinear().range([height, height/2 + 10]),
    z = d3.scaleOrdinal(d3.schemeCategory10); // TODO remove
    writes_y = d3.scaleBand()

var numbers_line = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.date); })
    .y(function(d) { return numbers_y(d.value); });

var percents_line = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.date); })
    .y(function(d) { return percents_y(d.value); });

var writes_area = d3.area()
    .x(function(d) { return x(d.date); })
    .y1(function(d) { return writes_y(d.id); }) // TODO map d.id to writes_y range somehow
    .y0(function(d) { return writes_y(d.id) + writes_y.bandwidth(); })
    .defined(function(d) { return d.value !== 0; });

var displayables_config = JSON.parse(document.getElementById("displayables-input").textContent);
function getAlias(sense_id) {
  var config = displayables_config[sense_id];
  if (!config) return sense_id;
  var alias = config.alias;
  if (alias)
    return alias;
  else
    return sense_id;
};
function getColor(sense_id) {
  var config = displayables_config[sense_id];
  if (!config) return sense_id;
  var color = config.color;
  return color;
};

function fetch_and_redraw() {
  d3.event.preventDefault();
  d3.select(".loading").classed("hidden", false);
  since_days = this.dataset.sinceDays;
  since_hours = this.dataset.sinceHours;
  if (since_days) 
    query = "since_days=" + since_days
  if (since_hours)
    query = "since_hours=" + since_hours 

  d3.csv("history?" + query, type, redraw)
  d3.select(".graph-since[disabled]").attr("disabled", null);
  d3.select(this).attr("disabled", true);
};

d3.selectAll(".graph-since").on("click", fetch_and_redraw);

d3.select(".loading").classed("hidden", false);
d3.csv("history?since_hours=1", type, redraw);

function unwrap(wrapped) {
  return wrapped.split("(")[1].split(")")[0]
};

function redraw(error, data) {
  if (error) throw error;
  
  sense_columns = data.columns.slice(1).filter(function(d) {
    return d.lastIndexOf("sense(", 0) == 0;
  });
  visible_sense_columns = sense_columns.filter(function(d) {
    return displayables_config[unwrap(d)].graph == "yes";
  });

  var senses = visible_sense_columns.map(function(id) {
    return {
      id: unwrap(id),
      values: data.map(function(d) {
        return {date: d.date, value: d[id]};
      })
    };
  });
  var numbers = senses.filter(function(d) {
    return displayables_config[d.id].type !== "percent";
  });
  var percents = senses.filter(function(d) {
    return displayables_config[d.id].type == "percent";
  });

  write_columns = data.columns.slice(1).filter(function(d) {
    return d.lastIndexOf("write(", 0) == 0
  });
  var writes = write_columns.map(function(id) {
    return {
      id: unwrap(id),
      values: data.map(function(d) {
        return {date: d.date, value: d[id], "id":unwrap(id)};
      })
    };
  });

  x.domain(d3.extent(data, function(d) { return d.date; }));

  numbers_y.domain([
    d3.min(numbers, function(c) { return d3.min(c.values, function(d) { return d.value; }); }),
    d3.max(numbers, function(c) { return d3.max(c.values, function(d) { return d.value; }); })
  ]);

  percents_y.domain([0, 100]);

  //writes_y.range(write_columns.map(function(d) { return unwrap(d)}))
  write_height = 10;
  writes_length = write_columns.length;
  below_x = 30
  writes_y.range([height + 100, height + 30]);
  writes_y.domain(write_columns.map(function(d) { return unwrap(d)}))
  //  writes_y.domain(d3.range(0, write_columns.length))

  z.domain(senses.map(function(c) { return c.id; }));

  var dict = {"numbers": numbers, "percents": percents, "writes": writes};
  var svg = d3.select("#graph")
    .selectAll("svg")
    .data([dict])
      
  var svgEnter = svg.enter().append("svg")

  var gEnter = svgEnter
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

  svgEnter.merge(svg).attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  gEnter.append("g")
        .attr("class", "axis axis--x")
        .attr("transform", "translate(0," + height + ")")

  gEnter.append("g")
        .attr("class", "axis axis-numbers-y")
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("dy", "0.71em")
          .attr("fill", "#000")
          .text("Numbers");

  gEnter.append("g")
        .attr("class", "axis axis-percents-y")
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("x", - (height/2)) // because of the transform above
          .attr("dy", "0.71em")
          .attr("fill", "#000")
          .text("Percents");

  gEnter.append("g")
        .attr("class", "axis axis-writes-y")
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("x", - (height + 30)) // because of the transform above
          .attr("dy", "0.71em")
          .attr("fill", "#000")
          .text("Writes");

  var g = svgEnter.merge(svg).select("g");
  g.select("g.axis.axis--x").transition().call(d3.axisBottom(x));
  g.select("g.axis.axis-numbers-y").transition().call(d3.axisLeft(numbers_y));
  g.select("g.axis.axis-percents-y").transition().call(d3.axisLeft(percents_y));
  g.select("g.axis.axis-writes-y").transition().call(d3.axisLeft(writes_y).tickFormat(getAlias));

  var number = g.selectAll(".number")
    .data(function(d) { return d["numbers"]; }, function(d) {return d.id; });

  var numberEnter = number.enter()
    .append("g")
    .attr("class", "number");

  numberEnter.append("path")
    .attr("class", "line");

  numberEnter.append("text")
    .attr("x", 3)
    .attr("dy", "0.35em")
    .style("font", "10px sans-serif");
  
  numberEnter.merge(number).select("path.line")
    .style("stroke", function(d) { return getColor(d.id); })
    .transition() 
      .attr("d", function(d) { return numbers_line(d.values); })
 
  numberEnter.merge(number).select("text")
    .datum(function(d) { return {id: d.id, value: d.values[d.values.length - 1]}; })
    .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + numbers_y(d.value.value) + ")"; })
    .text(function(d) { return getAlias(d.id); });

  number.exit()
    .remove();

  var percent = g.selectAll(".percent")
    .data(function(d) { return d["percents"]; }, function(d) {return d.id; });

  var percentEnter = percent.enter()
    .append("g")
    .attr("class", "percent");

  percentEnter.append("path")
    .attr("class", "line");

  percentEnter.append("text")
    .attr("x", 3)
    .attr("dy", "0.35em")
    .style("font", "10px sans-serif");
  
  percentEnter.merge(percent).select("path.line")
    .style("stroke", function(d) { return getColor(d.id); })
    .transition() 
      .attr("d", function(d) { return percents_line(d.values); })
 
  percentEnter.merge(percent).select("text")
    .datum(function(d) { return {id: d.id, value: d.values[d.values.length - 1]}; })
    .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + percents_y(d.value.value) + ")"; })
    .text(function(d) { return getAlias(d.id); });

  percent.exit()
    .remove();

  var write = g.selectAll(".write")
    .data(function(d) { return d["writes"]; }, function(d) {return d.id; });

  var writeEnter = write.enter()
    .append("g")
    .attr("class", "write");

  writeEnter.append("path")
    .attr("class", "area");

  writeEnter.append("text")
    .attr("x", 3)
    .attr("dy", writes_y.bandwidth()/2 + 6)
    .style("font", "10px sans-serif");
  
  writeEnter.merge(write).select("path.area")
    .style("fill", function(d) { return getColor(d.id); })
    .transition() 
      .attr("d", function(d) { return writes_area(d.values); })
 
  write.exit()
    .remove();

  d3.select(".loading").classed("hidden", true);

  var mouseG = svgEnter.append("g")
    .attr("class", "mouse-over-effects")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

  mouseG.enter().append("path") // black vertical line to follow mouse
    .attr("class", "mouse-line")
    .style("stroke", "black")
    .style("stroke-width", "1px")
    .style("opacity", "0");

  var lines = document.getElementsByClassName('line'); // todo use d3 selector
  var mousePerLineEnter = mouseG.selectAll('.mouse-per-line')
    .data(function(d) { return d.numbers; })
    .enter()
    .append("g")
    .attr("class", "mouse-per-line");

  mousePerLineEnter.append("circle")
    .attr("r", 7)
    .style("stroke", function(d) {
      return getColor(d.id)
    })
    .style("fill", "none")
    .style("stroke-width", "1px")
    .style("opacity", "0");

  mousePerLineEnter.append("text")
    .attr("transform", "translate(10,3)");

  mouseG.append("svg:rect") // append a rect to catch mouse movements on canvas<Paste>
    .attr("width", width + margin.left + margin.right)
		.attr("height", height + margin.top + margin.bottom)
		.attr("fill", "none")
		.attr("pointer-events", "all")
		.on("mouseout", function() { // hide line, circles and text
			d3.select(".mouse-line")
				.style("opacity", "1");
			d3.selectAll(".mouse-per-line circle")
      	.style("opacity", "1");
			d3.selectAll(".mouse-per-line text")
      	.style("opacity", "1");
		})
		.on("mousemove", function() { 
			var mouse = d3.mouse(this);
			d3.select(".mouse-line")
				.attr("d", function() {
					var d = "M" + mouse[0] + "," + height;
					d += " " + mouse[0] + "," + 0;
					return d;
				});
			d3.selectAll(".mouse-per-line")
				.attr("transform", function(d, i) {
					console.log(d);
					console.log(width/mouse[0]);
					var xDate = x.invert(mouse[0]),
							bisect = d3.bisector(function(d) { return d.date; }).right;
					var idx = bisect(d.values, xDate);

					var beginning = 0,
							end = lines[i].getTotalLength(),
							target = null;

					while (true) {
						target = Math.floor((beginning + end) / 2);
						pos = lines[i].getPointAtLength(target);
						if ((target === end || target === beginning) && pos.x !== mouse[0]) {
							break;
						}
						if (pos.x > mouse[0])      end = target;
						else if (pos.x < mouse[0]) beginning = target;
						else break; //position found
					}

					d3.select(this).select("text")
						.text(numbers_y.invert(pos.y).toFixed(2));

					return "translate(" + mouse[0] + "," + pos.y + ")";
				});
		});
};

function type(d, _, columns) {
  d.date = moment.utc(d.timestamp_utc)._d;
  for (var i = 1, n = columns.length, c; i < n; ++i) d[c = columns[i]] = +d[c];
  return d;
}
