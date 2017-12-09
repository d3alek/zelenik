margin = {top: 20, right: 80, bottom: 30, left: 50};
width = 960 - margin.left - margin.right,
  height = 500 - margin.top - margin.bottom;

var x = d3.scaleTime().range([0, width]),
    y = d3.scaleLinear().range([height, 0]),
    z = d3.scaleOrdinal(d3.schemeCategory10);

var line = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.date); })
    .y(function(d) { return y(d.value); });

d3.selectAll(".graph-since").on("click", function() {
  d3.event.preventDefault();
  console.log(this.dataset.url);
  d3.csv(this.dataset.url, type, redraw);
  d3.select(".graph-since[disabled]").attr("disabled", null);
  d3.select(this).attr("disabled", true);
});

d3.csv("senses", type, redraw);

function redraw(error, data) {
  if (error) throw error;
  
  console.log(data.columns)
  console.log(data.columns.slice(1))
  var senses = data.columns.slice(1).map(function(id) {
    return {
      id: id,
      values: data.map(function(d) {
        return {date: d.date, value: d[id]};
      })
    };
  });
  console.log(senses)

  x.domain(d3.extent(data, function(d) { return d.date; }));

  y.domain([
    d3.min(senses, function(c) { return d3.min(c.values, function(d) { return d.value; }); }),
    d3.max(senses, function(c) { return d3.max(c.values, function(d) { return d.value; }); })
  ]);

  z.domain(senses.map(function(c) { return c.id; }));

  var svg = d3.select("#graph")
    .selectAll("svg")
    .data([senses])
      
  console.log(svg)

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
        .attr("class", "axis axis--y")
        .append("text")
        .attr("transform", "rotate(-90)")
        .attr("y", 6)
        .attr("dy", "0.71em")
        .attr("fill", "#000")
        .text("Temperature, ºF");

  var g = svgEnter.merge(svg).select("g");
  g.select("g.axis.axis--x").transition().call(d3.axisBottom(x));
  g.select("g.axis.axis--y").transition().call(d3.axisLeft(y))

  var sense = g.selectAll(".sense")
    .data(function(d) { return d; }, function(d) {return d.id; });
  console.log(sense)

  var senseEnter = sense.enter()
    .append("g")
    .attr("class", "sense");

  senseEnter.append("path")
    .attr("class", "line");

  senseEnter.append("text")
    .attr("x", 3)
    .attr("dy", "0.35em")
    .style("font", "10px sans-serif");
  
  senseEnter.merge(sense).select("path.line")
    .style("stroke", function(d) { return z(d.id); })
    .transition() 
      .attr("d", function(d) { return line(d.values); })
 
  senseEnter.merge(sense).select("text")
    .datum(function(d) { return {id: d.id, value: d.values[d.values.length - 1]}; })
    .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + y(d.value.value) + ")"; })
    .text(function(d) { return d.id; });

  sense.exit()
    .remove();
};

function type(d, _, columns) {
  d.date = moment.utc(d.timestamp_utc)._d;
  for (var i = 1, n = columns.length, c; i < n; ++i) d[c = columns[i]] = +d[c];
  return d;
}
