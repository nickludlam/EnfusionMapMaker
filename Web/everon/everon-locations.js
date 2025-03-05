// This exports three arrays:
// labeledTownLocations: Locations of towns and other named locations
// labeledResourceLocations: Locations of resource depots
// labeledMilitaryBaseLocations: Locations of military bases


// Locations
var locSaintPhillipe = [4500.872, 10776.053];
var locMontignac = [4775.641, 7086.945];
var locEntreDeux = [5760.571, 7061.821];
var locMeaux = [4517.52, 9467.668];
var locSaintPierre = [9689.432, 1558.166];
var locMorton = [5137.254, 4009.941];
var locFigari = [5256.366, 5341.263];
var locLamentin = [1281.055, 5946.839];
var locChotain = [7087.74, 6011.904];
var locLevie = [7456.592, 4737.094];
var locDurras = [8826.12, 2746.123];
var locCamurac = [6594.162, 3116.684];
var locProvins = [5488.17, 6083.411];
var locAndresBeacon = [6843.832, 8191.218];
var locKermovan = [6359.376, 9668.684];
var locGravette = [4128.282, 7792.364];
var locQuarry = [8786.965, 3913.078];
var locRegina = [7188.38, 2312.382];
var locVilleneuve = [2847.008, 6339.848];
var locTyrone = [4948.837, 9075.68];

// Features
var locAirport = [4893.46, 11800.709];
var locPowerplant = [5826.642, 9786.735];

// Resource Depots
var resourceDepotFarm = [5009.537, 9964.422];
var resourceDepotMeauxHarbor = [4304.272, 9517.466];
var resourceDepotGorey = [4844.906, 8088.995];
var resourceDepotPinewoodLake = [4871.928, 5675.194];
var resourceDepotLevie = [6918, 4450];
var resourceDepotDurrasHill = [9044.778, 2741.715];
var resourceDepotSawmill = [3114.358, 5221.5];
var resourceDepotRegina = [7089.407, 2072.731];
var resourceDepotChotainIndustrial = [6455.525, 6487.396];

// Unmarked cap points
var capPointOldWood = [3293.234, 4488.741];
var capPointMortonValley = [4517.589, 4967.065];
var capPointLaruns = [7429.288, 5318.843];
var capPointQuarry = [8797.021, 3905.115];

// Military Bases
var militaryBaseChotain = [7444.065, 6697.595];
var militaryBaseLevie = [7476.739, 4301.884];
var militaryHospital = [3904.698, 8450.042];
var coastalBaseLamentin = [1062.89, 6047.846];
var coastalBaseMorton = [4956.796, 3875.627];

// Now derive the locations from the above
var labeledTownLocations = [
  { name: "Airport", gameCoords: locAirport },
  { name: "St Phillipe", gameCoords: locSaintPhillipe },
  { name: "Power Plant", gameCoords: locPowerplant },
  { name: "St Pierre", gameCoords: locSaintPierre },
  { name: "Meaux", gameCoords: locMeaux },
  { name: "Tyrone", gameCoords: locTyrone },
  { name: "Andres Beacon", gameCoords: locAndresBeacon },
  { name: "Gravette", gameCoords: locGravette },
  { name: "Villeneuve", gameCoords: locVilleneuve },
  { name: "Morton", gameCoords: locMorton },
  { name: "Lamentin", gameCoords: locLamentin },
  { name: "Chotain", gameCoords: locChotain },
  { name: "Montignac", gameCoords: locMontignac },
  { name: "Provins", gameCoords: locProvins },
  { name: "Figari", gameCoords: locFigari },
  { name: "Camurac", gameCoords: locCamurac },
  { name: "Quarry", gameCoords: locQuarry },
  { name: "Regina", gameCoords: locRegina },
  { name: "Durras", gameCoords: locDurras },
];

var labeledResourceLocations = [
  { name: "Farm", gameCoords: resourceDepotFarm },
  { name: "Gorey", gameCoords: resourceDepotGorey },
  { name: "Sawmill", gameCoords: resourceDepotSawmill },
  { name: "Chotain Industrial", gameCoords: resourceDepotChotainIndustrial },
  { name: "Hillside", gameCoords: resourceDepotLevie },
];

var labeledMilitaryBaseLocations = [
  { name: "Coastal Base Chotain", gameCoords: militaryBaseChotain },
  { name: "Military Base Levie", gameCoords: militaryBaseLevie },
  { name: "MilitaryHospital", gameCoords: militaryHospital },
  { name: "Coastal Base Lamentin", gameCoords: coastalBaseLamentin },
  { name: "Coastal Base Morton", gameCoords: coastalBaseMorton },
];
