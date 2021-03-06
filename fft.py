##================================================================================================
##================================================================================================
##
##
##      ECSE 316 - Signald and Networks
##      Winter 2021 Edition
##      Assignment 2
##
##      Group 28
##      Edwin Pan and Ji Ming Li
##      Due 2021 April 5th
##
##
##================================================================================================
##================================================================================================


import sys
import cv2
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from PIL import Image
import numpy as np
import math
import heapq
import time


#================================================
#
#   PROGRAM CONSTANTS <deprecated>
#
#       Any pre-runtime-set variables are kept
#       here. Useful, in particular, for things
#       which ened tuning.
#
#       Coefficients defining the noise filter
#       are defined here.
#
#================================================

# In terms of normalized distance from centre to
# wall of the image, where is 0.5 denoted.
DENOISING_CENTRE = 0.5
# How rapidly the sigmoid function use applies.
# Use high value for binary threshold; use
# low value for soft transition.
DENOISING_HARSHNESS = 3.0



#================================================
#
#   INPUT PARSING METHODS
#
#       Methods for getting program parametres
#       from either the user or from the
#       filesystem for running the program.
#
#       Here, you find:
#           - Arguments Parser
#           - Image Parser
#
#================================================

# Based on the arguments provided when this
# program is called via python in a terminal,
# returns either the default or explicitly
# provided program parametres.
# Returns None, None if invalid input is detected
# Returns an integer and string for program
# mode of operation and filename repsectively
# otherwise.
def get_mode_and_filename_from_terminal_params():

    #DEFAULT PARAMETRES
    prog_mode = 1
    file_name = "moonlanding.png"

    #PARAMETRE PARSING
    #sys.argv returns a list of all argument. arg 0 is always the name of the program.
    args_valid = True
    most_recent_arg = ""
    for i in range(1, len(sys.argv) ):
        #if the previous argument is option -m for mode
        if most_recent_arg == "-m" :
            #Break if mode already changed
            if prog_mode != 1:
                print("Duplicate -m argument detected. Aborting...")
                return None, None
            prog_mode = int(sys.argv[i])
            args_valid = True
            #Break if mode out of bounds
            if prog_mode < 1 or prog_mode > 4:
                print("Invalid -m argument detected: \'", prog_mode, "\'. Aborting...")
                return None, None
        #if the previous argument is option -i for file
        elif most_recent_arg == "-i" :
            file_name = sys.argv[i]
            args_valid = True
        #keep track of the previous argument
        most_recent_arg = sys.argv[i]
        #if -m or -r is the last arg, it's invalid.
        if most_recent_arg == "-m" or most_recent_arg == "-i" :
            args_valid = False

    #Return None if problems detected
    if args_valid is False:
        print("Detected option without argument. Aborting...")
        return None, None

    #Return args if arguments accepted
    print("No confusing arguments found. Proceeding...")
    return prog_mode, file_name

# Get initial command line args and deal with
# retrieving image byte data here as needed
def get_image_from_filename( filename, preview_input = False ):
    #Open up the image.
    image = None
    try:
        image = cv2.imread(filename, cv2.IMREAD_GRAYSCALE)
    except FileNotFoundError:
        print("File ", filename, " was not found. Aborting...")
        return None
    #Represent image as array
    data = np.asarray(image)
    #Describe the image provided
    #print("Data is of shape ", data.shape)
    #print("Data preview: \n", data)
    #image2 = Image.fromarray(data)
    #If preview enabled, have a pop-out window to show the input.
    if preview_input:
        plt.imshow( data, cmap='Greys')
        plt.show()
    #Return the image in array form
    return image

#================================================
#
#   IMAGE-RELATED HELPER METHODS
#
#       A set of methods useful for interacting
#       with the numpy-array representation of
#       the image is provided here.
#
#================================================

# Returns the data in (x, y) of two-dimensional
# array data.
def get_in_image_of_xy( data, x, y ):
    return data[y][x]

# Sets the data in (x, y) of two dimensional
# array data with provided value value.
def set_in_image_of_xy( data, x, y, value ):
    data[y][x] = value
    return data

# Upsizes the image to nearest power of two
# width and height as needed for fft's.
def upsize_to_square_power_of_two(img):
    max_dim = max( len(img), len(img[0]) )
    new_dim = 2
    while True:
        if new_dim is max_dim:
            break
        elif new_dim > max_dim:
            break
        else:
            new_dim *= 2
    return cv2.resize(img, (new_dim,new_dim) )

# Returns the minimum value in a two dimensional
# array input arr.
def min_in_2d( arr ):
    min_val = float('inf')
    for subarr in arr:
        for element in subarr:
            if element < min_val:
                min_val = element
    return min_val

