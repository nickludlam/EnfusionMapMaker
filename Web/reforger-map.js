
function makeMap(bounds, extraConfiguration) {
  // This is specifically for the Reforger/Enfusion maps, which uses a custom CRS
  // to achieve a 1:1 mapping between game coordinates and lat/lng (or in this case lng/lat)
  L.CRS.CustomSimple = L.Util.extend({}, L.CRS, {
    projection: L.Projection.LonLat,
    transformation: new L.Transformation(1/12.501, 0, -1/12.501, 0), // I had to eyeball this scale factor!

    scale(zoom) {
        return Math.pow(2, zoom);
    },

    zoom(scale) {
        return Math.log(scale) / Math.LN2;
    },

    distance(latlng1, latlng2) {
        const dx = latlng2.lng - latlng1.lng,
            dy = latlng2.lat - latlng1.lat;

        return Math.sqrt(dx * dx + dy * dy);
    },

    infinite: true
  });

  var map = L.map('map', {
      crs: L.CRS.CustomSimple,
      zoom: 0,
      ...extraConfiguration
  });

  // Invert the y axis so we can use the same tile naming scheme as the game
  L.TileLayer.InvertedY = L.TileLayer.extend({
      getTileUrl: function(tilecoords) {
          tilecoords.y = -(tilecoords.y + 1);
          return L.TileLayer.prototype.getTileUrl.call(this, tilecoords);
      }
  });

  // create a tile layer, and invert the z axis as we name by LODs
  tileLayer = new L.TileLayer.InvertedY('LODS/{z}/{x}/{y}/tile.jpg', {
      maxZoom: 5,
      minZoom: 0,
      bounds: bounds, // i.e. [[0,0], [12800,12800]],
      maxNativeZoom: 5,
  }).addTo(map);

  return map;
}

// Add regular (unclustered) markers
function addMapMarkers(map, resourceCoordinatesList) {
  resourceCoordinatesList.forEach(coord => {
      L.marker(gameCoordsToLatLng([coord[0], coord[1]])).addTo(map);
  });
}

// Add clustered markers using the Leaflet.markercluster plugin
function addClusteredMapMarkers(map, resourceCoordinatesList) {
  var clusteredMarkers = L.markerClusterGroup({
    disableClusteringAtZoom : 5
  });

  resourceCoordinatesList.forEach(coord => {
      var coordLatLng = gameCoordsToLatLng([coord[0], coord[1]]);
      //var coordMarker = L.marker(coordLatLng).addTo(map); // add directly to map
      var coordMarker = L.marker(coordLatLng);
      clusteredMarkers.addLayer(coordMarker);
  });

  map.addLayer(clusteredMarkers);
}

// Add custom labels to the map
function addMapLabel(map, gameCoordinates, label, cssClass) {
  var latlng = gameCoordsToLatLng(gameCoordinates);
  L.tooltip(latlng, {
    content: label,
    permanent: true,
    direction: "center",
    className: cssClass
  }).addTo(map);
}

// Hide labels when zoomed in past a certain level by altering the css class
function defineLabelVisibility(map, minZoomLevel, maxZoomLevel, targetSelector, hiddenClassname) {
  map.on('zoomend', function(e){
    var zoomLevel = map.getZoom();
    if (zoomLevel < minZoomLevel || zoomLevel > maxZoomLevel ){
      [].forEach.call(document.querySelectorAll(targetSelector), function (el) {
        // add hidden-tooltip class to hide
        el.classList.add(hiddenClassname);
      });
    } else {
      [].forEach.call(document.querySelectorAll(targetSelector), function (el) {
        el.classList.remove(hiddenClassname);
      });
    }
  });
}

// coordinate conversion - The +50 accounts for our offset as the
// camera looks down into the center of LOD0 tiles, not the corner

function gameCoordsToLatLng(coordPair) {
  return L.latLng([coordPair[1] + 50, coordPair[0] + 50]);
}

function latLngToGameCoords(latlng) {
  return [latlng.lng - 50, latlng.lat - 50];
}

// Adds a grid debug which displays coordinates of each tile
function addGridDebug(map) {
  L.GridLayer.GridDebug = L.GridLayer.extend({
      createTile: function (coords) {
        const tile = document.createElement('div');
        tile.style.outline = '1px solid #111';
        tile.style.fontWeight = 'bold';
        tile.style.fontSize = '14pt';
        tile.style.color = 'red';
        tile.innerHTML = [coords.z, coords.x, -(coords.y+1)].join('/');
        return tile;
      },
    });
    
  L.gridLayer.gridDebug = function (opts) {
      return new L.GridLayer.GridDebug(opts);
  };
  
  // Add debug grid overlay
  map.addLayer(L.gridLayer.gridDebug());
}
