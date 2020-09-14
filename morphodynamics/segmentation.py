import matplotlib.pyplot as plt
from skimage.exposure import histogram
from skimage.filters import gaussian, threshold_otsu, farid
from skimage.morphology import binary_closing, binary_erosion, disk
from skimage.measure import find_contours, label, regionprops
from scipy.interpolate import UnivariateSpline
from scipy.signal import argrelmin
from scipy.ndimage import median_filter
from scipy.ndimage.morphology import binary_fill_holes
from scipy.ndimage.measurements import center_of_mass
import numpy as np
from tifffile import imread, imsave
from cellpose import models




# from ArtifactGeneration import FigureHelper

# fh = FigureHelper(not True)

def segment_threshold(x, sigma, T, location):
    """Segment the cell image, possibly with automatic threshold selection."""

    # Determine the threshold based on the histogram, if not provided manually
    if T is None:
        h, _ = histogram(x, source_range='dtype')  # Compute histogram of image
        s = UnivariateSpline(range(0, 65536), h)  # Interpolate the histogram counts using a smoothing spline
        n = np.arange(0, 65535, 1)  # Create array with positions of histogram bins
        hs = s(n)  # Evaluate smoothing spline
        n0 = np.argmax(hs)  # Find position of maximum
        m = argrelmin(hs)[0]  # Find positions of local minima
        m = m[hs[m] < 0.2*hs[n0]]  # Remove local minima that are too strong
        T = m[n0 < m][0]  # Select first local minimum after maximum

    # # Artifact generation
    # if fh.debug & (T is None):
    #     fh.open_figure('Histogram')
    #     plt.plot(h, 'b', lw=0.1, zorder=50)
    #     # plt.xlim(0, 1000)
    #     plt.plot(n, hs, 'r', lw=0.1, zorder=100)
    #     plt.plot(n0, hs[n0], 'go', zorder=10)
    #     plt.plot(T, hs[T], 'yo', zorder=10)
    #     fh.close_figure()
    # fh.show()

    # Segment image by thresholding
    if sigma > 0:
        y = gaussian(x, sigma=sigma, preserve_range=True)  # Smooth input image with a Gaussian
        # y = median_filter(x, 9)
    else:
        y = x
    z = T < y  # Threshold image
    regions = label(z)

    return regions


def segment_farid(x):

    farid2 = farid(gaussian(x, 2, preserve_range=True)) > 1

    #farid_lab = label(farid2)
    #farid_reg = regionprops(farid_lab)
    #farid_indices = np.array(
    #    [0] + [x.label if x.area > 500 else 0 for x in farid_reg]
    #).astype(int)
    #farid3 = farid_indices[farid_lab] > 0
    #farid4 = binary_closing(farid3, disk(3))

    farid3 = binary_closing(farid2, disk(3))
    farid4 = binary_erosion(farid3, disk(3))

    farid_lab = label(farid4)
    farid_reg = regionprops(farid_lab)
    farid_indices = np.array(
        [0] + [x.label if x.area > 500 else 0 for x in farid_reg]
    ).astype(int)
    regions = farid_indices[farid_lab] > 0
    regions = label(regions)

    return regions


def track_threshold(regions, location):
    """Given a labelled mask and a location, keep the label closest to location"""

    nr = np.max(regions)
    if location is None: # Keep only the largest region
        sr = np.zeros((nr,)) # Allocate array of region sizes
        for k in range(nr):
            sr[k] = np.sum(binary_fill_holes(regions == k+1)) # Populate array
        k = np.argmax(sr) # Get index of largest region
        z = binary_fill_holes(regions == k+1) # Create mask of largest region
    else: # Keep the region that is closest to the specified location
        cm = np.zeros((nr,2)) # Allocate center of masses of regions
        for k in range(nr):
            cm[k] = center_of_mass(regions == k+1) # no hole filling if location is given
            #cm[k] = center_of_mass(binary_fill_holes(regions == k+1)) # Populate array
        k = np.argmin([np.linalg.norm(cm0-location) for cm0 in cm])  # Get index of closest region
        z = binary_fill_holes(regions == k+1)  # Create mask of closest region

    # # Fill holes in mask
    # z = binary_fill_holes(z)
    # # z[mask>0] = 0

    # # Artifact generation
    # fh.imshow('Input image', x)
    # fh.imshow('Segmented image', 255 * (T < y).astype(np.uint8))
    # fh.imshow('Filled largest segmented region', 255 * z.astype(np.uint8))
    # # fh.imshow('All regions', regions)
    # fh.show()

    return z


