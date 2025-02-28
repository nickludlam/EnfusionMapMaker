# Enfusion Map Maker

This project implements a tool for the Enfusion World Editor which automates taking screenshots of the map at regular intervals. The resulting screenshots can then be processed into tiles suitable for integration with a panning/zooming tiled map system like LeafletJS.

The Workbench Plugin is found within the `Enfusion/` folder, and should be added as a local plug-in. The Python script to create the map tiles is inside the `Scripts/` directory, and requires the Python Image Library to work.

Lastly there is an example HTML page which shows how to implement coordinate conversions which allow the use in-game coordinates within the web page to mark elements of the map.
