import argparse
from enum import Enum
import os
import sys
import glob
from PIL import Image, ImageOps, ImageFilter
import numpy as np
# from scipy import fftpack

# Configuration - Make sure this matches the Enfusion Workbench tool settings
TILE_CROP_SIZE = 550 # pixels - Set this initially to be too large for perfect tiling
TILE_OVERLAP = -7  # pixels - Then adjust this value to get the perfect tiling testing in -make_map mode

# Optional configuration
SKIP_EXISTING_TILES = True # Skip creating tiles that already exist
DELETE_ORIGINALS = True # Delete the original screenshots after cropping the tiles to save disk space

INTERMEDIATE_TILE_FILENAME_SUFFIX = "tile" # only change this if you have also changed the Enfusion Workbench settings
FINAL_TILE_FILENAME = "tile"
FINAL_TILE_IMAGE_TYPE = "jpg"
MINIMUM_SCREENSHOT_WIDTH = 1920 # pixels - Minimum width of the screenshot to be considered a full screenshot

class ScreenshotTileType(Enum):
    RAW_SCREENSHOT = "raw_screenshot"
    CROPPED_TILE = "cropped_tile"

class Screenshot():
    type: ScreenshotTileType
    xCoordWS: int
    zCoordWS: int
    # This has two images, the full resolution raw screenshot, and the cropped tile
    _screenshot_filepath: str|None

    _tile_filepath: str|None
    _screenshot_image: Image.Image|None
    _tile_image: Image.Image|None

    def __init__(self, xCoordWS: int, zCoordWS: int, type: ScreenshotTileType, screenshot_filepath: str|None = None, tile_filepath: str|None = None):
        self.type = type
        self.xCoordWS = xCoordWS
        self.zCoordWS = zCoordWS
        self._screenshot_filepath = screenshot_filepath
        self._tile_filepath = tile_filepath
        self._screenshot_image = None
        self._tile_image = None

    def __str__(self):
        return f"Screenshot {self.xCoordWS}x{self.zCoordWS}, screenshot_filepath={self.screenshot_filepath}, tile_filepath={self.tile_filepath}"
    
    @property
    def screenshot_image(self):
        if self._screenshot_image is None:
            if self.screenshot_filepath and os.path.exists(self.screenshot_filepath):
                self._screenshot_image = Image.open(self.screenshot_filepath)
                
            else:
                raise RuntimeError(f"Screenshot image not found at {self.screenshot_filepath}")
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
        if self.screenshot_filepath is None:
            raise RuntimeError("Cannot generate tile path without a screenshot filepath")
        # take filepath, strip of .png, and add output_file_suffix + output_tile_type
        return self.screenshot_filepath.replace(".png", f"_{INTERMEDIATE_TILE_FILENAME_SUFFIX}.png")
    
    @property
    def coordinate_string(self) -> str:
        return self.make_coordinate_string(self.xCoordWS, self.zCoordWS)
    
    @classmethod
    def make_coordinate_string(cls, x: int, z: int) -> str:
        return f"Screenshot_{x}_{z}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Screenshot):
            return False
        return self.xCoordWS == other.xCoordWS and self.zCoordWS == other.zCoordWS

    def __hash__(self) -> int:
        return hash(self.coordinate_string)
    
    def create_cropped_tile(self):
        # crop the center of the image to crop_size x crop_size
        width, height = self.screenshot_image.size
        if width < MINIMUM_SCREENSHOT_WIDTH :
            print(f"ERROR: Screenshot {self.screenshot_filepath} is too small to crop, it is only {width}x{height} pixels\nDid you forget to press F11 after starting the screenshot capture process?")
            sys.exit(1)

        left = (width - TILE_CROP_SIZE) / 2
        top = (height - TILE_CROP_SIZE) / 2
        right = (width + TILE_CROP_SIZE) / 2
        bottom = (height + TILE_CROP_SIZE) / 2
        cropped_image = self.screenshot_image.crop((left, top, right, bottom))
        # set the jpeg quality to 95
        cropped_image.save(self.tile_filepath, quality=95)
        self.unload()  # Unload the images to free memory

    def tile_exists(self):
        return os.path.exists(self.tile_filepath)
    
    def get_unit_coordinates(self, min_x: int, min_z: int, filename_coordinate_step: int):
        return (int((self.xCoordWS - min_x) / filename_coordinate_step), int((self.zCoordWS - min_z) / filename_coordinate_step))

