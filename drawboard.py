import json
from PIL import Image, ImageDraw, ImageOps
from xml.etree.ElementTree import ElementTree
import math
from types import ListType
import os, sys
from os import path
from optparse import OptionParser
from urllib import urlretrieve
import operator

#C:\Program Files (x86)\Memoir'44 Editor\res\en
#<M44>/Contents/Resources/res/en/sed_data.xml
#<M44>/Contents/Resources/defaults/preferences/prefs.js 
#pref("m44sed.gwt.prefix" , "http://www.daysofwonder.com/gwt/sed/");
#pref("m44sed.image.prefix" , "http://static.daysofwonder.com/memoir44/sed_images/");

if sys.platform.startswith('win'):
    app_dirs = [ 
        "C:/Program Files (x86)/Memoir'44 Editor",
        "C:/Program Files/Memoir'44 Editor"
    ]
else:
    app_dirs = [
        "/Applications/Memoir '44 Editor"
    ]

sed_data_xml = None
for d in app_dirs:
    if not sys.platform.startswith('win'):
        d = path.splitext(d)[0] + '.app'
        d = path.join(d, 'Contents', 'Resources')
    
    fname = path.join(d, 'res', 'en', 'sed_data.xml')
    if path.exists(fname):
        sed_data_xml = fname
        break
    
print 'sed data at',sed_data_xml

#sed_data_xml = "/Applications/Memoir '44 Editor.app/Contents/Resources/res/en/sed_data.xml"

base_url = 'http://static.daysofwonder.com/memoir44/sed_images/'

base_dir = path.dirname(__file__)   # script directory
image_dir = path.join(base_dir,'images')   # where we'll cache all images
bg_data_xml = path.join(image_dir,'bg_data.xml')

class XY(tuple):
    def __new__(cls,x,y):
        return tuple.__new__(cls,(x,y))
       
    @property
    def x(self):
        return self[0]
        
    @property
    def y(self):
        return self[1]
        
    def rotate(self):
        return XY(self.y,self.x)


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

# represents the artwork for a tile, tag, unit etc that might be displayed
# in a hex.  Lazily loads images on request from disk with URL fallback
class Artwork:
    # initialize from an XML element containing <icon> and <name> children
    # optional <nbrOrientation> element identifies how many (sequentially
    # numbered) variants of the image there are
    def __init__(self, elt):
        (self.base,self.ext) = path.splitext(elt.find('icon').text)
        
        self.images = {}
        
        for tag in ['name','label','type','nbrOrientation']:
            kid = elt.find(tag)
            if kid is not None:
                setattr(self,tag,kid.text)
            else:
                setattr(self,tag,None)
        
        if self.nbrOrientation:
            self.nbrOrientation = int(self.nbrOrientation)
            self.base = self.base[:-1]
            
    # request for a particular bitmap of this art
    def getImage(self,orientation = 1):
        if not orientation: orientation = 1
        
        # check if we've already loaded it
        if not self.images.has_key(orientation):
            self.images[orientation] = None # assume the worst
            
            relpath = self.getRelativePath(orientation)
            fname = path.join(image_dir, relpath)
            # do we have a file?
            if not path.exists(fname):
                url = base_url + relpath
                print "Retrieving",fname
                if not path.exists(path.dirname(fname)):
                    os.makedirs(path.dirname(fname))
                try:
                    urlretrieve(url, fname)
                except:
                    print "Failed to retrieve",url
                    return None
                    
            try:
                self.images[orientation] = Image.open(fname)
            except:
                print "Failed to open",fname
                return None
                    
        return self.images[orientation]
    
    def getRelativePath(self,orientation = 1):
        if self.nbrOrientation:
            if not orientation: orientation = 1
            return self.base + `orientation` + self.ext
        else:
            return self.base + self.ext

class ArtLibrary:
    def __init__(self, xml_files):
        self.artworks = {}
        
        for xml_file in xml_files:
            xml = ElementTree(file=xml_file)
            for elt in xml.getiterator():
                if elt.find('icon') is not None:
                    art = Artwork(elt)
                    if not art.name:
                        print 'Skiping icon with no name',art.icon
                    self.artworks[art.name] = art  
                    
    def getImage(self,name,orientation=1):  
        if not self.artworks.has_key(name):
            return None
        
        return self.artworks[name].getImage(orientation)
    
class Board:
    hexXY = XY(188,217)                 # size of tile images in pixels
