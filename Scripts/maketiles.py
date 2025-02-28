import os
import glob
from PIL import Image, ImageOps

# This will scan the initial screenshots, and crop out a center square
# and save a new file with the TILE_FILENAME_SUFFIX suffix
# It will then remove the original screenshot to preserve disk space.
# The Workbench Plugin will be aware of this _tile suffix file as well
# as the original screenshot file, and not recapture the same area again.


# It will then convert these "Screenshot" instances into LODTiles, which
# are JPG files for space efficiency, and obey a specific directory structure
# used by leafletjs


# TODO:
# - Make this accept a directory as a parameter, so it's portable!
#   It currently works directly in C:\Users\<USER>\Documents\My Games\ArmaReforgerWorkbench\profile
# - This needs separation into two files. One for screenshot processing
#   and one for LOD tile generation
# - Rework get_tile_size() and get_tile_overlap() functions used when looking
#   for the right crop dimensions to achieve seamless tiling (done by eyeballing!)
# - Adjust exposure to make the overall luminance matches better between tiles
#   when they cross the land/sea border
# - Keep track of mtime to auto overwrite existing LOD tiles with updated pixels
# - Convert all the print statements into logging statements
# - Extract all config like globs/paths/coordinates to a config dict or class
# - Reinstate large map creation example

# What are the filenames we're matching on?
GLOB_MATCH = "*/eden_*.png"

# Add this suffix to the cropped output tile image
TILE_FILENAME_SUFFIX = "_tile"

# We want to use PNG for speed and quality
TILE_IMAGE_TYPE = "png"

OVERLAP_ENABLED = True  # If we enable this, when the large map is made, we will overlap the tiles by TILE_OVERLAP pixels
                        # If we disable this, we will bake the overlap into the tile size
                        # We use this when we dont want to endlessly create new tiles during the process of determining size
                        # for seamless tiling
TILE_CROP_SIZE = 550 # pixels
TILE_OVERLAP = -7 # pixels
SKIP_EXISTING_TILES = True

def get_tile_size():
    if OVERLAP_ENABLED:
        return TILE_CROP_SIZE
    else:
        return TILE_CROP_SIZE + TILE_OVERLAP

def get_tile_overlap():
    if OVERLAP_ENABLED:
        return TILE_OVERLAP
    else:
        return 0.0


class LODTile():
    xCoord: int
    zCoord: int
    lodLevel: int
    _image: Image

    @staticmethod
    def get_glob():
        return "LODS/*/*/*/tile.jpg"

    def __init__(self, xCoord: int, zCoord: int, lodLevel: int):
        self.xCoord = xCoord
        self.zCoord = zCoord
        self.lodLevel = lodLevel

    def __str__(self) -> str:
        return f"LODTile {self.xCoord}, {self.zCoord}, LOD {self.lodLevel}"
    
    @property
    def lod_directory(self):
        return f"LODS/{self.lodLevel}"
    
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


