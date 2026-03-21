window.onload = init

function init(){


const map = new ol.Map({
  view:new ol.View({
  center:[35.15107279588091, 36.86282829475191, -11.17],
  zoom:7,
  maxZoom:10,
  minZoom:4
  }),
  layers:[
    new ol.layer.Tile({
        source: new ol.source.OSM()
    })
  ],
  target:"map"

 
  
})
map.on('click',function(e){
    console.log(e.coordinate);
  })
}