def segment_cellpose(model, x, diameter, location):
    """Segment image x using Cellpose. If model is None, a model is loaded"""

    if model is None:
        model = models.Cellpose(model_type='cyto')
    m, flows, styles, diams = model.eval([x], diameter=diameter, channels=[[0, 0]])
    m = m[0]
    return m


def track_cellpose(regions, location):
    """Given a labelled mask and a location, keep the label closest to location"""

    nr = np.max(regions)
    if location is None: # Keep only the largest region
        # m = m[np.argmax([np.sum(m0) for m0 in m])]
        sr = np.zeros((nr,)) # Allocate array of region sizes
        for k in range(nr):
            sr[k] = np.sum(regions == k+1) # Populate array
        k = np.argmax(sr) # Get index of largest region
        regions = regions == k+1 # Create mask of largest region
    else: # Keep the region that is closest to the specified location
        # nr = len(m)
        cm = np.zeros((nr, 2)) # Allocate center of masses of regions
        for k in range(nr):
            cm[k] = center_of_mass(regions == k+1) # Populate array
        k = np.argmin([np.linalg.norm(cm0-location) for cm0 in cm])  # Get index of closest region
        regions = regions == k+1 # Create mask of closest region
    return regions


def extract_contour(mask):
    """ Extract pixels along contour of mask. """

    return np.asarray(find_contours(mask, 0, fully_connected='high')[0], dtype=np.int)


def estimateBleaching(filename, K, shape):
    """Estimate the intensity decay due to bleaching."""

    x = np.zeros((K,) + shape, dtype=np.uint16)
    c = np.zeros((K,) + shape + (3,), dtype=np.uint8)
    I = np.zeros((K,))
    for k in range(K):
        x[k, :, :] = imread(filename + str(k + 1) + '.tif') # Input image
    xmax = np.max(x)
    for k in range(K):
        c[k, :, :, 1] = 255. * x[k, :, :] / xmax
        m = threshold_otsu(x[k, :, :]) < x[k, :, :]
        c[k, :, :, 0] = 255 * m
        I[k] = np.mean(x[k][m])
        # p1.imshow('Segmentation', c[k, :, :, :])
        # p1.show()
    # imsave(fh.figure_dir + 'Segmentation.tif', c)
    # fh.open_figure('Average intensity in segmented region')
    # plt.plot(I)
    # fh.close_figure()

# x = imread('C:\\Work\\UniBE 2\\Guillaume\\Example_Data\\FRET_sensors + actin\\Histamine\\Expt2\\w16TIRF-CFP\\RhoA_OP_his_02_w16TIRF-CFP_t53.tif')
# segment(x)

# calibrateBleaching('C:/Work/UniBE2/Guillaume/Example_Data/FRET_sensors + actin/Histamine/Expt2/w16TIRF-CFP/RhoA_OP_his_02_w16TIRF-CFP_t', 159, (358, 358))
# calibrateBleaching(r'C:\Work\UniBE2\Guillaume\Example_Data\FRET_sensors + actin\PDGF\RhoA_multipoint_0.5fn_s3_good\w34TIRF-mCherry\RhoA_multipoint_0.5fn_01_w34TIRF-mCherry_s3_t', 750, (358, 358))