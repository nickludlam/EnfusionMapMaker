# Enfusion Map Maker

This project implements a tool for the Enfusion World Editor which automates taking screenshots of the map at regular intervals. The resulting screenshots can then be processed into tiles suitable for integration with a panning/zooming tiled map system like LeafletJS.

The Workbench Plugin is found within the `Enfusion/` folder, and should be added as a local plug-in. The Python script to create the map tiles is inside the `Scripts/` directory, and requires the Python Image Library to work.

Lastly there is an example HTML page which shows how to implement coordinate conversions which allow the use in-game coordinates within the web page to mark elements of the map.

## Creating tiles

To create the tiles, first run the Enfusion World Editor and load the map you want to create tiles for. Then, open the Workbench Plugin and click the "Start" button. This will start taking screenshots of the map at regular intervals. The screenshots are saved to the `Screenshots/` directory.


### The process
Open Arma Reforger Tools
Select or add the Enfusion Map Maker plugin and start it
Open the Enfusion World Editor with your map of choice

Find the Castle/Tower/Rook chess icon along the toolbar at the top
Open the panel on the right side of the screen
Configure the plugin as required

IMPORTANT: Make sure your camera is set to an FOV of 15, and a far plane of 5000, this cannot be automated

View -> Toggle Visualisers
Also disable objects and flags which render as a large white cylinder. Not currently automated, but they are generally the `ConflictMilitaryBase` prefabs.

Positions with existing screenshots, or cropped tiles are automatically skipped

You can press escape to stop the process at any time, the camera will reset back to the initial position