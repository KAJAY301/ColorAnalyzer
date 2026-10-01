# Color Analyzer

Color Analyzer is a desktop application that reads an image or PDF file and identifies the dominant colors in the document. It groups visually similar hues, displays a palette summary, and shows the percentage and count of each detected color.

## Features

- Supports PNG, JPG, and PDF input files
- Merges all pages from a PDF into a single color analysis
- Detects the main colors using HSV-based clustering
- Displays a color table with:
  - swatch preview
  - color name
  - share percentage
  - pixel count
- Provides a Qt-based image viewer for checking the processed result

## Requirements

- Python 3.10+
- PyQt5
- OpenCV
- NumPy
- PyMuPDF

## Installation

1. Create and activate a virtual environment if needed.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the application with a file path:

```bash
python main.py image.png
python main.py document.pdf
```

On Windows, you can also use:

```bat
run.bat image.png
```

Then enter the number of colors to analyze in the GUI and click the analysis button.

## How It Works

The application converts the input image (or each PDF page) to HSV color space, samples the pixels, and clusters similar colors according to hue, saturation, and brightness. The result is shown in a table and visualized as a recolored output image.

## Supported File Types

- JPEG / JPG
- PNG
- PDF

## Notes

- For PDF files, all pages are combined before the color count is calculated.
- The script expects the path to a real file. If the file does not exist, it will exit with an error.
- The app is intended for local desktop use and requires a graphical session.

## Project Structure

- main.py — application entry point
- color_analyzer/ — application modules
  - analyzer.py — main window and analysis workflow
  - color_utils.py — color processing and image/PDF loading
  - widgets.py — image viewer and copyable table widgets
- resources/ — toolbar icons
- requirements.txt — Python dependencies
- run.bat — Windows shortcut for launching the app
- ColorAnalyzer.spec — PyInstaller build configuration

