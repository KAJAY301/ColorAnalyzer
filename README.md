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

1. Install Rust and create and activate a Python virtual environment.
2. Install the Python dependencies and Maturin:
3. Build and install the native Rust extension:

```bash
pip install -r requirements.txt
pip install maturin
cd color_core
maturin develop --release
cd ..
```

## Usage

Start the application and choose a file using the **選擇檔案** button. You can use the same button later to switch to another image or PDF.

```bash
python main.py
```

You can also open a file directly by passing its path:

```bash
python main.py image.png
python main.py document.pdf
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
- If a selected file cannot be read, the app displays an error and remains open so you can choose another file.
- The app is intended for local desktop use and requires a graphical session.

## Project Structure

- `main.py` — application entry point
- `color_analyzer/` — GUI and image/color processing modules
- `color_core/` — Rust extension for performance-critical color processing
- `resources/` — toolbar icons
- `stylesheet.qss` — application stylesheet
- `requirements.txt` — Python runtime dependencies
- `ColorAnalyzer.spec` — PyInstaller build configuration
