#!/bin/bash
# filepath: deploy.sh

# Exit on error
set -e

TARGET_DIR=/Users/nick/Documents/SecurityPrices/InvestSmartExport

# List the files and folders to deploy (edit as needed)
FILES_AND_FOLDERS=(
  "main.py"
  "config_schemas.py"
  "pyproject.toml"
  "launch.sh"
)

# Create target directory if it doesn't exist
echo "Deploying to target directory: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

# Copy files and folders, creating intermediate directories as needed
for item in "${FILES_AND_FOLDERS[@]}"; do
  echo "Processing $item..."
  if [ -e "$item" ]; then
    dest="$TARGET_DIR/$item"
    mkdir -p "$(dirname "$dest")"
    if [ -d "$item" ]; then
      # Copy directory contents recursively, preserving structure
      cp -r "$item"/* "$dest"/ 2>/dev/null || true
    else
      # Copy file to the destination path
      cp "$item" "$dest"
    fi
  fi
done

# Handle config.yaml
if [ ! -f "$TARGET_DIR/config.yaml" ]; then
  if [ -f "config.yaml.example" ]; then
    cp "config.yaml.example" "$TARGET_DIR/config.yaml"
    echo "Copied config.yaml.example to $TARGET_DIR/config.yaml"
  else
    echo "config.yaml.example not found in source directory."
  fi
fi

echo "Deployment complete to $TARGET_DIR"