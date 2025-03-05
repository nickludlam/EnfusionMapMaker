const edge_to_center_offset = 50; // from the camera looking down into the center of LOD0 tiles
const MAX_ZOOM = 5; // If this is changed, it throws off the coordinate conversion - I don't understand why!

function makeMap(mapTilePathTemplate, initialZoom, bounds, mapBufferRatio, extraMapConfiguration) {
  var zoom = initialZoom;
  var center = bounds.getCenter();
  console.log(center);

  var urlCenterZoom = getCenterZoomFromURL();
  if (urlCenterZoom) {
    center = urlCenterZoom.center;
    zoom = urlCenterZoom.zoom;
  }

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
      zoom,
      center,
      ...extraMapConfiguration
  });
  
  // Invert the y axis so we can use the same tile naming scheme as the game
  L.TileLayer.InvertedY = L.TileLayer.extend({
    getTileUrl: function(tilecoords) {
      tilecoords.y = -(tilecoords.y + 1);
      return L.TileLayer.prototype.getTileUrl.call(this, tilecoords);
    }
  });

  // create a tile layer, and invert the z axis as we name by LODs
  tileLayer = new L.TileLayer.InvertedY(mapTilePathTemplate, {
    maxZoom: MAX_ZOOM,
    minZoom: 0,
    zoomReverse: true,
    bounds: bounds,
  }).addTo(map);

  var maxBounds = map.getBounds();
  var maxBoundsJSON = maxBounds.toBBoxString();
  console.log(`getMaxBounds: ${maxBoundsJSON}`);

  // Add a bit of padding so the map feels less annoying when zoomed out
  map.setMaxBounds(addPaddingToBounds(map.getBounds(), mapBufferRatio));

  // Constaly update the URL with the current map center
  // map.on('moveend', function() {
  //   // Get the current center of the map
  //   const center = map.getCenter();
    
  //   // Create the URL with updated lat/long parameters
  //   const newUrl = updateUrlParameters(
  //       window.location.href, {
  //         'center': `${center.lat.toFixed(6)}-${center.lng.toFixed(6)}`,
  //         'zoom': map.getZoom().toFixed(0)
  //       }
  //   );
    
  //   // Replace the current history entry without creating a new one
  //   window.history.replaceState(null, '', newUrl);
  // });

  return map;
}

// Add regular (unclustered) markers
function addMapMarkers(map, gameCoordinatesList) {
  gameCoordinatesList.forEach(coord => {
    L.marker(gameCoordsToLatLng([coord[0], coord[1]])).addTo(map);
  });
}

// Add clustered markers using the Leaflet.markercluster plugin
function addClusteredMapMarkers(map, resourceCoordinatesList) {
  var clusteredMarkers = L.markerClusterGroup({
    disableClusteringAtZoom : map.getMaxZoom()
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

// coordinate conversion - The +edge_to_center_offset accounts for our offset as the
// camera looks down into the center of LOD0 tiles, not the corner

function gameCoordsToLatLng(coordPair) {
  return L.latLng([coordPair[1] + edge_to_center_offset, coordPair[0] + edge_to_center_offset]);
}

function latLngToGameCoords(latlng) {
  return [latlng.lng - edge_to_center_offset, latlng.lat - edge_to_center_offset];
}

// Convert game coordinates to a Leaflet bounds object by swapping the x and y for LngLat
function gameCoordsToBounds(coordPairMin, coordPairMax, padding=0) {
  coordPairMin = [coordPairMin[0] - padding, coordPairMin[1] - padding];
  coordPairMax = [coordPairMax[0] + padding, coordPairMax[1] + padding];
  const min = gameCoordsToLatLng([coordPairMin[0], coordPairMin[1]]);
  const max = gameCoordsToLatLng([coordPairMax[0], coordPairMax[1]]);
  return L.latLngBounds(min, max);
}

function addPaddingToBounds(bounds, bufferRatio) {
  return bounds.pad(bufferRatio);
}

// Adds a grid debug which displays coordinates of each tile
function addGridDebug(map) {
  var maxZoom = map.getMaxZoom();
  L.GridLayer.GridDebug = L.GridLayer.extend({
    createTile: function (coords) {
      const tile = document.createElement('div');
      tile.style.outline = '1px solid #111';
      tile.style.fontWeight = 'bold';
      tile.style.fontSize = '14pt';
      tile.style.color = 'red';
      tile.innerHTML = [maxZoom - coords.z, coords.x, -(coords.y+1)].join('/');
      return tile;
    },
  });
    
  L.gridLayer.gridDebug = function (opts) {
      return new L.GridLayer.GridDebug(opts);
  };
  
  // Add debug grid overlay
  map.addLayer(L.gridLayer.gridDebug());
}

// URL functions

// During initialisation we can get the center and zoom from the URL
function getCenterZoomFromURL() {
  const urlParams = new URLSearchParams(window.location.search);
  const centerParam = urlParams.get('center');
  const zoomParam = urlParams.get('zoom');
  
  if (centerParam && zoomParam) {
      const [lat, lng] = centerParam.split('-').map(parseFloat);
      const zoom = parseInt(zoomParam);
      
      if (!isNaN(lat) && !isNaN(lng) && !isNaN(zoom)) {
        return {center: [lat, lng], zoom};
      }
  }
  
  return null;
}

// Utility function to update URL parameters
function updateUrlParameters(uri, keyValueDictionary) {
  // Remove the hash part of the URL if it exists
  const i = uri.indexOf('#');
  const hash = i === -1 ? '' : uri.substr(i);
  uri = i === -1 ? uri : uri.substr(0, i);

  // Create a URL object to help with parameter manipulation
  const url = new URL(uri, window.location.origin);
  
  // Set the new parameter values
  for (const [key, value] of Object.entries(keyValueDictionary)) {
      url.searchParams.set(key, value);
  }
  
  // Reconstruct the full URL with the hash
  return url.toString() + hash;
} 