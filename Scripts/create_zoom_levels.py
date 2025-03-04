import argparse
from enum import Enum
import os
import glob
from PIL import Image, ImageOps

class MapTile():
    xCoord: int
    zCoord: int
    lod: int
    basedir: str
    _image: Image.Image

    @staticmethod
    def get_glob():
        return "*/*/*/tile.jpg"

    def __init__(self, xCoord: int, zCoord: int, lod: int, basedir: str):
        self.xCoord = xCoord
        self.zCoord = zCoord
        self.lod = lod
        self.basedir = basedir

    def __str__(self) -> str:
        return f"MapTile {self.xCoord},{self.zCoord} @ LOD {self.lod} in {self.basedir}"
    
    @property
    def coordinates(self) -> tuple[int, int]:
        return (self.xCoord, self.zCoord)

    @property
    def zoom_directory(self):
        return os.path.join(self.basedir, str(self.lod))
    
    @property
    def coordinate_directory(self):
        return os.path.join(self.zoom_directory, str(self.xCoord), str(self.zCoord))
    
    @property
    def filename(self):
        return f"tile.jpg"

    @property
    def filepath(self):
        return os.path.join(self.coordinate_directory, self.filename)

    @property
    def image(self):
        return Image.open(self.filepath)
    
    def write_image(self, image: Image.Image, quality: int = 80):
        self.make_directory()
        image.save(self.filepath, quality=quality)

    def __hash__(self) -> int:
        return hash((self.lod, self.xCoord, self.zCoord))

    def make_directory(self):
        os.makedirs(self.coordinate_directory, exist_ok=True)

class MapTileContainer():
    max_lod: int = 5

    basedir: str
    map_tiles: dict[int, list[MapTile]]
    zoom_level: int # 5 is the most zoomed in, 0 is the least zoomed in
    _tile_size: int

    @classmethod
    def from_directory(cls, directory: str) -> "MapTileContainer":
        glob_path = os.path.join(directory, MapTile.get_glob())
        matching_files = glob.glob(glob_path)
        lod_tiles: dict[int, list[MapTile]] = {}
        for file in matching_files:
            # Files are in the structure {zoom_level}/{x}/{z}/tile.jpg
            path_elements = file.split("/")
            lod_level = int(path_elements[-4])
            x = int(path_elements[-3])
            z = int(path_elements[-2])
            tile = MapTile(x, z, lod_level, directory)
            print(f"Found tile {tile}")
            if lod_level not in lod_tiles:
                lod_tiles[lod_level] = []
            lod_tiles[lod_level].append(tile)
        if len(lod_tiles) == 0:
            raise Exception("No LOD tiles found")
        return cls(lod_tiles, directory)
    
    def __init__(self, tile_dict: dict[int, list[MapTile]], basedir: str, background_color: str = "#2B3D49"):
        self.map_tiles = tile_dict
        self.basedir = basedir
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
        # First find the first tile at LOD 0
        lod0_tiles = self.map_tiles[0]
        tile = lod0_tiles[0]
        size = tile.image.size
        return size[0]

    def min_worldspace_coordinates(self, lod: int):
        min_x = min([tile.xCoord for tile in self.map_tiles[lod]])
        min_z = min([tile.zCoord for tile in self.map_tiles[lod]])
        return (min_x, min_z)

    def max_worldspace_coordinates(self, lod: int):
        max_x = max([tile.xCoord for tile in self.map_tiles[lod]])
        max_z = max([tile.zCoord for tile in self.map_tiles[lod]])
        return (max_x, max_z)
    
    def make_remaining_lod_levels(self, overwrite_existing: bool = False):
        # Since we want to actually end on the min_zoom_level, we need to reverse the range
        for lod in range(1, self.max_lod+1):
            self.make_lod(lod, overwrite_existing)

    def get_tiles(self, lod: int, min_x: int, min_z: int, max_x: int, max_z: int) -> list[MapTile]:
        return [tile for tile in self.map_tiles[lod] if tile.xCoord >= min_x and tile.xCoord <= max_x and tile.zCoord >= min_z and tile.zCoord <= max_z]

    def make_lod(self, lod: int, overwrite_existing: bool = False):
        if lod == 0:
            raise Exception("Cannot create LOD 0 - This must come from the source images")
        
        print(f"Creating LOD {lod}")

        # First, we need to find the maximum x and z values, and they come from the deeper zoom level
        min_x, min_z = self.min_worldspace_coordinates(lod-1)
        max_x, max_z = self.max_worldspace_coordinates(lod-1) 

        # round to the nearest even number
        min_x = min_x - (min_x % 2)
        min_z = min_z - (min_z % 2)
        max_x = max_x + (max_x % 2)
        max_z = max_z + (max_z % 2)

        print(f"Source tiles from LOD {lod}: min_x={min_x}, max_x={max_x}, min_z={min_z}, max_z={max_z}")

        # Now we need to create a new list of tiles
        new_tiles = []

        for x in range(min_x, max_x+1, 2):
            for z in range(min_z, max_z+1, 2):
                # Find the 4 tiles that make up the 2x2 grid
                grid_tiles = self.get_tiles(lod-1, x, z, x+1, z+1)

                if len(grid_tiles) > 0:
                    print(f"Joining tiles at {lod}: {x},{z}")
                    # Now we need to merge the 4 tiles into a single tile
                    map_tile = self.merge_tiles(x, z, grid_tiles, lod, overwrite_existing)
                else:
                    print(f"Creating empty tile at {lod}: {x},{z}")
                    new_image = Image.new("RGB", (self._tile_size, self._tile_size), self.background_color)
                    map_tile = MapTile(x//2, z//2, lod, self.basedir)
                    if not os.path.exists(map_tile.filepath) or overwrite_existing:
                        map_tile.write_image(new_image)

                new_tiles.append(map_tile)

        # Now we need to update the list of tiles
        self.map_tiles[lod] = new_tiles

    def merge_tiles(self, source_x: int, source_z: int, tiles: list[MapTile], new_lod_level: int, overwrite_existing: bool = False) -> MapTile:
        # Create a new image that is 2x the size of the original tiles
        new_image = Image.new("RGB", (self._tile_size * 2, self._tile_size * 2), self.background_color)

        for x in range(0, 2):
            for z in range(0, 2):
                # get the tile from tiles
                target_coordinate = (source_x + x, source_z + z)
                tile = next((tile for tile in tiles if tile.coordinates == target_coordinate), None)
                if tile is not None:
                    flipped_z = 1 - z

                    # Open the image and paste it into the new image
                    new_image.paste(tile.image, (x * self._tile_size, flipped_z * self._tile_size))

        # now resize the image to the original size
        new_image = new_image.resize((self._tile_size, self._tile_size), Image.Resampling.LANCZOS)
        map_tile = MapTile(source_x//2, source_z//2, new_lod_level, self.basedir)
        if not os.path.exists(map_tile.filepath) or overwrite_existing:
            map_tile.write_image(new_image)

        return map_tile


if __name__ == "__main__":
    # Set up the args - We take an input directory to locate the screenshots and write tiles next to them
    parser = argparse.ArgumentParser(description="Center crop screenshots to a given resolution")
    parser.add_argument("input_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("-f", "--force-overwrite", action="store_true", help="Force overwrite existing files")
    args = parser.parse_args()

    print(f"Processing screenshots in {args.input_dir}")
    map_tile_container = MapTileContainer.from_directory(args.input_dir)
    map_tile_container.make_remaining_lod_levels(args.force_overwrite)
    print("Done!")