#    background_color = (79,105,66)      # olive green
    background_color = (255,255,255)    # white
    line_color = (214,35,44)            # dark red
    border_color = (0,0,0)              # black
    border_width = 1                    # pixels
    marginXY = XY(hexXY.x/2, hexXY.y/2)
    
    # actual tiles are 2.0866" (53mm) across the flats
    DPI = 90        # = 188 / 2.0866

    formats = {
        'standard' : XY(13,9),      # [(4,5,4) / (3.5, 5, 3.5) ] 
        'overlord' : XY(26,9),
        'breakthrough' : XY(13,17)
    }
    
    # the hexagon keys we can deal with, layered from bottom up
    drawing_layers = [
        'terrain',      # hexagonal terrain tile
        'lines',        # pseudo-key when we draw lines between flank
        'rect_terrain', # rectangular tile, like a bunker
        'obstacle',     # 3D obstacle like sandbags
        'unit',         # unit indicator
        'tags',         # token like victory marker
        'text'          # map label
    ]

    # return a list of background terrain names based on board format/style
    @staticmethod
    def backgroundTerrain(face, format):
        faces = {
            'countryside' : [['countryside']],
            'winter' :      [['snow']],
            'beach' :       [['countryside'],['beach'],['coast'],['ocean']],
            'desert' :      [['sand']]
            }   
                 
        names = faces[face]
        
        if face == 'beach':
            if format is 'overlord':
                repeat = (11,3,1,2)
            else:
                repeat = (4,3,1,1)
        else:
            if format is 'overlord':
                repeat = (17,)
            else:
                repeat = (9,)
    
        return sum(map(operator.mul, names, repeat),[])

            
    # coordinates - we use a system where each row and column counts 0,1,2,...
    # with top right starting from 0,0
    @staticmethod
    def coords(row, col):
      x = int(Board.hexXY.x * (col + (row%2)/2.))
      y = int(Board.hexXY.y * row * 3 / 4) 
      return XY(x + Board.marginXY.x, y + Board.marginXY.y)
    
    # convert from  m44 format where even rows have even cols, odd rows have odd cols
    @staticmethod
    def coords2(row, col2):
      return Board.coords(row, (col2 - (row%2))/2)

    def __init__(self, m44file):
        scenario = json.load(open(m44file))
        self.info = scenario['board']
        # info is a dictionary with board details like:
        # u'labels': [], 
        # u'hexagons': [{u'terrain': {u'name': u'highground'}, u'col': 0, u'row': 0}, ... 
        # u'type': u'STANDARD', 
        # u'face': u'WINTER'}

        self.game_info = scenario['game_info']
        # Scenario name is in a localized block, so take first localization
        # (maybe better to prefer a specific language?)
        # scenario = { "text": { "en": { "name": "My title", ...
        try:
            self.text = scenario['text'].values()[0]
        except:
            self.text = {}
        
        if not self.text.has_key('name'):
            self.text['name'] = '(unnamed scenario'
        
        # get the size and background icon generator
        format,face = self.info['type'].lower(),self.info['face'].lower()
        
        self.cols, self.rows = Board.formats[format]
        self.rowStyles = Board.backgroundTerrain(face,format)

    def getImage(self, icons):
        # create a white empty board image with correct size and scaling (DPI)
        size = XY(    Board.hexXY.x*self.cols + 2 * Board.marginXY.x, 
                  int(Board.hexXY.y*(self.rows*3+1)/4) + 2 * Board.marginXY.y)
        board = Image.new('RGB', size, Board.background_color)
        canvas = ImageDraw.Draw(board)
              
        # label the scenario
        canvas.text(
            (Board.marginXY.x / 2, Board.marginXY.y / 3),
            self.text['name'], fill = 'black')
        
        # paint the board background
        for row in xrange(self.rows):
            name = self.rowStyles[row]
            image = icons.getImage(name)
            if not image:
                print "No background image for",name
                continue
            
            for col in xrange(self.cols - (row%2)): # skip last hex on odd rows
                board.paste(image, Board.coords(row,col), image)

        # paint the right number of victory markers
        for p in ['1','2']:
            vp = self.game_info['victory_player' + p]
            
            name = 'medal' + p
            medal = icons.getImage(name)
            if not medal:
                print "Couldn't find victory marker image",name
                continue
                
            medal = medal.crop(medal.getbbox())
            if p == '1':    # Draw top medals upside facing board edge
                medal = ImageOps.flip(medal)
            mx,my = medal.size
            medal = medal.resize((int(mx*1.5),int(my*1.5)),Image.ANTIALIAS)
            mx,my = medal.size
            for col in xrange(self.cols-vp,self.cols):
                x,y = Board.coords(0, col)
                x,y = (x-mx/2,y-my*3/4)
                if p == '2':
                    x = board.size[0] - x - mx
                    y = board.size[1] - y - my
                board.paste(medal,(x,y),medal)
   
        # now paint on the overlay elements
        for key in Board.drawing_layers:
            if key is 'lines':      # placeholder for flank lines
                col = 0
                while col < self.cols:
                    for inc in [4,5,4]:
                       col += inc
                       if col >= self.cols:
                           break
                           
                       (x,y1) = Board.coords(0,col)
                       x -= 1
                       y1 += Board.hexXY.y/4
                       y2 = Board.coords(self.rows,0).y
                       
                       y = y1
                       while y < y2:
                           ye = min(y2,y+36)
                           canvas.line([(x,y),(x,ye)], fill=Board.line_color, width=7) 
                           y += 45
                continue
                
            hexagons = self.info[key is 'text' and 'labels' or 'hexagons']
            for hexagon in hexagons:
                col,row = hexagon['col'],hexagon['row']

                content = hexagon.get(key,None)
                if not content: continue
                # make everything a list for simplicity
                if type(content) is not ListType:
                    contents = [content]
                else:
                    contents = content

                xy = Board.coords2(row,col)
                
                if key is 'text':
                    for (i,content) in enumerate(contents):
                        (w,h) = canvas.textsize(content)
                        textXY = XY(
            xy.x - w/2 + Board.hexXY.x/2,
            xy.y - int(h*1.1*(i - len(contents)/2)) + Board.hexXY.y*3/4)
                        canvas.text(textXY, content, fill="black")
                        
                    continue            # on to next layer, else fall through
                    
                if any(key not in Board.drawing_layers + ['col','row'] 
                        for key in hexagon.keys()):
                    print 'unknown key in:',hexagon.keys()
                    
                for content in contents:
                    name = content['name']
                    image = icons.getImage(name, content.get('orientation',1))
                    if not image:
                        print "(col=%d,row=%d): No image for %s"%(
                            col,row,name)
                        continue
                        
                    board.paste(image,xy,image)
                  
        board = ImageOps.expand(
            board, border=Board.border_width, fill=Board.border_color)
        
        return board
        
                   
