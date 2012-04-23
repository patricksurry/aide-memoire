import json
from PIL import Image, ImageDraw, ImageOps, ImageFont
from xml.etree.ElementTree import ElementTree
import math
from types import ListType
import os, sys
from os import path
from argparse import ArgumentParser
from urllib import urlretrieve
import operator
from xy import XY

# default location for M44 editor
if sys.platform.startswith('win'):
    app_dirs = [ 
        "C:/Program Files (x86)/Memoir'44 Editor",
        "C:/Program Files/Memoir'44 Editor"
    ]
else:
    app_dirs = [
        "/Applications/Memoir '44 Editor"
    ]
    
base_url = 'http://static.daysofwonder.com/memoir44/sed_images/'


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
    unitTL = XY(44,80)                  # top-left corner of unit symbol
    badgeSize = XY(64,64)               # size to scale unit badges to
#    background_color = (79,105,66)      # olive green
    background_color = (255,255,255)    # white
    border_color = (0,0,0)              # black
    border_width = 1                    # pixels
    marginXY = hexXY.doti((1/3., 1/2.)) # whitespace around tiles
    dash_color = (214,35,44)            # dark red
    dash_length = (36,9)                # black/white length
    dash_width = 7                      # pixels
    
    formats = {
        'standard' : XY(13,9),      # [(4,5,4) / (3.5, 5, 3.5) ] 
        'overlord' : XY(26,9),
        'breakthrough' : XY(13,17)
    }
    
    # the hexagon keys we can deal with, layered from bottom up
    drawing_layers = [
        'terrain',      # hexagonal terrain tile
        'lines',        # pseudo-layer to draw dotted lines between flanks
        'rect_terrain', # rectangular tile, like a bunker
        'obstacle',     # 3D obstacle like sandbags
        'unit',         # unit indicator, includes nbr_units and badge sublayers
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
      xy = Board.hexXY.doti((col + (row%2)/2., row * 3 / 4.))
      return xy + Board.marginXY
    
    # convert from  m44 format where even rows have even cols, odd rows have odd cols
    @staticmethod
    def coords2(row, col2):
      return Board.coords(row, (col2 - (row%2))/2)

    def __init__(self, m44file, hexWidth = 2.0866):
        # use hexWidthto choose a particular hex width in inches
        # actual M44 tiles are 2.0866" (53mm) across the flats
        self.DPI = int(round(Board.hexXY.x / hexWidth))
        
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

    def getImage(self, icons, skipLayers = []):
        # create a white empty board image with correct size and scaling (DPI)
        size = Board.marginXY * 2 + \
            Board.hexXY.doti( (self.cols, (self.rows*3+1)/4.) )
        board = Image.new('RGB', size, Board.background_color)
        canvas = ImageDraw.Draw(board)
              
        try:
            font = ImageFont.truetype('verdanab.ttf',32)
        except:
            print "Couldn't open Verdana TTF, using (ugly) system default"
            font = ImageFont.load_default()
            
        # label the scenario
        canvas.text(Board.marginXY.doti( (1/2., 1/3.) ),
            self.text['name'], fill = 'black', font=font)
        
        # paint the board background
        outline = icons.getImage('outline')
        for row in xrange(self.rows):
            name = self.rowStyles[row]
            image = icons.getImage(name)
            if not image:
                print "No background image for",name
                continue
            
            for col in xrange(self.cols - (row%2)): # skip last hex on odd rows
                xy = Board.coords(row,col)
                if outline: board.paste(outline, tuple(xy), outline)
                board.paste(image, tuple(xy), image)

        # medal1 - Allies Medal
        # medal2 - German Medal
        # <note there isn't a medal3>
        # medal4 - Victoria Cross
        # medal5 - Italian Medal of Valor
        # medal6 - Hero of the Soviet Union Medal
        # medal7 - Order of the Golden Kite Medal
		medal_dict = {
		    # Default axis / allies medals in side_player[1|2] value
		    'ALLIES' : 1, 'AXIS' : 2, 
		    # Country-specific medals, coded in country_player[1|2] value
		    'US' : 1, 'DE' : 2, 'GB' : 4, 'IT' : 5, 'RU' : 6, 'JP' : 7
		}
		
        # paint the victory medals, with player1 at the top (flipped)
        # and player2 at the bottom.
        for p in ['1','2']:
            vp = self.game_info.get('victory_player' + p, 6)
            
            side = self.game_info.get('side_player' + p, '')
            country = self.game_info.get('country_player' + p, '')
            
            medal_num = medal_dict.get(country, None)
            if not medal_num:
                medal_num = medal_dict.get(side, None)
                
            medal_name = 'medal' + (medal_num and `medal_num`) or p
            
            medal = icons.getImage(medal_name)
            if not medal:
                print "Couldn't find victory marker image",name
                continue
                
            medal = medal.crop(medal.getbbox())
            if p == '1':    # Draw top medals upside facing board edge
                medal = ImageOps.flip(medal)
            medal = medal.resize((XY(*medal.size) * 1.5).ints(),Image.ANTIALIAS)
            mxy = XY(*medal.size)
            for col in xrange(self.cols-vp,self.cols):
                xy = Board.coords(0, col) - mxy.doti((1/2.,3/4.))
                if p == '2':    # Position bottom medals by reflection
                    xy = - xy - mxy + board.size
                board.paste(medal,tuple(xy),medal)
   
        # now paint on the overlay elements
        for key in Board.drawing_layers:
            if key in skipLayers:
                continue            # skipping this layer?
                
            if key is 'lines':      # placeholder for flank lines
                col = 0
                while col < self.cols:
                    for inc in [4,5,4]:
                       col += inc
                       if col >= self.cols:
                           break
                           
                       # Find starting point of dashed flank line
                       (x,y1) = Board.coords(0,col)
                       x -= Board.dash_width / 2 - 2
                       y1 += Board.hexXY.y/4
                       # Find ending point
                       y2 = Board.coords(self.rows,0).y
                       
                       # Draw the dashed line
                       y = y1
                       while y < y2:
                           ye = min(y2, y+Board.dash_length[0])
                           canvas.line([(x,y),(x,ye)], 
                               fill=Board.dash_color, width=Board.dash_width) 
                           y += sum(Board.dash_length)
                           
                continue            # on to next layer
                
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
                        wh = XY(*canvas.textsize(content, font=font))
                        pos = xy + Board.hexXY.doti( (1/2., 3/4.) ) \
                            - wh.doti( (1/2., 1.1*(i - len(contents)/2)) )
                        canvas.text(pos, content, fill="black", font=font)
                        
                    continue            # on to next hex
                    
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
                    board.paste(image,tuple(xy),image)
                    
                    # handle nbr_units and badge attributes within unit layer
                    if content.has_key('badge'):    # unit badges
                        # badges are not padded to hex size, and too small
                        # so resize and center on unit top left corner
                        image = icons.getImage(content['badge'])
                        image = image.resize(Board.badgeSize,Image.ANTIALIAS)
                        if image:
                            pos = xy + Board.unitTL - Board.badgeSize / 2
                            board.paste(image, tuple(pos), image)
                            
                    if content.has_key('nbr_units'):
                        image = icons.getImage('nbr_units', int(content['nbr_units']))
                        if image:
                            board.paste(image, tuple(xy), image)
                  
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
        page = page.swap() 
    
    for i,x in enumerate(map(int,tiling.x)):
        for j,y in enumerate(map(int,tiling.y)):
            tile = image.crop(
              (x,y, min(size.x, x+eff_size.x),min(size.y, y+eff_size.y)))
            tile.load()     # force a non-destructive copy
            tile.save(output_base + '%02d%02d'%(i,j) + ext, dpi=(DPI,DPI))
            
########################################

parser = ArgumentParser(
    description = "Render a Memoir 44 scenario file for multi-page printing")
parser.add_argument('scenario_file', 
    metavar='scenario.m44', help='The M44 scenario to render')
parser.add_argument('output_base', nargs='?',
    metavar='outputbase.png', help='The canonical path for output image(s)')
parser.add_argument('-a','--appdir', default=None,
    help='Pathname of the Memoir 44 Editor folder')
parser.add_argument('-w','--hexwidth', type=float, default=2.0866,
    help="Hex width in inches across the flats")
parser.add_argument('-p','--pagesize', default='letter',
    help="Page size to tile image over, or none for single large image.  Supported values: %s"%(', '.join(page_sizes.keys())))
parser.add_argument('-m','--margin', type=float, default=0.5,
    help="Margin in inches between image and each page edge")
parser.add_argument('-o','--overlap', type=float, default=0.25,
    help="Overlap in inches between adjoining image sections")
parser.add_argument('-x','--xlayers', nargs='+',
    choices=Board.drawing_layers + ['none'], default=['obstacle','unit'],
    help="List of drawing layers to skip")

args = parser.parse_args()

if args.appdir:
    if not path.exists(args.appdir) and not path.exists(args.appdir + '.app'):
        print "Can't find specified appdir:",args.appdir
    else:
        if path.isfile(args.appdir):
            args.appdir = path.dirname(args.appdir)
        app_dirs = [args.appdir] + app_dirs
        
sed_data_xml = None
for d in app_dirs:
    # Mac install is at /path/appname.app/Contents/Resources/...
    if not sys.platform.startswith('win'):
        d = path.splitext(d)[0] + '.app'    # ensure .app terminated
        d = path.join(d, 'Contents', 'Resources')
    
    fname = path.join(d, 'res', 'en', 'sed_data.xml')
    if path.exists(fname):
        sed_data_xml = fname
        break

if not sed_data_xml:
    print "Can't find Memoir '44 Editor resource data, sorry"
    sys.exit(-1)

base_dir = path.dirname(__file__)   # script directory
image_dir = path.join(base_dir,'images')   # where we'll cache all images
bg_data_xml = path.join(image_dir,'bg_data.xml')

if not path.exists(args.scenario_file):
    print "ERROR: Can't find scenario file %s"%args.scenario_file
    sys.exit(-1)

args.pagesize = args.pagesize.lower()
if args.pagesize not in page_sizes.keys():
    print "ERROR: Unknown page size %s"%args.pagesize
    sys.exit(-2)

# output to basename (excluding extension), based on scenario file if not given
if not args.output_base:
    args.output_base = args.scenario_file
args.output_base = path.splitext(args.output_base)[0]
    
# read the foreground hex (and other tiles and counters) image dictionaries
icons = ArtLibrary([sed_data_xml, bg_data_xml])

board = Board(args.scenario_file, hexWidth=args.hexwidth)
image = board.getImage(icons, skipLayers=args.xlayers)
saveDPI = (board.DPI, board.DPI)

page_inches = page_sizes[args.pagesize]

if not page_inches:     # just save full size image
    image.save(args.output_base + '.png', dpi=(board.DPI,board.DPI))
else:
    # create the split up images
    margin_size = int(args.margin * board.DPI)
    overlap_size = int(args.overlap * board.DPI)
    
    eff_size = page_inches * board.DPI - 2*margin_size
    
    splitImage(image, eff_size, overlap_size, args.output_base, board.DPI)
    
