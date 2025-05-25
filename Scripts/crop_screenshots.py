import argparse
from enum import Enum
import os
import sys
import glob
from PIL import Image, ImageOps, ImageFilter
import numpy as np
from scipy import fftpack

# Configuration - Make sure this matches the Enfusion Workbench tool settings
TILE_CROP_SIZE = 550 # pixels - Set this initially to be too large for perfect tiling
TILE_OVERLAP = -7  # pixels - Then adjust this value to get the perfect tiling testing in -make_map mode

# Optional configuration
SKIP_EXISTING_TILES = True # Skip creating tiles that already exist
DELETE_ORIGINALS = False # Delete the original screenshots after cropping the tiles to save disk space

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
        return f"Screenshot {self.xCoordWS}x{self.zCoordWS}, screenshot_filepath={self.screenshot_filepath}, tile_filepath={self.tile_filepath}"
    
    @property
    def screenshot_image(self):
        if self._screenshot_image is None:
            if os.path.exists(self.screenshot_filepath):            
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
    mapped_screenshots: dict[str, Screenshot]
    _tile_step_size: int = -1  # This will be set after loading all screenshots
    
    def __init__(self, screenshots: list[Screenshot]|None = None):
        if screenshots is None:
            screenshots = []
        self.screenshots = screenshots
        self.mapped_screenshots = {}
        for screenshot in screenshots:
            self.mapped_screenshots[screenshot.coordinate_string] = screenshot
        if len(screenshots) != len(self.mapped_screenshots):
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
        
        # Calculate the step size based on looking at the minimum diffference between the x and z coordinates of all screenshots
        x_coords = [screenshot.xCoordWS for screenshot in self.screenshots if screenshot.xCoordWS is not None]
        z_coords = [screenshot.zCoordWS for screenshot in self.screenshots if screenshot.zCoordWS is not None]
        if len(x_coords) == 0 or len(z_coords) == 0:
            raise RuntimeError("No valid x or z coordinates found in screenshots")
        x_diff = min([abs(x_coords[i] - x_coords[i+1]) for i in range(len(x_coords)-1)])
        z_diff = min([abs(z_coords[i] - z_coords[i+1]) for i in range(len(z_coords)-1)])
        # Check they're not different
        if x_diff != z_diff:
            print(f"WARNING: x_diff ({x_diff}) and z_diff ({z_diff}) are not equal, using the minimum of both")
        self._tile_step_size = min(x_diff, z_diff)
        return self._tile_step_size        

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

    def auto_find_crop(self):
        # Find the highest detail screenshot
        
        # highest_detail_screenshot, highest_detail = self.find_highest_detail_screenshot()
        
        source_screenshot = self.mapped_screenshots[Screenshot.make_coordinate_string(5700, 3800)]
        
        # Then pick the z neighbour in either direction
        screenshot_above = self.find_neighbour(source_screenshot, 0, self.tile_step_size)
        screenshot_below = self.find_neighbour(source_screenshot, 0, -self.tile_step_size)
        
        # Pick the first non None neighbour
        neighbour_screenshot = screenshot_above if screenshot_above is not None else screenshot_below
        if neighbour_screenshot is None:
            raise RuntimeError(f"No neighbours found at coordinate {source_screenshot.xCoordWS}, {source_screenshot.zCoordWS}")
        
        # now get the size of the screenshot
        width, height = source_screenshot.screenshot_image.size
        
        # We now want to find the best matching row in the neighbour_screenshot for the source screenshot source row
        
        source_row = 0 if screenshot_above is not None else height - 1
        print(f"source_screenshot: {source_screenshot}")
        print(f"source_row: {source_row}")
        print(f"neighbour_screenshot: {neighbour_screenshot}")
        print(f"neighbour_screenshot direction: {'above' if screenshot_above is not None else 'below'}")
        
        best_match_index, best_match_score, all_scores = self.find_best_matching_row(source_screenshot, source_row, neighbour_screenshot)
        print(f"Best match row: {best_match_index}, Best match score: {best_match_score}")
        
        # Visualize the match
        visualization = self.visualize_match(source_screenshot.screenshot_filepath, source_row, neighbour_screenshot.screenshot_filepath, best_match_index)
        visualization.show()
    
    def find_neighbour(self, screenshot: Screenshot, x_offset: int, z_offset: int) -> Screenshot:
        x = screenshot.xCoordWS + x_offset
        z = screenshot.zCoordWS + z_offset
        neighbour_coordinate_lookup = Screenshot.make_coordinate_string(x, z)
        try:
            return self.mapped_screenshots[neighbour_coordinate_lookup]
        except KeyError:
            return None 

    def find_highest_detail_screenshot(self) -> tuple[Screenshot, float]:
        max_detail = ()
        for screenshot in self.screenshots:
            detail = self.measure_detail(screenshot)
            print(f"detail for {screenshot.xCoordWS}, {screenshot.zCoordWS}: {detail}")
            if max_detail == () or detail > max_detail[1]:
                max_detail = (screenshot, detail)
        return max_detail
    
    def measure_detail(self, screenshot: Screenshot) -> float:
        """
        Measure the detail of a screenshot by calculating the average pixel intensity of the edge image
        """
        image_path = screenshot.screenshot_filepath
        img = Image.open(image_path)
        # Convert to grayscale for edge detection
        gray_img = img.convert("L")
        # Apply edge detection filter
        edge_img = gray_img.filter(ImageFilter.FIND_EDGES)
        # Calculate the average pixel value in the edge image
        edge_intensity = sum(edge_img.getdata()) / (edge_img.width * edge_img.height)
        return edge_intensity

    
    def frequency_analysis(self, screenshot: Screenshot):
        image_path = screenshot.screenshot_filepath
        img = Image.open(image_path).convert("L")
        img_array = np.array(img)
        
        # Apply FFT to get frequency domain representation
        f_transform = fftpack.fft2(img_array)
        f_transform_shifted = fftpack.fftshift(f_transform)
        
        # Calculate magnitudes of frequency components
        magnitude = np.abs(f_transform_shifted)
        
        # Separate high frequency components (center is low frequency)
        h, w = magnitude.shape
        center_h, center_w = h//2, w//2
        
        # Create a mask for high frequency components
        radius = min(center_h, center_w) // 3  # Adjust this threshold as needed
        y, x = np.ogrid[:h, :w]
        mask = ((y - center_h)**2 + (x - center_w)**2) > radius**2
        
        # Calculate high frequency energy
        high_freq_energy = np.sum(magnitude * mask)
        total_energy = np.sum(magnitude)
        
        return high_freq_energy / total_energy


    def find_best_matching_row(self, source_screenshot: Screenshot, source_row_index: int, target_screenshot: Screenshot):
        """
        Find the best matching row in the target image for a given row from the source image.
        
        Parameters:
        -----------
        source_image_path : str
            Path to the source image
        target_image_path : str
            Path to the target image where we want to find the matching row
        source_row_index : int
            Index of the row in the source image to match
        metric : str, optional
            Similarity metric to use ('mse', 'ncc', or 'sad')
            
        Returns:
        --------
        best_match_index : int
            Index of the best matching row in the target image
        best_match_score : float
            Score of the best match (interpretation depends on metric)
        all_scores : list
            List of scores for all rows in the target image
        """
        
        source_img = source_screenshot.screenshot_image
        target_img = target_screenshot.screenshot_image
        
        # Convert to numpy arrays
        source_array = np.array(source_img)
        target_array = np.array(target_img)
        
        # Ensure images have the same width or resize if needed
        if source_array.shape[1] != target_array.shape[1]:
            print(f"Warning: Images have different widths. Source: {source_array.shape[1]}, Target: {target_array.shape[1]}")
            # Resize target to match source width if needed
            target_img = target_img.resize((source_img.width, target_img.height))
            target_array = np.array(target_img)
        
        # Extract the source row
        source_row = source_array[source_row_index]
        
        # Calculate scores for each row in the target image
        scores = []
        
        for i in range(target_array.shape[0]):
            target_row = target_array[i]
            
            # use normalized cross-correlation (NCC) (higher is better)
            
            # Handle multi-channel images
            if len(source_row.shape) > 1:
                # Calculate NCC for each channel and average
                channel_scores = []
                for c in range(source_row.shape[-1]):
                    src = source_row[..., c].astype(float)
                    tgt = target_row[..., c].astype(float)
                    
                    src_norm = src - np.mean(src)
                    tgt_norm = tgt - np.mean(tgt)
                    
                    numerator = np.sum(src_norm * tgt_norm)
                    denominator = np.sqrt(np.sum(src_norm**2) * np.sum(tgt_norm**2))
                    
                    # Avoid division by zero
                    if denominator == 0:
                        channel_scores.append(0)
                    else:
                        channel_scores.append(numerator / denominator)
                
                score = np.mean(channel_scores)
            else:
                src = source_row.astype(float)
                tgt = target_row.astype(float)
                
                src_norm = src - np.mean(src)
                tgt_norm = tgt - np.mean(tgt)
                
                numerator = np.sum(src_norm * tgt_norm)
                denominator = np.sqrt(np.sum(src_norm**2) * np.sum(tgt_norm**2))
                
                # Avoid division by zero
                if denominator == 0:
                    score = 0
                else:
                    score = numerator / denominator
                    
            scores.append(score)
        
        # NCC, higher is better
        best_match_index = np.argmax(scores)
        best_match_score = scores[best_match_index]
        
        return best_match_index, best_match_score, scores

    def visualize_match(self, source_image_path, source_row, target_image_path, target_row):
        """
        Create a visualization of the matching rows from both images.
        
        Parameters:
        -----------
        source_image_path : str
            Path to the source image
        target_image_path : str
            Path to the target image
        source_row : int
            Index of the row in the source image
        target_row : int
            Index of the matching row in the target image
            
        Returns:
        --------
        visualization : PIL.Image
            An image highlighting the matching rows in both images
        """
        # Open images
        source_img = Image.open(source_image_path)
        target_img = Image.open(target_image_path)
        
        # Convert to numpy arrays for manipulation
        source_array = np.array(source_img)
        target_array = np.array(target_img)
        
        # Create copies for highlighting
        source_highlight = source_array.copy()
        target_highlight = target_array.copy()
        
        # Highlight the rows (make them red for visibility)
        if len(source_array.shape) == 3:  # Color image
            source_highlight[source_row, :, 0] = 255  # Red channel
            source_highlight[source_row, :, 1] = 0    # Green channel
            source_highlight[source_row, :, 2] = 0    # Blue channel
            
            target_highlight[target_row, :, 0] = 255
            target_highlight[target_row, :, 1] = 0
            target_highlight[target_row, :, 2] = 0
        else:  # Grayscale image
            source_highlight[source_row, :] = 255
            target_highlight[target_row, :] = 255
        
        # Create a new image to show both side by side
        if len(source_array.shape) == 3:
            height = max(source_array.shape[0], target_array.shape[0])
            width = source_array.shape[1] + target_array.shape[1]
            visualization = np.zeros((height, width, 3), dtype=np.uint8)
            
            visualization[:source_array.shape[0], :source_array.shape[1]] = source_highlight
            visualization[:target_array.shape[0], source_array.shape[1]:] = target_highlight
        else:
            height = max(source_array.shape[0], target_array.shape[0])
            width = source_array.shape[1] + target_array.shape[1]
            visualization = np.zeros((height, width), dtype=np.uint8)
            
            visualization[:source_array.shape[0], :source_array.shape[1]] = source_highlight
            visualization[:target_array.shape[0], source_array.shape[1]:] = target_highlight
        
        return Image.fromarray(visualization)



if __name__ == "__main__":
    # Set up the args - We take an input directory to locate the screenshots and write tiles next to them
    parser = argparse.ArgumentParser(description="Center crop screenshots to a given resolution")
    parser.add_argument("input_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("output_dir", help="The directory containing the screenshots to crop")
    parser.add_argument("-f", "--find-crop", help="Automatically find the crop size", action="store_true")
    parser.add_argument("-m", "--make_map", help="Create a large map from the screenshots instead of the final tiles", action="store_true")
    args = parser.parse_args()

    print(f"Processing screenshots in {args.input_dir}")
    screenshot_processor = ScreenshotProcessor.from_directory(args.input_dir)
    
    if args.find_crop:
        print("Finding the crop size")
        screenshot_processor.auto_find_crop()
        sys.exit(0)
    
    screenshot_processor.make_tiles() # Will also delete the original screenshots if DELETE_ORIGINALS is True

    if args.make_map:
        print("Making large test map")
        screenshot_processor.make_large_map(os.path.join(args.output_dir, "test_map.jpeg"))
    else:
        print("Creating initial tiles")
        screenshot_processor.make_initial_tiles(args.output_dir, 0)