# Returns the maximum value in a two dimensional
# array input arr.
def max_in_2d( arr ):
    max_val = float('-inf')
    for subarr in arr:
        for element in subarr:
            if element > max_val:
                max_val = element
    return max_val

# Returns the complex-numbered 2d array into a
# real numbered 2d array comprising of the
# magnitudes at each original element.
def mag_2d_of_complex_2d( arr ):
    height = len(arr)
    width = len(arr[0])
    new_arr = np.empty( (height, width) )
    for i in range(height):
        for j in range(width):
            new_arr[j][i] = ( arr[j][i].real**2 + arr[j][i].imag**2 )**0.5
    return new_arr

# Returns the real-valued 2d array of arr by
# ignoring all the imaginary components.
def ignore_imaginaries( arr ):
    # Remove Complex Addend (bugfix)
    height = len(arr)
    width = len(arr[0])
    real_arr = np.empty( arr.shape )
    for i in range(height):
        for j in range(width):
            real_arr[i][j] = arr[i][j].real
    return real_arr

# Sigmoid function.
def sigmoid(x):
    return 1/( 1+math.exp(-x) )

# Radial Mask Function: Used to reduce noise
# the farther away out from the centre of a
# square frame something is.
# Distance is a normalized 0-1 where 0
# indicates being at the centre of the image
# while 1 indicates being in a centre of an
# edge of a square image.
def radial_inside_mask(x):
    return -sigmoid( DENOISING_HARSHNESS*(x-DENOISING_CENTRE) )

# Quadratic mask which uses a quadratic
# function with a trough (no peak) where
# positions where the function dips below
# 0 are set to 0 and locations
def mask_quadratic(x,y,dim,sinkage,harshness,radius):
    return max(0, 
                min(1,
                    min(harshness*(x/dim-0.5-radius)*(x/dim-0.5+radius),
                        harshness*(y/dim-0.5-radius)*(y/dim-0.5+radius))
                    -sinkage 
                    )
                )



#================================================
#
#   MATH IMPLEMENTATIONS
#       includes FFT and iFFT's as well as
#       useful saving and plotting functions.
#       
#       Methods completing DFT, FFT, iFFT,
#       2D FFT, 2D iFFT are here.
#
#       Methods creating plots and saving
#       transform arrays are also here.
#
#       Section's function implementations are
#       all written by Ji Ming Li.
#
#================================================

# Direct Fourier Transform on input 1D array x.
def dft(x):
    N = len(x)
    n = np.arange(N)
    k = n.reshape((N, 1))
    e = np.exp(-2j * np.pi * k * n / N)

    X = np.dot(e, x)
    return X

# Fast Fourier Transform on input 1D array x.
def fft(x):
    N = len(x)

    if N ==1:
        return x
    else:
        X_even = fft(x[::2])
        X_odd = fft(x[1::2])
        f = np.exp(-2j*np.pi*np.arange(N)/ N)
        X = np.concatenate([X_even+f[:int(N/2)]*X_odd, X_even+f[int(N/2):]*X_odd])

    return X

# Inverse Fourier Transform on input 1D array x.
def ifft(x):
    N = len(x)

    if N == 1:
        return x
    else:
        X_even = ifft(x[::2])
        X_odd = ifft(x[1::2])
        f = np.exp(2j*np.pi*np.arange(N)/ N)
        X = np.concatenate([X_even+f[:int(N/2)]*X_odd, X_even+f[int(N/2):]*X_odd])
        X = X/2
        return X

# Two-Dimensional Fourier Transform on 2d array x naive algorithm.
def dft2d(x):
    N = len(x)
    M = len(x[0])

    X = np.empty([N, M], dtype=complex)

    for i in range(M):
        X[:,i] = dft(x[:,i])
    for i in range(N):
        X[i] = dft(X[i])

    return X

# Two-Dimensional Fourier Transform on 2d array x.
def fft2d(x):
    N = len(x)
    M = len(x[0])

    X = np.empty([N, M], dtype=complex)

    for i in range(M):
        X[:,i] = fft(x[:,i])
    for i in range(N):
        X[i] = fft(X[i])

    return X

# Two-Dimensional Inverse Fourier Transform on
# 2d array x.
def ifft2d(x):
    N = len(x)
    M = len(x[0])

    X = np.empty([N, M], dtype=complex)

    for i in range(M):
        X[:,i] = ifft(x[:,i])
    for i in range(N):
        X[i] = ifft(X[i])

    return X

# Simple uniformly scaled plot of 2d array.
def plot(x):
#    N = len(x)
#    M = len(x[0])
    plt.imshow(abs(x))
    plt.show()

# Displays the provided image in input x.
def plotImage(x):
    img = Image.fromarray(x, 'L')
#    imgplot = plt.imshow(img)
    img.show()