class ScreenshotProcessor():
    screenshots: list[Screenshot]
    mapped_screenshots: dict[str, Screenshot]
    _tile_step_size: int = -1

    def __init__(self, screenshots: list[Screenshot]|None = None):
        if screenshots is None:
            screenshots = []
        self.screenshots = screenshots
        self.mapped_screenshots = {}
        for screenshot in screenshots:
            self.mapped_screenshots[screenshot.coordinate_string] = screenshot
        if len(screenshots) != len(self.mapped_screenshots):
            raise RuntimeError("Duplicate screenshots found")

        if len(screenshots) > 0:
            self.sort()
    
    @classmethod
    def from_directory(cls, directory: str):
        screenshot_processor = ScreenshotProcessor()
        
        glob_match = os.path.join(directory, f"*{os.sep}*.png")
        matching_filepaths = glob.glob(glob_match)
        if len(matching_filepaths) == 0:
            raise RuntimeError(f"No screenshots found in {directory}")

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
                screenshot_processor.add_screenshot(Screenshot(x, z, ScreenshotTileType.CROPPED_TILE, tile_filepath=filepath))
            else:
                x = int(filename_elements[-2])
                z = int(filename_elements[-1])
                screenshot_processor.add_screenshot(Screenshot(x, z, ScreenshotTileType.RAW_SCREENSHOT, screenshot_filepath=filepath))

        return screenshot_processor
        
    def __str__(self):
        return f"ScreenshotProcessor {len(self.screenshots)} screenshots"
    
    def __repr__(self):
        return str(self)


    def add_screenshot(self, screenshot: Screenshot):
        if screenshot in self.mapped_screenshots:
            return
        self.screenshots.append(screenshot)
        self.mapped_screenshots[screenshot.coordinate_string] = screenshot
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
        # Use a different method to calculate the tile step size
        if len(self.screenshots) == 0:
            raise RuntimeError("No screenshots available to calculate tile step size")
        if self._tile_step_size != -1:
            return self._tile_step_size
        
        # Get the sorted set of unique x and z coordinates
        x_coords = sorted(set([screenshot.xCoordWS for screenshot in self.screenshots if screenshot.xCoordWS is not None]))
        z_coords = sorted(set([screenshot.zCoordWS for screenshot in self.screenshots if screenshot.zCoordWS is not None]))
        
        # Debug print the first 10 x coordinates
        if len(x_coords) == 0 or len(z_coords) == 0:
            raise RuntimeError("No valid x or z coordinates found in screenshots")
        x_diff = min([abs(x_coords[i] - x_coords[i+1]) for i in range(len(x_coords)-1)])
        z_diff = min([abs(z_coords[i] - z_coords[i+1]) for i in range(len(z_coords)-1)])

        # Check we're not zero
        if x_diff == 0 or z_diff == 0:
            raise RuntimeError("Calculated tile step size is zero, cannot proceed")

        # Check they're not different
        if x_diff != z_diff:
            print(f"WARNING: x_diff ({x_diff}) and z_diff ({z_diff}) are not equal. There might be an issue with the screenshot coordinates.")
        self._tile_step_size = min(x_diff, z_diff)
        print(f"Calculated tile step size: {self._tile_step_size}")
        return self._tile_step_size        

    def count(self):
        return len(self.screenshots)

    def crop_screenshots(self):
        for screenshot in self.screenshots:
            if screenshot.tile_exists() and SKIP_EXISTING_TILES:
                print(f"Skipping cropped tile {screenshot.tile_filepath}")
            else:
                print(f"Creating cropped screenshot for coordinate {screenshot.xCoordWS}, {screenshot.zCoordWS}")
                screenshot.create_cropped_tile()
                screenshot.unload()

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

    def make_initial_tiles(self, output_directory: str, initial_z_dirname: int, is_ocean_tile = lambda tile_path: False):
        if len(self.screenshots) < 2:
            raise RuntimeError("Not enough screenshots to calculate tile step size. At least two screenshots are required.")

        created_image_count = 0

        # Initial z should usually be 5, as we support 5 levels of detail
        for screenshot in self.screenshots:
            normalized_x = int(screenshot.xCoordWS / self.tile_step_size)
            normalized_z = int(screenshot.zCoordWS / self.tile_step_size)

            # Skip ocean tiles if the function indicates so
            if is_ocean_tile(screenshot.tile_filepath):
                print(f"Skipping ocean tile at {screenshot.tile_filepath}")
                continue

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

                image.save(intial_tile_filepath, quality=98)
                created_image_count += 1

        print(f"Created {created_image_count} initial tiles in {output_directory}/{initial_z_dirname}/")
        
