var
  map = L.map('map', {
    attributionControl: false
  }),
  info = {},
  tile_layer,
  index_histogram_chart,
  statistics,
  clip = false,
  clipped_min,
  clipped_max
;


function addTileLayer(info) {

  window.info = info;

  if (tile_layer) {
    map.removeLayer(tile_layer);
  }

  var bounds = L.latLngBounds(
    [info.bounds.slice(0, 2).reverse(), info.bounds.slice(2, 4).reverse()]
  );
  map.fitBounds(bounds);

  tile_layer = L.tileLayer(info.tiles.join(""), {
    bounds: bounds,
    minZoom: info.minzoom,
    maxZoom: L.Browser.retina ? (info.maxzoom + 1) : info.maxzoom,
    maxNativeZoom: L.Browser.retina ? (info.maxzoom - 1) : info.maxzoom,
    tms: info.scheme === "tms",
    opacity: 1,
    detectRetina: true
  });

  tile_layer.addTo(map);

}


function indices_of_base(base) {

  $("#index_histogram").html("");

  get_tiles_info(base);

  if (base == "rgb") {
    var selects = ["vari", "gli", "ior", "ngri"];
  } else if (base == "nir") {
    var selects = ["ndvi", "savi", "mnli", "osavi", "bai", "msr", "rdvi", "tdvi", "lai"];
  }

  var html = ["<option value='none'>None</option>"];

  for (select in selects) {
    html.push(
      "<option value='", selects[select], "'>", selects[select].toUpperCase(), "</option>"
    );
  }

  $("#vi").html(html.join(""));
}


function get_tiles_info(base) {
  $.ajax("/" + base + "_orthophoto/tiles.json").done(function(info) {
    addTileLayer(info);
  });
}


function renderIndexHistogram() {

  var
    holder = $("#index_histogram"),
    histogram_data = statistics.histogram_256
  ;

  if (index_histogram_chart) {
    index_histogram_chart.detach();
  }

  // Cap outliers so a single tall bar doesn't flatten the rest of the histogram.
  for (var el in histogram_data) {
      if (histogram_data[el] > 10000) {
          histogram_data[el] = 1000;
      }
  }

  var
      data = {
          labels: [statistics.min.toFixed(2), statistics.max.toFixed(2)],
          series: [
              histogram_data
          ]
      },
      options = {
          width: 279,
          height: 160,
          axisX: {
              offset: 15
          },
          axisY: {
              showLabel: false,
              offset: -2
          }
      },
      draw_counter = 0,
      color_map = generateColorMap("RdYlGn", 256)
  ;

  index_histogram_chart = new Chartist.Bar(holder[0], data, options);

  index_histogram_chart.on("draw", function(context) {
      if (context.type == "bar") {
          var color = color_map[draw_counter];
          draw_counter++;

          context.element.attr({
              style: "stroke-width: 1px; stroke: " + color
          });

          if (draw_counter >= histogram_data.length) {
              draw_counter = 0;
          }
      }
  });

  index_histogram_chart.on("created", function() {
      min_label = $(".ct-labels > foreignObject:eq(0)");
      max_label = $(".ct-labels > foreignObject:eq(1)");

      if (min_label[0]) {
          min_label[0].setAttribute("x", "0");
      }

      if (max_label[0]) {
          max_label[0].setAttribute("x", "254");
      }

      renderRangeInput(holder);
      reColorizeIndexHistogram();
  });
}


function findClippedMinMax() {
  var
      data = statistics.histogram_256,
      sum = data.reduce(add, 0),
      clip_3_percent = sum * .03,
      lower_sum = 0,
      upper_sum = 0,
      last_lower_i,
      last_upper_i
  ;

  for (var i = 0; i < data.length; i++) {
      if (lower_sum < clip_3_percent) {
          lower_sum += data[i];
          last_lower_i = i;
      }

      if (upper_sum < clip_3_percent) {
          upper_sum += data[data.length-1-i];
          last_upper_i = data.length-1-i;
      }
  }

  clipped_min = math_map_value(last_lower_i, 0, 255, statistics.min, statistics.max);
  clipped_max = math_map_value(last_upper_i, 0, 255, statistics.min, statistics.max);
}


function add(a, b) {
  return a + b;
}


function math_map_value(value, in_low, in_high, to_low, to_high) {
  return to_low + (value - in_low) * (to_high - to_low) / (in_high - in_low);
}