class LODTileContainer():
    lod_tiles: dict[int, list[LODTile]]
    lod_level: int
    _tile_size: int|None = None
    _fallback_tile_image = None

    _background_hex = "#2B3D49" # This matches the background color of the sea

    @classmethod
    def load(cls):
        matching_files = glob.glob(LODTile.get_glob())
        lod_tiles: dict[int, list[LODTile]] = {}
        for file in matching_files:
            # Files are in the strucrure LOD/{level}/{x}/{z}/tile.jpg
            path_elements = file.split("/")
            lod_level = int(path_elements[-4])
            x = int(path_elements[-3])
            z = int(path_elements[-2])
            tile = LODTile(x, z, lod_level)
            if lod_level not in lod_tiles:
                lod_tiles[lod_level] = []
            lod_tiles[lod_level].append(tile)
        if len(lod_tiles) == 0:
            raise Exception("No LOD tiles found")
        return cls(lod_tiles)
    
    def __init__(self, lod_tile_dict: dict[int, list[LODTile]]):
        self.lod_tiles = lod_tile_dict
        self._tile_size = self.find_tile_size()
        print(self)

    def __str__(self):
        # Construct a summary of { LOD level: number of tiles }
        summary = {lod_level: len(tiles) for lod_level, tiles in self.lod_tiles.items()}
        return f"LODTileContainer: {summary}"

    @property
    def background_color(self):
        # convert the hex color into a tuple
        hex_source = self._background_hex.lstrip("#")
        return tuple(int(hex_source[i:i+2], 16) for i in (0, 2, 4))

    def find_tile_size(self):
        # First find the first time at LOD 0
        lod_0_tiles = self.lod_tiles[0]
        tile = lod_0_tiles[0]
        size = tile.image.size
        return size[0]

    def min_worldspace_coordinates(self, lod_level: int):
        min_x = min([tile.xCoord for tile in self.lod_tiles[lod_level]])
        min_z = min([tile.zCoord for tile in self.lod_tiles[lod_level]])
        return (min_x, min_z)

    def max_worldspace_coordinates(self, lod_level: int):
        max_x = max([tile.xCoord for tile in self.lod_tiles[lod_level]])
        max_z = max([tile.zCoord for tile in self.lod_tiles[lod_level]])
        return (max_x, max_z)
    
    @property
    def fallback_tile_image(self):
        # take the first tile from LOD 0
        if self._fallback_tile_image is None:
            self._fallback_tile_image = self.lod_tiles[0][0].image
        return self._fallback_tile_image
    
    def make_LOD(self, lod_level: int) -> int:
        print(f"Creating LOD {lod_level}")
        # For each LOD level, we need to merge every 2x2 grid of tiles from the LOD below, into a single tile
        source_tiles = self.lod_tiles[lod_level-1]

        # First, we need to find the maximum x and z values
        min_x, min_z = 0, 0
        max_x, max_z = self.max_worldspace_coordinates(lod_level-1) # always get the max from LOD 0 as its the source when we want to divide by a power of 2

        # round up to the nearest even number
        max_x = max_x + (2 - (max_x % 2))
        max_z = max_z + (2 - (max_z % 2))

        print(f"LOD {lod_level}: min_x={min_x}, max_x={max_x}, min_z={min_z}, max_z={max_z}")

        # Now we need to create a new list of tiles
        new_tiles = []

        for x in range(min_x, max_x, 2):
            for z in range(min_z, max_z, 2):
                # print(f"Processing 2x2 grid at {x}, {z}")

                # the new tile would be at x/2, z/2, so check if we already have that tile
                # if lod_level in self.lod_tiles:
                #     existing_tile = [tile for tile in self.lod_tiles[lod_level] if tile.xCoord == x//2 and tile.zCoord == z//2]
                #     if len(existing_tile) > 0:
                #         print(f"Tile at {x//2}, {z//2} already exists, skipping")
                #         continue

                # Find the 4 tiles that make up the 2x2 grid
                grid_tiles = [tile for tile in source_tiles if tile.xCoord >= x and tile.xCoord < x + 2 and tile.zCoord >= z and tile.zCoord < z + 2]
                if len(grid_tiles) > 0:
                    # min_grid_x = min([tile.xCoord for tile in grid_tiles])
                    # min_grid_z = min([tile.zCoord for tile in grid_tiles])
                    # max_grid_x = max([tile.xCoord for tile in grid_tiles])
                    # max_grid_z = max([tile.zCoord for tile in grid_tiles])

                    # print(f"Processing 2x2 grid at {min_grid_x}, {min_grid_z} to {max_grid_x}, {max_grid_z}  (originally from x={x}, z={z})")
                    # for tile in grid_tiles:
                    #     print(f" source grid tile {tile.xCoord}, {tile.zCoord}, filename {tile.fullpath}")

                    # Now we need to merge the 4 tiles into a single tile
                    new_lod_tile = self.merge_tiles(grid_tiles, lod_level)
                    # Add the new tile to the list
                    new_tiles.append(new_lod_tile)
                else:
                    print(f"Creating empty tile at grid at {x}, {z}")
                    # create an empty tile
                    new_lod_tile = LODTile(x//2, z//2, lod_level)
                    new_image = Image.new("RGB", (self._tile_size, self._tile_size), self.background_color)
                    os.makedirs(new_lod_tile.coordinate_directory, exist_ok=True)
                    output_filename = new_lod_tile.fullpath
                    if not os.path.exists(output_filename):
                        print(f"Saving new tile {new_lod_tile}")
                        new_image.save(output_filename, quality=80)

                    new_tiles.append(new_lod_tile)

        # Now we need to update the list of tiles
        self.lod_tiles[lod_level] = new_tiles

    def merge_tiles(self, tiles: list[LODTile], new_lod_level: int) -> LODTile:
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

        new_lod_tile = LODTile(new_tile_x, new_tile_z, new_lod_level)
        os.makedirs(new_lod_tile.coordinate_directory, exist_ok=True)
        output_filename = new_lod_tile.fullpath
        if not os.path.exists(output_filename):
            print(f"Saving new tile {new_lod_tile}")
            new_image.save(output_filename, quality=80)

        return new_lod_tile


class Screenshot():
    xCoordWS: int
    zCoordWS: int
    # This has two images, the full resolution raw screenshot, and the cropped tile
    _screenshot_filepath: str|None
    _tile_filepath: str
    _screenshot_image: Image
    _tile_image: Image

    def __init__(self, xCoordWS: int, zCoordWS: int, screenshot_filepath: str|None = None, tile_filepath: str|None = None):
        self.xCoordWS = xCoordWS
        self.zCoordWS = zCoordWS
        self._screenshot_filepath = screenshot_filepath
        self._tile_filepath = tile_filepath
        self._screenshot_image = None
        self._tile_image = None

    def __str__(self):
        return f"Screenshot {self.xCoordWS}, {self.zCoordWS}"
    
    @property
    def screenshot_image(self):
        if self._screenshot_image is None:
            self._screenshot_image = Image.open(self.screenshot_filepath)
        return self._screenshot_image

    @property
    def tile_image(self):
        if self._tile_image is None:
            self._tile_image = Image.open(self.tile_filepath)
        return self._tile_image

    @property
    def screenshot_filepath(self):
        return self._screenshot_filepath

    @property
    def tile_filepath(self):
        if self._tile_filepath is not None:
            return self._tile_filepath
        return self.generate_tile_path()

    def unload(self):
        self._screenshot_image = None
        self._tile_image = None

    def generate_tile_path(self):
        # take filepath, strip of .png, and add output_file_suffix + output_tile_type
        return self.screenshot_filepath.replace(".png", f"{TILE_FILENAME_SUFFIX}.{TILE_IMAGE_TYPE}")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Screenshot):
            return False
        return self.xCoordWS == other.xCoordWS and self.zCoordWS == other.zCoordWS

    def __hash__(self) -> int:
        return hash((self.xCoordWS, self.zCoordWS))
    
    def create_tile(self):
        # crop the center of the image to crop_size x crop_size
        width, height = self.screenshot_image.size
        left = (width - get_tile_size()) / 2
        top = (height - get_tile_size()) / 2
        right = (width + get_tile_size()) / 2
        bottom = (height + get_tile_size()) / 2
        cropped_image = self.screenshot_image.crop((left, top, right, bottom))
        # set the jpeg quality to 95
        cropped_image.save(self.tile_filepath, quality=95)

    def tile_exists(self):
        return os.path.exists(self.tile_filepath) and SKIP_EXISTING_TILES
    
    def get_unit_coordinates(self, min_x: int, min_z: int, filename_coordinate_step: int):
        return (int((self.xCoordWS - min_x) / filename_coordinate_step), int((self.zCoordWS - min_z) / filename_coordinate_step))

