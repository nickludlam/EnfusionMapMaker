import argparse
from enum import Enum
import os
import glob
from PIL import Image, ImageOps

class MapTile():
    xCoord: int
    zCoord: int
    lodLevel: int
    _image: Image.Image

    @staticmethod
    def get_glob():
        return "*/*/*/tile.jpg"

    def __init__(self, xCoord: int, zCoord: int, lodLevel: int):
        self.xCoord = xCoord
        self.zCoord = zCoord
        self.lodLevel = lodLevel

    def __str__(self) -> str:
        return f"MapTile {self.xCoord}, {self.zCoord}, LOD {self.lodLevel}"
    
    @property
    def lod_directory(self):
        return f"{self.lodLevel}"
    
    @property
    def coordinate_directory(self):
        return f"{self.lod_directory}/{self.xCoord}/{self.zCoord}"
    
    @property
    def filename(self):
        return f"tile.jpg"

    @property
    def fullpath(self):
        return f"{self.coordinate_directory}/{self.filename}"

    @property
    def image(self):
        return Image.open(self.fullpath)

    def __hash__(self) -> int:
        return hash((self.xCoord, self.zCoord, self.lodLevel))


class MapTileContainer():
    max_zoom_level: int = 5
    min_zoom_level: int = 0

    map_tiles: dict[int, list[MapTile]]
    zoom_level: int # 5 is the most zoomed in, 0 is the least zoomed in
    _tile_size: int|None = None

    @classmethod
    def from_directory(cls, directory: str) -> "MapTileContainer":
        glob_path = os.path.join(directory, MapTile.get_glob())
        matching_files = glob.glob(glob_path)
        lod_tiles: dict[int, list[MapTile]] = {}
        for file in matching_files:
            # Files are in the structure LOD/{level}/{x}/{z}/tile.jpg
            path_elements = file.split("/")
            lod_level = int(path_elements[-4])
            x = int(path_elements[-3])
            z = int(path_elements[-2])
            tile = MapTile(x, z, lod_level)
            if lod_level not in lod_tiles:
                lod_tiles[lod_level] = []
            lod_tiles[lod_level].append(tile)
        if len(lod_tiles) == 0:
            raise Exception("No LOD tiles found")
        return cls(lod_tiles)
    
    def __init__(self, lod_tile_dict: dict[int, list[MapTile]], background_color: str = "#2B3D49"):
        self.map_tiles = lod_tile_dict
        self._tile_size = self.find_tile_size()
        self._background_hex = background_color
        print(self)

    def __str__(self):
        # Construct a summary of { zoom level: number of tiles }
        summary = {zoom_level: len(tiles) for zoom_level, tiles in self.map_tiles.items()}
        return f"MapTileContainer: {summary}"

    @property
    def background_color(self):
        # convert the hex color into a tuple
        hex_source = self._background_hex.lstrip("#")
        return tuple(int(hex_source[i:i+2], 16) for i in (0, 2, 4))

    def find_tile_size(self):
        # First find the first tile at LOD 5
        zoom_5_tiles = self.map_tiles[5]
        tile = zoom_5_tiles[0]
        size = tile.image.size
        return size[0]

    def min_worldspace_coordinates(self, lod_level: int):
        min_x = min([tile.xCoord for tile in self.map_tiles[lod_level]])
        min_z = min([tile.zCoord for tile in self.map_tiles[lod_level]])
        return (min_x, min_z)

    def max_worldspace_coordinates(self, lod_level: int):
        max_x = max([tile.xCoord for tile in self.map_tiles[lod_level]])
        max_z = max([tile.zCoord for tile in self.map_tiles[lod_level]])
        return (max_x, max_z)
        
    def make_zoom_level(self, zoom_level: int) -> int:
        print(f"Creating zoom {zoom_level}")
        # For each zoom level, we need to merge every 2x2 grid of tiles from the LOD below, into a single tile
        source_tiles = self.map_tiles[zoom_level+1]

        # First, we need to find the maximum x and z values, and they come from the deeper zoom level
        min_x, min_z = 0, 0
        max_x, max_z = self.max_worldspace_coordinates(zoom_level+1) 

        # round up to the nearest even number
        max_x = max_x + (2 - (max_x % 2))
        max_z = max_z + (2 - (max_z % 2))

        print(f"Zoom {zoom_level}: min_x={min_x}, max_x={max_x}, min_z={min_z}, max_z={max_z}")

        # Now we need to create a new list of tiles
        new_tiles = []

        for x in range(min_x, max_x, 2):
            for z in range(min_z, max_z, 2):
                # Find the 4 tiles that make up the 2x2 grid
                grid_tiles = [tile for tile in source_tiles if tile.xCoord >= x and tile.xCoord < x + 2 and tile.zCoord >= z and tile.zCoord < z + 2]
                if len(grid_tiles) > 0:
                    # Now we need to merge the 4 tiles into a single tile
                    new_lod_tile = self.merge_tiles(grid_tiles, zoom_level)
                    # Add the new tile to the list
                    new_tiles.append(new_lod_tile)
                else:
                    print(f"Creating empty tile at grid at {x}, {z}")
                    # create an empty tile
                    new_lod_tile = MapTile(x//2, z//2, zoom_level)
                    new_image = Image.new("RGB", (self._tile_size, self._tile_size), self.background_color)
                    os.makedirs(new_lod_tile.coordinate_directory, exist_ok=True)
                    output_filename = new_lod_tile.fullpath
                    if not os.path.exists(output_filename):
                        print(f"Saving new tile {new_lod_tile}")
                        new_image.save(output_filename, quality=80)

                    new_tiles.append(new_lod_tile)

        # Now we need to update the list of tiles
        self.map_tiles[zoom_level] = new_tiles

    def merge_tiles(self, tiles: list[MapTile], new_zoom_level: int) -> MapTile:
        # Create a new image that is 2x the size of the original tiles
        new_image = Image.new("RGB", (self._tile_size * 2, self._tile_size * 2), self.background_color)

        # sort the tiles by x and z worldspace coords
        sorted_tiles = sorted(tiles, key=lambda tile: (tile.xCoord, tile.zCoord))
        min_x = min([tile.xCoord for tile in sorted_tiles])
        min_z = min([tile.zCoord for tile in sorted_tiles])
        max_x = max([tile.xCoord for tile in sorted_tiles])
        max_z = max([tile.zCoord for tile in sorted_tiles])

        x_coord_lookup = [min_x, max_x]
        z_coord_lookup = [min_z, max_z]

        # Paste the 4 tiles into the new image
        for i, tile in enumerate(sorted_tiles):
            x = x_coord_lookup.index(tile.xCoord)
            z = z_coord_lookup.index(tile.zCoord)

            # invert z
            z = 1 - z
            
            # Calculate the coordinates in the new image
            paste_tile_coord_x = x * self._tile_size
            paste_tile_coord_z = z * self._tile_size

            # Paste the tile into the new image
            new_image.paste(tile.image, (paste_tile_coord_x, paste_tile_coord_z))

        # now resize the image to the original size
        new_image = new_image.resize((self._tile_size, self._tile_size), Image.Resampling.LANCZOS)

        # New tile should inherit the coordinates of the top left tile
        new_tile_x = max_x // 2
        new_tile_z = max_z // 2

        # print(f"Converting span {min_x},{min_z} to {max_x},{max_z} => {new_tile_x}, {new_tile_z} at LOD {new_lod_level}")

        new_lod_tile = MapTile(new_tile_x, new_tile_z, new_zoom_level)
        os.makedirs(new_lod_tile.coordinate_directory, exist_ok=True)
        output_filename = new_lod_tile.fullpath
        if not os.path.exists(output_filename):
            print(f"Saving new tile {new_lod_tile}")
            new_image.save(output_filename, quality=80)

        return new_lod_tile


if __name__ == "__main__":
    # Set up the args - We take an input directory to locate the screenshots and write tiles next to them
    parser = argparse.ArgumentParser(description="Center crop screenshots to a given resolution")
    parser.add_argument("input_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("output_dir", help="The directory containing the screenshots to crop")
    args = parser.parse_args()

    print(f"Processing screenshots in {args.input_dir}")
    screenshot_processor = MapTileContainer.from_directory(args.input_dir)
    screenshot_processor.make_tiles() # Will also delete the original screenshots if DELETE_ORIGINALS is True

    print("Creating initial tiles")
    screenshot_processor.make_initial_tiles(args.output_dir, "5")