def is_predominantly_ocean(image_path, target_color, color_threshold, percentage_threshold):
    """
    Checks if an image is predominantly a specific color, based on thresholds.

    Args:
        image_path (str): Path to the image file.
        target_color (tuple): The target (R, G, B) ocean color.
        color_threshold (int): The maximum Euclidean distance a pixel's color
                               can be from the target color to be counted.
        percentage_threshold (float): The minimum percentage (0.0 to 1.0) of
                                      pixels that must be "ocean" for the
                                      image to be considered an ocean tile.

    Returns:
        bool: True if the image is predominantly the target color, False otherwise.
    """
    try:
        # Open the image and convert to RGB
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            
            # Convert the image to a NumPy array
            # data will have shape (height, width, 3)
            data = np.array(img_rgb)
            
            # Get total number of pixels
            total_pixels = data.shape[0] * data.shape[1]
            if total_pixels == 0:
                return False # Handle empty image

            # --- Efficient NumPy Calculation ---
            
            # 1. Create a NumPy array for the target color
            target_color_np = np.array(target_color)
            
            # 2. Calculate the squared Euclidean distance from each pixel to the target color
            # We use squared distance to avoid a costly square root on every pixel.
            # np.sum(..., axis=-1) sums the (R-R')^2, (G-G')^2, (B-B')^2 for each pixel
            distances_sq = np.sum((data - target_color_np)**2, axis=-1)
            
            # 3. Count pixels where the squared distance is less than the squared threshold
            ocean_pixel_count = np.sum(distances_sq <= color_threshold**2)
            
            # 4. Calculate the percentage
            ocean_percentage = ocean_pixel_count / total_pixels
            
            # 5. Compare against the threshold
            return ocean_percentage >= percentage_threshold

    except (IOError, FileNotFoundError):
        print(f"Error: Could not open image at {image_path}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


if __name__ == "__main__":
    # Data related to detecting ocean tiles, which we skip to save on serving redundant tiles
    DEFAULT_OCEAN_COLOR = "#273132"
    DEFAULT_OCEAN_COLOR_TOLERANCE = 3 # Color tolerance for ocean detection - max Euclidean distance in RGB space
    MIN_OCEAN_PERCENTAGE = 0.98  # Minimum percentage of ocean pixels to consider a tile as ocean

    # Set up the args - We take an input directory to locate the screenshots and write tiles next to them
    parser = argparse.ArgumentParser(description="Center crop screenshots to a given resolution")
    parser.add_argument("input_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("output_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("-m", "--make_map", help="Create a large map from the screenshots instead of the final tiles", action="store_true")
    parser.add_argument("--skip-ocean-tiles", help="Skip creating tiles that are predominantly ocean", action="store_true")
    parser.add_argument("--ocean_color", default=DEFAULT_OCEAN_COLOR, help=f"Hex color code for the ocean (default: {DEFAULT_OCEAN_COLOR}).")
    parser.add_argument("--ocean_color_tolerance", type=int, default=DEFAULT_OCEAN_COLOR_TOLERANCE, help=f"Color tolerance for ocean detection (default: {DEFAULT_OCEAN_COLOR_TOLERANCE}).")
    parser.add_argument("--min_ocean_percentage", type=float, default=MIN_OCEAN_PERCENTAGE, help=f"Minimum percentage of ocean pixels to consider a tile as ocean (default: {MIN_OCEAN_PERCENTAGE}).")

    args = parser.parse_args()

    # Check the format of ocean color - starts with # and is 7 characters long
    if not args.ocean_color.startswith("#") or len(args.ocean_color) != 7:
        print("Error: Ocean color must be a hex code in the format #RRGGBB")
        sys.exit(1)
    # Now check for [1:] being valid hex digits
    try:
        int(args.ocean_color[1:], 16)
    except ValueError:
        print("Error: Ocean color must be a hex code in the format #RRGGBB")
        sys.exit(1)

    ocean_color_rgb = tuple(int(args.ocean_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

    print(f"Processing screenshots in {args.input_dir}")
    screenshot_processor = ScreenshotProcessor.from_directory(args.input_dir)
    
    print(f"Cropping {screenshot_processor.count()} screenshots")
    screenshot_processor.crop_screenshots() # Will also delete the original screenshots if DELETE_ORIGINALS is True

    if args.make_map:
        print("Making large test map")
        screenshot_processor.make_large_map(os.path.join(args.output_dir, "test_map.jpeg"))
    else:
        if args.skip_ocean_tiles:
            print("Skipping ocean tiles enabled")
            is_ocean_tile = lambda tile_path: is_predominantly_ocean(tile_path, ocean_color_rgb, args.ocean_color_tolerance, args.min_ocean_percentage)
        else:
            is_ocean_tile = lambda tile_path: False
      
        print("Creating initial tiles")
        screenshot_processor.make_initial_tiles(args.output_dir, 0, is_ocean_tile=is_ocean_tile)

    print("Done processing screenshots")
