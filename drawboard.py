#!/usr/bin/python
import json
from PIL import Image, ImageDraw, ImageOps, ImageFont
from xml.etree.ElementTree import ElementTree
import math
from types import ListType
import os, sys
from os import path
from argparse import ArgumentParser, ArgumentTypeError
from urllib import urlretrieve
import operator

# local imports
from xy import XY
import splitimage

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

def findSedData(folders):
    for d in folders:
        # Mac install is at /path/appname.app/Contents/Resources/...
        if not sys.platform.startswith('win'):
            d = path.splitext(d)[0] + '.app'    # ensure .app terminated
            d = path.join(d, 'Contents', 'Resources')
        
        fname = path.join(d, 'res', 'en', 'sed_data.xml')
        if path.exists(fname):
            return fname
    
    return None

def getImageDir():
    base_dir = path.dirname(__file__)   # script directory
    return path.join(base_dir,'images')   # where we'll cache all images 
    
def findBgData():
    fname = path.join(getImageDir(),'bg_data.xml')
    return fname

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
    def getImage(self, imageDir, imageURL, orientation = 1):
        if not orientation: orientation = 1
        
        # check if we've already loaded it
        if not self.images.has_key(orientation):
            self.images[orientation] = None # assume the worst
            
            relpath = self.getRelativePath(orientation)
            fname = path.join(imageDir, relpath)
            # do we have a file?
            if not path.exists(fname):
                url = imageURL + relpath
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
    def __init__(self, xml_files, imageDir, imageURL):
        self.artworks = {}
        self.imageDir = imageDir
        self.imageURL = imageURL
        
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
        
        return self.artworks[name].getImage(self.imageDir, self.imageURL, orientation)
    
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
    dash_length = (36,9)                # black/white length in pixels
    dash_width = 7                      # pixels
    
    formats = {
        'standard' : XY(13,9),      # 2570 x 1737 px @ 90DPI = 28.6" x 19.3"
        'overlord' : XY(26,9),      # 5014 x 1737 px @ 90DPI = 55.7" x 19.3"
        'brkthru'  : XY(13,17)      # 2570 x 3039 px @ 90DPI = 28.6" x 33.8"
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
            'country' :     [['countryside']],
            'winter' :      [['snow']],
            'beach' :       [['countryside'],['beach'],['coast'],['ocean']],
            'desert' :      [['desert']]
            }   
                 
        names = faces[face]
        
        if face == 'beach':
            if format == 'brkthru':
                repeat = (11,3,1,2)
            else:
                repeat = (4,3,1,1)
        else:
            if format == 'brkthru':
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

    def render(self, icons, skipLayers = [], hexWidth = 2.0866):
        # create a blank empty board image with correct size and scaling (DPI)
        size = Board.marginXY * 2 + \
            Board.hexXY.doti( (self.cols, (self.rows*3+1)/4.) )
        board = Image.new('RGB', size, Board.background_color)
        canvas = ImageDraw.Draw(board)
        
        # use hexWidthto choose a particular hex width in inches
        # actual M44 tiles are 2.0866" (53mm) across the flats
        dpi = int(round(Board.hexXY.x / hexWidth))
        
        try:
            font = ImageFont.truetype('verdanab.ttf',32)
        except:
            print "Couldn't open VerdanaBold TTF, using (ugly) system default"
            font = ImageFont.load_default()
            
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

        # label the scenario
        canvas.text(Board.marginXY.doti( (1/2., 1/3.) ),
            self.text['name'], fill = 'black', font=font)
        
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
                            - wh.doti( (1/2., 1.1*(len(contents)/2. - i)) )
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
        board.info['dpi'] = (dpi,dpi)
        
        return board
        
def setupArgParser():
    
    # validate argument value containing comma-separated list of strings
    # from a fixed list
    def choiceList(choices = None):
        def checkList(value):
            values = value.split(',')
            for value in values:
                if value not in choices:
                    raise ArgumentTypeError( 
                        'invalid choice: %s (choose from %s)'%(
                            value, ', '.join(choices)))
            
            return values
        return checkList
     
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
    layer_opts = Board.drawing_layers + ['none']
    parser.add_argument('-x','--xlayers', 
        type=choiceList(choices = layer_opts),
        metavar=','.join(layer_opts),
        default=['obstacle','unit'],
        help="Comma-separated list of drawing layers to skip")
    
    parser = splitimage.setupArgParser(parser)
    
    return parser
    
########################################

if __name__ == "__main__":
    args = setupArgParser().parse_args()
    
    if args.appdir:
        if not path.exists(args.appdir) and not path.exists(args.appdir + '.app'):
            print "WARNING: Can't find specified appdir:",args.appdir
        else:
            if path.isfile(args.appdir):
                args.appdir = path.dirname(args.appdir)
            app_dirs = [args.appdir] + app_dirs
          
    sed_data_xml = findSedData(app_dirs)
    if not sed_data_xml:
        print "Can't find Memoir '44 Editor resource data, sorry"
        sys.exit(-1)
    
    if not path.exists(args.scenario_file):
        print "ERROR: Can't find scenario file %s"%args.scenario_file
        sys.exit(-1)
    
    # output to basename (excluding extension), based on scenario file if not given
    if not args.output_base:
        args.output_base = args.scenario_file
    args.output_base = path.splitext(args.output_base)[0]
        
    # read the foreground hex (and other tiles and counters) image dictionaries
    icons = ArtLibrary([sed_data_xml, findBgData()], getImageDir(), base_url)

    # create the board
    board = Board(args.scenario_file)
    # render the image
    image = board.render(icons, skipLayers=args.xlayers, hexWidth=args.hexwidth)
    # save the tiled versions
    splitimage.saveTiledImagesArgs(image, args.output_base, args)

