import json, sys
from os import path
from PIL import Image, ImageDraw
from argparse import ArgumentParser, ArgumentTypeError

from xy import XY

page_sizes = {
    'none': None,
    'a0' : XY(33.11, 46.81),
    'a1' : XY(23.39, 33.11),
    'a2' : XY(16.54, 23.39),
    'a3' : XY(11.69, 16.54),
    'a4' : XY( 8.27, 11.69),
    'letter' : XY(8.5,11),
    'legal'  : XY(8.5,14),
    'ledger' : XY(11,17),
    'tabloid': XY(17,11),
    '11x17'  : XY(11,17)
}

def setupArgParser(parser = None):    
    if not parser:
        parser = ArgumentParser(
            description = "Split an image for multi-page printing, based on DPI specified in the image")
        parser.add_argument('source_image', help='The image to split')
        parser.add_argument('output_base', nargs='?',
            help='The base path for output image(s)')
        
    parser.add_argument('-p','--page_size', default='letter', choices=page_sizes.keys(),
        help="Page size for tiled images, or none for single image")
    parser.add_argument('-m','--margin', type=float, default=0.5,
        help="Margin in inches between image and each page edge")
    parser.add_argument('-o','--overlap', type=float, default=0.25,
        help="Overlap in inches between adjoining image sections")
    parser.add_argument('--nomarks',action='store_true',default=False,
        help="Don't draw registration marks on tiled images")
    parser.add_argument('--dpi',type=int, default=None,
        help="Override image DPI information")
    return parser
    
# divide an overall dimension into interval length chunks with given overlap
# between internal intervals
def subdivide(overall, interval, overlap):
    xs = [0.]
    while xs[-1] + interval < overall:
        xs.append(xs[-1] + interval - overlap)
    return xs

# entrypoint for external caller that is using our argument processing
def saveTiledImagesArgs(image, basename, args, ext='.png'):
    saveTiledImages(image, basename,
        page_sizes[args.page_size], args.margin, args.overlap,
        ext, args.dpi, register_marks = not args.nomarks)
        
def saveTiledImages(image, basename, 
    pageXY_inches, margin_inches, overlap_inches,
    ext = '.png', dpi = None, register_marks = True):        
    
    if not dpi:
        try:
            dpi = image.info['dpi'][0]
        except:
            sys.exit("savedTiledImages: No DPI specified explicitly or found in image")
    
    if not pageXY_inches:     # just save full size image
        fname = basename + ext
        image.save(fname, dpi=(dpi,dpi))
        return [fname]          # early return
        
    # create the split up images
    margin_px = int(margin_inches * dpi)
    overlap_px = int(overlap_inches * dpi)
    
    tileXY_px = (pageXY_inches * dpi - XY(1,1)*2*margin_px).ints()
    
    fullXY_px = XY(*image.size)
    
    # Try tiling both portrait and landscape modes
    tiling1 = XY( 
        subdivide(fullXY_px.x, tileXY_px.x, overlap_px),
        subdivide(fullXY_px.y, tileXY_px.y, overlap_px))
    pages1 = XY(*map(len, tiling1))
    
    tiling2 = XY(
        subdivide(fullXY_px.x, tileXY_px.y, overlap_px),
        subdivide(fullXY_px.y, tileXY_px.x, overlap_px))
    pages2 = XY(*map(len, tiling2))
    
    n1 = pages1.x*pages1.y
    n2 = pages2.x*pages2.y
    if n1 < n2:
        print "Using standard (portrait) tiling on %d pages (%dx%d vs %dx%d)"%(
            n1,pages1.x,pages1.y,pages2.x,pages2.y)
        tiling = tiling1
        pages = pages1
    else:
        print "Using rotated (landscape) tiling on %d pages (%dx%d vs %dx%d)"%(
            n2,pages2.x,pages2.y,pages1.x,pages1.y)
        tiling = tiling2
        pages = pages2
        tileXY_px = tileXY_px.swap() 
    
    outputs = []
    for i,x in enumerate(map(int,tiling.x)):
        for j,y in enumerate(map(int,tiling.y)):
            tile = image.crop(
              (x,y, 
               min(fullXY_px.x, x+tileXY_px.x), min(fullXY_px.y, y+tileXY_px.y)))
            tile.load()     # force a non-destructive copy
            
            # possibly draw register marks
            if register_marks:
                canvas = ImageDraw.Draw(tile)
                xt,yt = tile.size
                d = overlap_px/10
                xo,yo = overlap_px/2,overlap_px/2
                if i > 0 or j > 0:
                    canvas.line((xo-d,yo,0,yo),width=1,fill='black')
                    canvas.line((xo,yo-d,xo,0),width=1,fill='black')
                    
                xo,yo = overlap_px/2,yt-overlap_px/2
                if i > 0 or j+1 < pages.y:
                    canvas.line((xo-d,yo,0, yo),width=1,fill='black')
                    canvas.line((xo,yo+d,xo,yt),width=1,fill='black')                        
            
                xo,yo = xt-overlap_px/2,overlap_px/2
                if i+1 < pages.x or j > 0:  
                    canvas.line((xo+d,yo,xt,yo),width=1,fill='black')
                    canvas.line((xo,yo-d,xo,0 ),width=1,fill='black')
                    
                xo,yo = xt-overlap_px/2,yt-overlap_px/2
                if i+1 < pages.x or j+1 < pages.y:               
                    canvas.line((xo+d,yo,xt,yo),width=1,fill='black')
                    canvas.line((xo,yo+d,xo,yt),width=1,fill='black')
                        
            fname = basename + '%02d%02d'%(i+1,j+1) + ext
            outputs.append(fname)
            tile.save(fname, dpi=(dpi, dpi))
            
    return outputs

########################################
if __name__ == "__main__":
    parser = setupArgParser()
    args = parser.parse_args()
    
    if not path.exists(args.source_image):
        print "ERROR: Can't find source image",args.source_image
        sys.exit(-1)
        
    args.page_size = args.page_size.lower()
    if args.page_size not in page_sizes.keys():
        print "ERROR: Unknown page size",args.page_size
        sys.exit(-2)
    
    # output to basename (excluding extension), based on source if not given
    if not args.output_base:
        args.output_base = args.source_image
    args.output_base, ext = path.splitext(args.output_base)
    
    if not ext:
        ext = path.splitext(args.source_image)[1]
        
    try:
        image = Image.open(args.source_image)
    except:
        print "ERROR: Couldn't open source image",args.source_image
        
    saveTiledImagesArgs(image, args.output_base, args)
    