# Creates a logarithmically y-scaled plot
# on input two dimensional array x.
# Modified from how it was originally written in colab
# to fix some errors.
#def logPlot(x):
#    cmap = colors['plasma']
#    cmap.set_bad(cmap(0))
#    h, xedges, yedges = np.histogram2d(x)
#    pcm = axes[1].pcolormesh(xedges, yedges, h.T, cmap=cmap,
#                         norm=LogNorm(vmax=1.5e2), rasterized=True)
#    fig.colorbar(pcm, ax=axes[1], label="# points", pad=0)
#    axes[1].set_title("2d histogram and log color scale")

# Saves the transform matrix x to file
# with name name.
#def saveToCSV(x, name):
#    np.savetxt(name+".csv", a, delimiter=",")



#================================================
#
#   MAIN
#
#================================================

def main():
    # Obtain user-defined program parametres
    mode, filename = get_mode_and_filename_from_terminal_params()
    # Stop for user errors
    if mode is None or filename is None:
        return
    # Attempt to retrieve image data
    img = get_image_from_filename(filename)
    # Stop for io errors
    if img is None:
        return

    # Switch between program modes:
    if mode is 1:
        # Perform FFT and output 1x2 plot of the
        # original image and the fourier signal.

        # Upscale, as needed, to an image of
        # resolution of 2^n for some natural
        # number n. Necessary for FFT.
        up_img = upsize_to_square_power_of_two( img )
        up_dim = len(up_img)
        # Get the 2D Fourier Transform
        up_2dft = fft2d(up_img)
        up_2dft2 = np.fft.fft2(up_img)
        # Scale it to original size
        #ft = cv2.resize( up_2dft.astype(np.uint8), (width, height) )
        ft = up_2dft
        # Construct the figure
        fig, (ax1, ax2, ax3) = plt.subplots(1,3)
        fig.suptitle("Image and its Fourier Transform")
        # Add the image as the leftside plot
        ax1.imshow(up_img, cmap='gray')
        # Create the logarithmic colormap of the
        # fourier transform as the rightside plot
        # Keep in mind to display not the literal
        # Fourier Transform, which is complex, but
        # its magnitudes.
        mag_ft = mag_2d_of_complex_2d(ft)
        min_mag_ft = min_in_2d(mag_ft)
        max_mag_ft = max_in_2d(mag_ft)
        mag_ft_graph = ax2.pcolormesh( 
                range(up_dim), range(up_dim), mag_ft, 
                norm=colors.LogNorm( vmin=min_mag_ft, vmax=max_mag_ft ), cmap='PuBu_r',
                shading='auto')
        fig.colorbar( mag_ft_graph, ax=ax2, extend='max')

        mag_ft2 = mag_2d_of_complex_2d(up_2dft2)
        min_mag_ft2 = min_in_2d(mag_ft2)
        max_mag_ft2 = max_in_2d(mag_ft2)
        mag_ft_graph2 = ax3.pcolormesh( 
                range(up_dim), range(up_dim), mag_ft2, 
                norm=colors.LogNorm( vmin=min_mag_ft2, vmax=max_mag_ft2 ), cmap='PuBu_r',
                shading='auto')
        fig.colorbar( mag_ft_graph2, ax=ax3, extend='max')
        # Show the plot
        plt.show()
        # Terminal Verbosity
        print("Executed program in mode 1. Now exiting!")

        return
    elif mode is 2:
        # Denoise Output: Output a 1x2 plot of
        # original image and denoised image.

        # Keep record of the original image
        # resolution.
        height = len(img)
        width = len(img[0])
        # Upscale image for fft and apply fft
        up_img = upsize_to_square_power_of_two( img )
        up_dim = len(up_img)
        up_fft = fft2d(up_img)
        # De-noise (Filter High Frequencies)
        # Also count zeros.
        zeros = 0
        for i in range(up_dim):
            for j in range(up_dim):
                mask = mask_quadratic(i,j,up_dim,0.4,12,0.25)
                up_fft[i][j] = up_fft[i][j]*mask
                if mask is 0:
                    zeros += 1
        print("Out of the ", up_dim**2, " Fourier Coefficients, ", zeros, " are zeroes.")
        # De-noise (Obtain image form)
        up_img = ifft2d(up_fft)
        # Remove Complex Addend (bugfix)
        up_img = ignore_imaginaries(up_img)
        # Resize back to original size
        denoised_img = cv2.resize( up_img, (width,height) )
        # Show plots
        fig, (ax1, ax2) = plt.subplots(1,2)
        fig.suptitle("Original Image and its following Denoised Version")
        ax1.imshow(img, cmap='gray')
        ax2.imshow(denoised_img, cmap='gray')
        plt.show()
        # Terminal Verbosity
        print("Executed program in mode 2. Now exiting!")

        return
    elif mode is 3:
        # Double Functionality: (A) Compress the
        # to various degrees and output the
        # results in a 2x3 plot; and
        # (B) Save the Fourier Transform Matrix
        # to CSV.

        # Compression Method
        # Prioritizes zeroing based on how manhattan
        # close coefficients are to the "middle"
        def compress( img, square_dim, per_cent ):
            # Make a copy for edits and returnage
            compressed_img = np.copy(img)
            # Figure out how many zeroes are needed
            target_zeros = square_dim**2*per_cent//100
            # Create an ordered list of coefficients
            # for zeroing
            heap = []
            for i in range(square_dim):
                for j in range(square_dim):
                    heapq.heappush(heap, ( abs( (i-square_dim/2)**0.5+(j-square_dim/2)**0.5), i, j ) )
            # Zeroing
            for i in range(target_zeros):
                throwaway, x, y = heapq.heappop(heap)
                compressed_img[x][y] = 0
            return compressed_img
        # Keep record of the original image
        # resolution.
        height = len(img)
        width = len(img[0])
        # Upscale image for fft and apply fft
        up_img = upsize_to_square_power_of_two( img )
        up_dim = len(up_img)
        up_fft = fft2d(up_img)
        # Compress Fouriers at 6 different levels
        compression_rates = [0,10,30,50,80,95]
        compressed_ffts = [up_fft, up_fft, up_fft, up_fft, up_fft, up_fft]
        for i in range(6):
            compressed_ffts[i] = compress(  compressed_ffts[i],
                                            up_dim,
                                            compression_rates[i]
                                            )
        # Translate Compressed Fouriers to Images
        compressed_img = [img, img, img, img, img, img]
        for i in range(6):
            compressed_img[i] = ignore_imaginaries( ifft2d( compressed_ffts[i] ) )
        # Save Compressed Fourier Matrices
        for i in range(6):
            save_name = filename.split('.')[0] + "CompressedBy" + str(compression_rates[i]) +"Percent.csv"
            np.savetxt( save_name, compressed_ffts[i], delimiter=',')
        # Prepare the figures of the 6 different 
        # levels of compression
        fig, subplots = plt.subplots(2,3)
        fig.suptitle("Image Compressed at 6 Increasing Intense Levels")
        for i in range(6):
            subplots[i//3][i%3].imshow( compressed_img[i], cmap='gray' )
            str_name = filename.split('.')[0] + " Image With " + str(compression_rates[i]) + "% Compression"
            subplots[i//3][i%3].set_title(str_name)
        # Show the plots
        plt.show()
        # Terminal Verbosity
        print("Executed program in mode 3. Now exiting!")

        return
    elif mode is 4:
        # Plotting Mode: Produces plots that
        # summarize the runtime complexity of
        # the Fourier Transform Algorithms.

        #size of matrix, capacity of computer, lets suppose 9 for now
        #e.g. so write 10 for 2 ** 9
        size = 11
        trials = 10
        runtime = np.zeros((2, size-5, trials+1))

        for i in range(size-5):
            runtime[0][i][0] = 2**(i+5)
            runtime[1][i][0] = 2**(i+5)
            for j in range(trials):
                arr = np.random.rand(2**(i+5),2**(i+5))
                start_time = time.time()
                dft2d(arr)
                dft_end = time.time()
                fft2d(arr)
                fft_end = time.time()
                runtime[0][i][j+1] = dft_end - start_time
                runtime[1][i][j+1] = fft_end - dft_end

        #x data
        x = []
        for i in range(5,size):
            x.append(int(2**i))
        #average
        avgdft = []
        for i in runtime[0]:
            avgdft.append(np.average(i[1:]))

        avgfft = []
        for i in runtime[1]:
            avgfft.append(np.average(i[1:]))

        #std dev.
        stddft = []
        for i in runtime[0]:
            stddft.append(np.std(i[1:]))

        stdfft = []
        for i in runtime[1]:
            stdfft.append(np.std(i[1:]))

        xpoints = x
        ypoints = avgdft
        zpoints = avgfft

        fig, ax = plt.subplots()

        ax.errorbar(xpoints, ypoints, yerr=stddft, label = "dft", solid_capstyle='projecting', capsize=2)
        ax.errorbar(xpoints, zpoints, yerr=stdfft, label = "fft", solid_capstyle='projecting', capsize=2)
        plt.title("runtime (second) comparison between dft and fft of different array size")
        plt.xlabel("size of 2d array")
        plt.ylabel("time in seconds")
        plt.xscale('log', basex=2)
        plt.legend()
        plt.show()
        # Terminal Verbosity
        print("Executed program in mode 4. Now exiting!")

        return
    else:
        print("Illegal mode detected. Exiting.")
        return

if __name__ == "__main__":
    main()