# divide an overall dimension into interval length chunks with given overlap
# between internal intervals
def subdivide(overall, interval, overlap):
    xs = [0.]
    while xs[-1] + interval < overall:
        xs.append(xs[-1] + interval - overlap)
    return xs

def splitImage(image, page, overlap, output_base, DPI, ext='.png'):
    size = XY(*image.size)
    
    # Try tiling both portrait and landscape modes
    tiling1 = XY( 
        subdivide(size.x, page.x, overlap),
        subdivide(size.y, page.y, overlap))
    pages1 = len(tiling1.x) * len(tiling1.y)
    
    tiling2 = XY(
        subdivide(size.x, page.y, overlap),
        subdivide(size.y, page.x, overlap))
    pages2 = len(tiling2.x) * len(tiling2.y)    
    
    if pages1 < pages2:
        print "Using standard (portrait) tiling (%d vs %d pages)"%(pages1, pages2)
        tiling = tiling1
    else:
        print "Using rotated (landscape) tiling (%d vs %d pages)"%(pages2, pages1)
        tiling = tiling2
        page = page.rotate() 
    
    for i,x in enumerate(map(int,tiling.x)):
        for j,y in enumerate(map(int,tiling.y)):
            tile = image.crop(
              (x,y, min(size.x, x+eff_size.x),min(size.y, y+eff_size.y)))
            tile.load()     # force a non-destructive copy
            tile.save(output_base + '%02d%02d'%(i,j) + ext, dpi=(DPI,DPI))
            
########################################

parser = OptionParser("Usage: %prog [options] input.m44 [output[.png]]",
    add_help_option=False)
parser.add_option('-?','--help', action='callback', 
  callback=lambda o,os,v,p: parser.print_help() or sys.exit())
parser.add_option('-p','--pagesize', type='string', default='letter',
    help="Page size or none to skip, i.e. %s"%(', '.join(page_sizes.keys())))
parser.add_option('-m','--margin', type='float', default=0.5,
    help="Blank margin (inches) between image and every page edge"),
parser.add_option('-o','--overlap', type='float', default=0.25,
    help="Overlap between internal boundaries of image sections"),

(options, args) = parser.parse_args()

if len(args) < 1 or len(args) > 2:
    if len(args) == 0:
        print 'ERROR: No input file specified!'
    else:
        print 'ERROR: Too many arguments provided (%s)'%`args`
    parser.print_help()
    sys.exit(-1)

scenario_file = args[0]
if not path.exists(scenario_file):
    print "ERROR: Can't find scenario file %s"%scenario_file
    sys.exit(-2)

options.pagesize = options.pagesize.lower()
if options.pagesize not in page_sizes.keys():
    print "ERROR: Unknown page size %s"%options.pagesize
    sys.exit(-2)

# output to basename (excluding extension) of last argument
output_base = path.splitext(args[-1])[0]
    
# read the foreground hex (and other tiles and counters) image dictionaries
icons = ArtLibrary([sed_data_xml, bg_data_xml])

board = Board(scenario_file)
image = board.getImage(icons)
saveDPI = (board.DPI, board.DPI)

page_inches = page_sizes[options.pagesize]

if not page_inches:     # just save full size image
    image.save(output_base + '.png', dpi=(board.DPI,board.DPI))
else:

    margin_size = int(options.margin * board.DPI)
    overlap_size = int(options.overlap * board.DPI)
    
    eff_size = XY(int(page_inches.x * board.DPI - 2*margin_size), 
                  int(page_inches.y * board.DPI - 2*margin_size))
    
    splitImage(image, eff_size, overlap_size, output_base, board.DPI)
    