function generateColorMap(colormap, nshades) {
  var
      step = 1/(nshades-1),
      result = []
  ;
  for (var i = 0; i <= (nshades-1); i++) {
      var color = d3.interpolateRdYlGn(i * step);
      result.push(color);
  }

  return result;
}


function renderRangeInput(holder) {

  var range_holder = $("#range_selector");
  if (range_holder[0]) {
      range_holder.remove();
  }

  if (clip) {
      var value = clipped_min + "," + clipped_max;

      updateMinMaxLabels(clipped_min, clipped_max);
  } else {
      var value = statistics.min + "," + statistics.max;
  }

  var range = $("<div id='range_selector'><input type='range' multiple min='" + statistics.min + "' max='" + statistics.max + "' value='" + value + "' step='0.0001' style='width: 271px' /></div>");
  holder.append(range);

  multirange.init();

  $("#range_selector input").on("change", function() {

      clip = true;

      clipped_min = this.valueLow;
      clipped_max = this.valueHigh;
      changeTileLayer();

      reColorizeIndexHistogram();

  });

  $("#range_selector input").on("input", function() {
      updateMinMaxLabels(this.valueLow, this.valueHigh);
  });
}


function updateMinMaxLabels(valueLow, valueHigh) {
  if (min_label && min_label[0]) {
      min_label[0].childNodes[0].innerText = valueLow.toFixed(2);
      max_label[0].childNodes[0].innerText = valueHigh.toFixed(2);
      min_label[0].setAttribute("x", math_map_value(valueLow, statistics.min, statistics.max, 0, 254));
      max_label[0].setAttribute("x", math_map_value(valueHigh, statistics.min, statistics.max, 0, 254));
  }
}


function reColorizeIndexHistogram() {
  if (clip) {
      var
          counter_min = Math.floor(math_map_value(clipped_min, statistics.min, statistics.max, 0, 255)),
          counter_max = Math.floor(math_map_value(clipped_max, statistics.min, statistics.max, 0, 255)),
          colors_needed = (counter_max - counter_min) + 1,
          color_map = generateColorMap("RdYlGn", colors_needed),
          color_counter = 0
      ;

      var bars = $("#index_histogram svg .ct-series line");
      bars.each(function(i) {
          if (i <= counter_min) {
              var color = color_map[0];
          } else if (i >= counter_max) {
              var color = color_map[color_map.length-1];
          } else {
              var color = color_map[color_counter];
              color_counter++;
          }
          this.style = "stroke-width: 1px; stroke: " + color;
      });
  }
}


function changeTileLayer() {
  var
      min = statistics.min,
      max = statistics.max
  ;

  if (clip) {
      min = clipped_min;
      max = clipped_max;
  }

  var
    base = $("#base").val(),
    val = $("#vi").val(),
    tile_url = ["/vegetation_index?index=", val, "&min=", min, "&max=", max, "&tile=", base, "_tiles/{z}/{x}/{y}.png"]
  ;

  tile_layer.setUrl(tile_url.join(""));
}


var basemaps = {
  'Google Maps Hybrid': L.tileLayer('//{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', {
      subdomains: ['mt0','mt1','mt2','mt3'],
      maxZoom: 21,
      minZoom: 0,
      label: 'Google Maps Hybrid'
  }).addTo(map),
  'Google Maps Terrain': L.tileLayer('//{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}', {
      subdomains: ['mt0','mt1','mt2','mt3'],
      maxZoom: 21,
      minZoom: 0,
      label: 'Google Maps Terrain'
  }),
  'No Map': L.tileLayer('/1px.gif', {
      maxZoom: 21,
      minZoom: 0,
      label: 'No Map'
  })
}

var autolayers = L.control.autolayers({
  overlays: {},
  selectedOverlays: [],
  baseLayers: basemaps
}).addTo(map);


$("#base").change(function() {
  var val = $(this).val();

  indices_of_base(val);
});


$("#vi").change(function() {
  var
    val = $(this).val()
    base = $("#base").val();
  ;

  if (val == "none") {

    indices_of_base(base);

  } else {

    $.ajax("/indices_statistics/" + val + ".json").done(function(statistics) {

      window.statistics = statistics;

      info.tiles = ["/vegetation_index?index=", val, "&min=", statistics["min"], "&max=", statistics["max"], "&tile=", base, "_tiles/{z}/{x}/{y}.png"];
      addTileLayer(info);

      renderIndexHistogram();

      findClippedMinMax();
      clip = true;

      reColorizeIndexHistogram();
      changeTileLayer();

    });

  }

});


indices_of_base("rgb");