class ScreenshotProcessor():
    screenshots: list[Screenshot]
    hashed_screenshots: set[Screenshot]

    def __init__(self, screenshots: list[Screenshot]|None = None):
        if screenshots is None:
            screenshots = []
        self.screenshots = screenshots
        self.hashed_screenshots = set(screenshots)
        if len(screenshots) != len(self.hashed_screenshots):
            raise RuntimeError("WARNING: Duplicate screenshots found")

        if len(screenshots) > 0:
            self.sort()
    
    def __str__(self):
        return f"ScreenshotProcessor {len(self.screenshots)} screenshots"
    
    def __repr__(self):
        return str(self)

    def add_screenshot(self, screenshot: Screenshot):
        if screenshot in self.hashed_screenshots:
            return
        self.screenshots.append(screenshot)
        self.hashed_screenshots.add(screenshot)
        self.sort()

    def sort(self):
        self.screenshots = sorted(self.screenshots, key=lambda screenshot: (screenshot.xCoordWS, screenshot.zCoordWS))
    
    def min_x(self):
        # scan the list of screenshots and find the minimum x coordinate
        return min([screenshot.xCoordWS for screenshot in self.screenshots
                    if screenshot.xCoordWS is not None])
    
    def max_x(self):
        return max([screenshot.xCoordWS for screenshot in self.screenshots
                    if screenshot.xCoordWS is not None])
    
    def min_z(self):
        return min([screenshot.zCoordWS for screenshot in self.screenshots
                    if screenshot.zCoordWS is not None])
    
    def max_z(self):
        return max([screenshot.zCoordWS for screenshot in self.screenshots
                    if screenshot.zCoordWS is not None])

    @property
    def tile_step_size(self):
        # take the first two tiles, and calculate the difference in x and z
        tile_0 = self.screenshots[0]
        tile_1 = self.screenshots[1]
        x_diff = abs(tile_0.xCoordWS - tile_1.xCoordWS)
        z_diff = abs(tile_0.zCoordWS - tile_1.zCoordWS)
        # return which ever is larger
        return max(x_diff, z_diff)

    def count(self):
        return len(self.screenshots)

    def make_tiles(self):
        for screenshot in self.screenshots:
            if not screenshot.tile_exists():
                print(f"Creating screenshot tile at {screenshot.xCoordWS}, {screenshot.zCoordWS}")
                screenshot.create_tile()
            else:
                # print(f"Screenshot tile at {screenshot.xCoordWS}, {screenshot.zCoordWS} already exists")
                pass

    def remove_original_screenshots(self):
        for screenshot in self.screenshots:
            if screenshot.screenshot_filepath is not None and screenshot.tile_exists():
                print(f"Removing original screenshot {screenshot.screenshot_filepath}")
                os.remove(screenshot.screenshot_filepath)

    def composite_screenshot_tiles(self, tiles: list[Screenshot], output_filename: str):
        tile_min_x = min([tile.xCoordWS for tile in tiles])
        tile_min_z = min([tile.zCoordWS for tile in tiles])
        tile_max_x = max([tile.xCoordWS for tile in tiles])
        tile_max_z = max([tile.zCoordWS for tile in tiles])

        # worldspace range
        x_ws_range = tile_max_x - tile_min_x
        z_ws_range = tile_max_z - tile_min_z

        # unit range
        x_unit_range = int(x_ws_range / self.tile_step_size) + 1
        z_unit_range = int(z_ws_range / self.tile_step_size) + 1

        # create a new image with the size of the map
        map_image = Image.new("RGB", (x_unit_range * get_tile_size(), z_unit_range * get_tile_size()), (0, 0, 0, 0))
        sorted_tiles = sorted(tiles, key=lambda tile: (tile.xCoordWS, tile.zCoordWS))

        for tile in sorted_tiles:
            x, z = tile.get_unit_coordinates(tile_min_x, tile_min_z, self.tile_step_size)

            # flip the z coordinate so that the origin is at the bottom left
            z = z_unit_range - z - 1

            paste_tile_coord_x = int(x * get_tile_size())
            paste_tile_coord_z = int(z * get_tile_size())

            # OPTIONAL: now account for how much we want to overlap the tiles
            if get_tile_overlap() != 0.0:
                displacement_x = int(get_tile_overlap() * x)
                displacement_z = int(get_tile_overlap() * z)
                print(f"Adjusting tile coordinates by overlap of {displacement_x},{displacement_z} px")
                paste_tile_coord_x += displacement_x
                paste_tile_coord_z += displacement_z

            print(f"Placing {tile.tile_filepath} at {paste_tile_coord_x}, {paste_tile_coord_z} (unit {x}, {z})")
            map_image.paste(tile.tile_image, (paste_tile_coord_x, paste_tile_coord_z))
            tile.unload()
        
        # save the map image
        map_image.save(output_filename, quality=96)
        print(f"Saved tiles to {output_filename}")


    def make_large_map(self, filepath: str = "map.jpeg", x_coods_start: int = 0, z_coord_start: int = 0, max_x_tile_count: int = 0, max_z_tile_count: int = 0):
        included_tiles = []
        min_x_coord = -1
        min_z_coord = -1
        max_x_coord = -1
        max_z_coord = -1
        for screenshot in self.screenshots:
            if x_coods_start > 0 and screenshot.xCoordWS < x_coods_start:
                continue
            if z_coord_start > 0 and screenshot.zCoordWS < z_coord_start:
                continue
            
            # update our mins and maxes
            if min_x_coord == -1 or screenshot.xCoordWS < min_x_coord:
                min_x_coord = screenshot.xCoordWS
            if min_z_coord == -1 or screenshot.zCoordWS < min_z_coord:
                min_z_coord = screenshot.zCoordWS
            if max_x_coord == -1 or screenshot.xCoordWS > max_x_coord:
                max_x_coord = screenshot.xCoordWS
            if max_z_coord == -1 or screenshot.zCoordWS > max_z_coord:
                max_z_coord = screenshot.zCoordWS
            
            x_tile_count = int((max_x_coord - min_x_coord) / self.tile_step_size)
            z_tile_count = int((max_z_coord - min_z_coord) / self.tile_step_size)

            print(f"min_x_coord: {min_x_coord}, min_z_coord: {min_z_coord}, max_x_coord: {max_x_coord}, max_z_coord: {max_z_coord}")
            print(f"Current axis tile counts: {x_tile_count}, {z_tile_count}")

            if (max_x_tile_count == 0 or x_tile_count <= max_x_tile_count) or (max_z_tile_count == 0 or z_tile_count <= max_z_tile_count):
                included_tiles.append(screenshot)

        print(f"Creating large map from {len(included_tiles)} tiles")
        self.composite_screenshot_tiles(included_tiles, filepath)

    def make_lod_0(self) -> list[LODTile]:
        # At LOD 0, we use the original tiles, and output to a new folder
        # At LOD 1+, we merge every 2x2 grid of tiles into a single tile from the LOD below, and resize to get_tile_size()
        for screenshot in self.screenshots:
            normalized_x = int(screenshot.xCoordWS / self.tile_step_size)
            normalized_z = int(screenshot.zCoordWS / self.tile_step_size)

            lod_tile = LODTile(normalized_x, normalized_z, 0)
            # copy the tile to the new folder
            if not os.path.exists(lod_tile.fullpath):
                lod_directory_path = os.path.dirname(lod_tile.fullpath)
                os.makedirs(lod_directory_path, exist_ok=True)
                print(f"Converting {screenshot.tile_filepath} to {lod_tile.fullpath}")
                image = Image.open(screenshot.tile_filepath)

                # crop the image to get_tile_size() + get_tile_overlap()
                target_size = get_tile_size() + get_tile_overlap()
                image_size = image.size
                if image_size[0] != target_size or image_size[1] != target_size:
                    left = (image_size[0] - target_size) / 2
                    top = (image_size[1] - target_size) / 2
                    right = (image_size[0] + target_size) / 2
                    bottom = (image_size[1] + target_size) / 2
                    image = image.crop((left, top, right, bottom))

                image.save(lod_tile.fullpath, quality=95)


