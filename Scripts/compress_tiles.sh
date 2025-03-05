#!/bin/bash

# Optional script to compress the JPEG images in the LODS directory
# using ImageMagick. This script will create a new directory called
# Compressed_LODS with the compressed images.

# Set source and destination directories
SOURCE_DIR="LODS"
DEST_DIR="Compressed_LODS"

# Create the destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Find all JPEG files and process them
find "$SOURCE_DIR" -type f -name "*.jpg" | while read -r file; do
    # Calculate relative path from source directory
    relative_path="${file#$SOURCE_DIR/}"

    echo "Processing $relative_path"

    # Create corresponding directory structure in destination
    mkdir -p "$(dirname "$DEST_DIR/$relative_path")"
    
    # Process the image with ImageMagick
    # Options:
    # -strip: Remove metadata
    # -quality 85: Compress with 85% quality (adjust as needed)
    # -colorspace sRGB: Ensure consistent color space
    mogrify -strip \
            -quality 85 \
            -sampling-factor 4:2:0 \
            -colorspace sRGB \
            -interlace Plane \
            -define jpeg:dct-method=float \
            -path "$(dirname "$DEST_DIR/$relative_path")" \
            -format jpg \
            "$file"
done

echo "Image conversion complete!"
