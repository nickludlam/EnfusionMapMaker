import argparse
from enum import Enum
import os
import glob
from PIL import Image, ImageOps

# Configuration - Make sure this matches the Enfusion Workbench tool settings
TILE_CROP_SIZE = 550 # pixels - Set this initially to be too large for perfect tiling
TILE_OVERLAP = -7  # pixels - Then adjust this value to get the perfect tiling testing in -make_map mode

# Optional configuration
SKIP_EXISTING_TILES = True # Skip creating tiles that already exist
DELETE_ORIGINALS = True # Delete the original screenshots after cropping the tiles to save disk space

INTERMEDIATE_TILE_FILENAME_SUFFIX = "tile" # only change this if you have also changed the Enfusion Workbench settings
FINAL_TILE_FILENAME = "tile"
FINAL_TILE_IMAGE_TYPE = "jpg"


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
    def tile_image(self) -> Image.Image:
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
        return self.screenshot_filepath.replace(".png", f"_{INTERMEDIATE_TILE_FILENAME_SUFFIX}.png")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Screenshot):
            return False
        return self.xCoordWS == other.xCoordWS and self.zCoordWS == other.zCoordWS

    def __hash__(self) -> int:
        return hash((self.xCoordWS, self.zCoordWS))
    
    def create_tile(self):
        # crop the center of the image to crop_size x crop_size
        width, height = self.screenshot_image.size
        left = (width - TILE_CROP_SIZE) / 2
        top = (height - TILE_CROP_SIZE) / 2
        right = (width + TILE_CROP_SIZE) / 2
        bottom = (height + TILE_CROP_SIZE) / 2
        cropped_image = self.screenshot_image.crop((left, top, right, bottom))
        # set the jpeg quality to 95
        cropped_image.save(self.tile_filepath, quality=95)

    def tile_exists(self):
        return os.path.exists(self.tile_filepath)
    
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
    
    @classmethod
    def from_directory(cls, directory: str):
        screenshot_processor = ScreenshotProcessor()
        
        glob_match = os.path.join(directory, f"*/*.png")
        matching_filepaths = glob.glob(glob_match)
        if len(matching_filepaths) == 0:
            raise print(f"ERROR: No screenshots found in {directory}")

        print(f"Importing {len(matching_filepaths)} files")
        for filepath in matching_filepaths:
            # incoming screenshot filenames are in the format
            # {prefix}_{x}_{z}.png - The original full resolution screenshot
            # {prefix}_{x}_{z}_tile.png - The cropped tile
            filename = os.path.basename(filepath)
            filename_no_ext = os.path.splitext(filename)[0]
            filename_elements = filename_no_ext.split("_")
            if filename_elements[-1] == INTERMEDIATE_TILE_FILENAME_SUFFIX:
                x = int(filename_elements[-3])
                z = int(filename_elements[-2])
                screenshot_processor.add_screenshot(Screenshot(x, z, tile_filepath=filepath))
            else:
                x = int(filename_elements[-2])
                z = int(filename_elements[-1])
                screenshot_processor.add_screenshot(Screenshot(x, z, screenshot_filepath=filepath))

        return screenshot_processor
        
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
            if screenshot.tile_exists() and SKIP_EXISTING_TILES:
                print(f"Skipping {screenshot.tile_filepath}")
            else:
                print(f"Creating cropped screenshot tile for coordinate {screenshot.xCoordWS}, {screenshot.zCoordWS}")
                screenshot.create_tile()

            if DELETE_ORIGINALS and screenshot.screenshot_filepath is not None:
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

        output_image_size_x = x_unit_range * TILE_CROP_SIZE
        output_image_size_z = z_unit_range * TILE_CROP_SIZE

        # we need to account for the overlap by adding the <dim>_unit_range * overlap from the output size
        # don't forget that get_tile_overlap() returns a negative number
        if TILE_OVERLAP != 0:
            output_image_size_x += (x_unit_range - 1) * TILE_OVERLAP
            output_image_size_z += (z_unit_range - 1) * TILE_OVERLAP

        # create a new image with the size of the map
        map_image = Image.new("RGB", (output_image_size_x, output_image_size_z), (0, 0, 0, 0))
        sorted_tiles = sorted(tiles, key=lambda tile: (tile.xCoordWS, tile.zCoordWS))

        for tile in sorted_tiles:
            x, z = tile.get_unit_coordinates(tile_min_x, tile_min_z, self.tile_step_size)

            # flip the z coordinate so that the origin is at the bottom left
            z = z_unit_range - z - 1

            paste_tile_coord_x = int(x * TILE_CROP_SIZE)
            paste_tile_coord_z = int(z * TILE_CROP_SIZE)

            # OPTIONAL: now account for how much we want to overlap the tiles
            if TILE_OVERLAP != 0:
                displacement_x = int(TILE_OVERLAP * x)
                displacement_z = int(TILE_OVERLAP * z)
                print(f"Adjusting tile coordinates by overlap of {displacement_x},{displacement_z} px")
                paste_tile_coord_x += displacement_x
                paste_tile_coord_z += displacement_z

            print(f"Placing {tile.tile_filepath} at {paste_tile_coord_x}, {paste_tile_coord_z} (unit {x}, {z})")
            map_image.paste(tile.tile_image, (paste_tile_coord_x, paste_tile_coord_z))
            tile.unload()
        
        # save the map image
        map_image.save(output_filename, quality=96)
        print(f"Saved tiles to {output_filename}")


    def make_large_map(self, filepath: str = "map.jpeg", x_coods_start: int = -1, z_coord_start: int = -1, max_x_tile_count: int = -1, max_z_tile_count: int = -1):
        if x_coods_start < 0 and z_coord_start < 0 and max_x_tile_count < 0 and max_z_tile_count < 0:
            print("Creating large map from all tiles")
            self.composite_screenshot_tiles(self.screenshots, filepath)
            return

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

            # print(f"min_x_coord: {min_x_coord}, min_z_coord: {min_z_coord}, max_x_coord: {max_x_coord}, max_z_coord: {max_z_coord}")
            # print(f"Current axis tile counts: {x_tile_count}, {z_tile_count}")

            if (max_x_tile_count == 0 or x_tile_count <= max_x_tile_count) or (max_z_tile_count == 0 or z_tile_count <= max_z_tile_count):
                included_tiles.append(screenshot)

        print(f"Creating large map from {len(included_tiles)} tiles (min_x: {min_x_coord}, min_z: {min_z_coord}, max_x: {max_x_coord}, max_z: {max_z_coord})")
        self.composite_screenshot_tiles(included_tiles, filepath)

    def make_initial_tiles(self, output_directory: str, initial_z_dirname: int):
        # Initial z should usually be 5, as we support 5 levels of detail
        for screenshot in self.screenshots:
            normalized_x = int(screenshot.xCoordWS / self.tile_step_size)
            normalized_z = int(screenshot.zCoordWS / self.tile_step_size)

            # Folder structure is output_directory/initial_z_dirname/normalized_x/normalized_z
            # i.e. output_directory/5/0/0/tile.jpg
            intial_tile_filepath = os.path.join(output_directory, str(initial_z_dirname), str(normalized_x), str(normalized_z), f"{FINAL_TILE_FILENAME}.{FINAL_TILE_IMAGE_TYPE}")
            # copy the tile to the new folder
            if not os.path.exists(intial_tile_filepath):
                tile_directory_path = os.path.dirname(intial_tile_filepath)
                os.makedirs(tile_directory_path, exist_ok=True)

                print(f"Converting {screenshot.tile_filepath} to {intial_tile_filepath}")
                image = Image.open(screenshot.tile_filepath)

                
                target_size = TILE_CROP_SIZE + TILE_OVERLAP
                image_size = image.size
                if image_size[0] != target_size or image_size[1] != target_size:
                    left = (image_size[0] - target_size) / 2
                    top = (image_size[1] - target_size) / 2
                    right = (image_size[0] + target_size) / 2
                    bottom = (image_size[1] + target_size) / 2
                    image = image.crop((left, top, right, bottom))

                image.save(intial_tile_filepath, quality=95)


if __name__ == "__main__":
    # Set up the args - We take an input directory to locate the screenshots and write tiles next to them
    parser = argparse.ArgumentParser(description="Center crop screenshots to a given resolution")
    parser.add_argument("input_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("output_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("-m", "--make_map", help="Create a large map from the screenshots instead of the final tiles", action="store_true")
    args = parser.parse_args()

    print(f"Processing screenshots in {args.input_dir}")
    screenshot_processor = ScreenshotProcessor.from_directory(args.input_dir)
    screenshot_processor.make_tiles() # Will also delete the original screenshots if DELETE_ORIGINALS is True

    if args.make_map:
        print("Making large test map")
        screenshot_processor.make_large_map(os.path.join(args.output_dir, "test_map.jpeg"))
    else:
        print("Creating initial tiles")
        screenshot_processor.make_initial_tiles(args.output_dir, 0)