print("Scanning for existing files")
matching_files = glob.glob(GLOB_MATCH)
screenshot_files = [file for file in matching_files if TILE_FILENAME_SUFFIX not in file]
tile_files = [file for file in matching_files if TILE_FILENAME_SUFFIX in file]

screenshot_processor = ScreenshotProcessor()
if (len(screenshot_files) > 0):
    for file in screenshot_files:
        # Files have the suffix _{x}_{z}.png, so use -ve offsets for splitting
        x = int(file.split("_")[-2])
        z = int(file.split("_")[-1].split(".")[0])
        screenshot_processor.add_screenshot(Screenshot(x, z, screenshot_filepath=file))

# # Now we need to create the tiles from cached tile files, as we might have deleted the screenshots
if (len(tile_files) > 0):
    for file in tile_files:
        # Files have the suffix _{x}_{z}_tile.png, so use -ve offsets for splitting
        x = int(file.split("_")[-3])
        z = int(file.split("_")[-2])
        screenshot_processor.add_screenshot(Screenshot(x, z, tile_filepath=file))


print("Making tiles")
screenshot_processor.make_tiles()
if len(screenshot_files) > 0:
    print("Removing original screenshots")
    screenshot_processor.remove_original_screenshots()

print("Creating LOD 0 tiles")
created_lod0 = screenshot_processor.make_lod_0()

# tile_container.make_large_map("large_map.jpg", x_coods_start=1000, z_coord_start=1000, max_x_tile_count=30, max_z_tile_count=30)


# LOD generation
print("Loading the existing LODs")
lod_tile_container = LODTileContainer.load()
print(lod_tile_container)
lod_tile_container.make_LOD(1)
lod_tile_container.make_LOD(2)
lod_tile_container.make_LOD(3)
lod_tile_container.make_LOD(4)
lod_tile_container.make_LOD(5)
