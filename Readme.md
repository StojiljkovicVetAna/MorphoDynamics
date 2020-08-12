# Morphodynamics

This software can be used to analyze the dynamics of single-cells imaged by time-lapse fluorescence microscopy. The dynamics of morphology and fluorescence intensity distribution can be jointly analyzed through the segmentation and splitting of cells into a set of smaller regions (windows) that can be represented as two-dimensional grids to facilitate interpretation of events.

## Installation

We strongly recommend to install the necessary software via conda. If you don't have conda installed, follow [these instructions](https://docs.conda.io/en/latest/miniconda.html) to install a minimal version called miniconda.

Then, download this package to your machine, open a terminal and move to the downloaded folder (Morphodynamics-master). The latter contains an ```environment.yml``` file that can be used to setup a conda environment wih all necessary packages. For that, just execute the folling line:

```
conda env create -f environment.yml
````

Then activate the environment:

```
conda activate morphodynamics
```

and install the Morphodynamics package using pip (the dot at the end of the line is important):

```
pip install .
```

## Updates

To update your local installation with the latest version available on GitHub, activate the environment and install the package directly from GitHub:

```
conda activate morphodynamics 
pip install --upgrade git+https://github.com/ZejjT5E44/MorphoDynamics.git@master#egg=morphodynamics
```

The above command should prompt you to enter your GitHub username and password, as the repository is private.

## Usage

Whenever you want to use Jupyter and the Morphodynamics package, open a terminal, activate the environment 

```
conda activate morphodynamics
```

and start a Jupyter session:

```
jupyter notebook
```

Two notebooks are provided in the ```notebooks``` folder. [Morpho_segmentation.ipynb](Morpho_segmentation.ipynb) allows you to perform cell segmentation and windowing. It accepts data in the form of series of tiffs, tiff stacks or nd2 files (still experimental). Once segmentation is done and saved, that information can be used to proceed to the data analysis per se in the [InterfaceFigures.ipynb](InterfaceFigures.ipynb) notebooks. There you import the segmentation, and can choose from a variety of different analysis to plot.
