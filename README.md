This Python script will render maps from Memoir '44 scenario files (.m44 format)
into image files segmented for printing on whatever paper size you like.

You can control the map scaling (if you prefer larger or smaller hexes),
paper size, and what details of the scenario are rendered (by default unit 
location and movable obstacles are not displayed).

It requires a copy of the Memoir '44 scenario editor, please purchase a copy 
at http://www.daysofwonder.com/

To use this script, you'll need a Mac or PC with Python and 
the Python image library (PIL) module.  

To install Python:

    - download version 2.7.x from http://www.python.org/download/releases
    - for Windows, use a 32-bit version even on a 64-bit machine
    
You can install PIL from http://www.pythonware.com/products/pil/ but I've had
problems with the font support.  I found that the Pillow distribution worked 
better (http://pypi.python.org/pypi/Pillow).  

To install Pillow:

    - install setuptools (http://pypi.python.org/pypi/setuptools).  For windows
      this has a standard installer.
    - copy the URL for the Pillow Egg file matching your python version
      (find it at http://pypi.python.org/pypi/Pillow#downloads)
    - using a command shell, install Pillow using setuptools' easy_install, 
      something like this:

      c:\python27\scripts\easy_install http://pypi.python.org/packages/2.7/P/Pillow/Pillow-1.7.7-py2.7-win32.egg#md5=b3f805a974b4b4525799f23d0028ea14
      
Now test the script.

In a command shell, change to the directory where you install the 'drawboard.py'
script and associated files.  Try a test like this (change the path for python 
as needed):


    c:\python27\python drawboard.py juno.m44

This should create a set of 8.5x11 image files for the Juno scenario.  The
images are saved with a dot-per-inch setting so that when printed at 100% scale
they will fill the target page completely (minus a border), with hex sizes
matching the original M44 boards.

If that all works, you can design and save your own .m44 scenarios, and render
your own maps. Make sure you print the images a full size (according to image 
DPI).  On a PC I find IrfanView's thumbnail view useful: you can select all
the images making up a map and then batch print them on selected paper at full 
scale.  You can get IrfanView, a great free graphic viewer, at www.irfanview.com

There are also a number of options to control details of how the script works. 
To see a list of options just do:

    c:\python27\python drawboard.py --help

You might want to try options like this:

    --hexwidth 3.0      Print maps with larger hexes (3" across the flats)
    
    --pagesize a4       Make image sections that fit on European A4 paper
    
    --pagesize none     Create one big image without segmenting, so you
                        can use your flat-screen TV as the board :-)
                        
    --xlayers none      Draw all map layers (including units and obstacles
                        which are normally skipped)
                        
                        
Author: Patrick Surry (patrick.surry@gmail.com)





