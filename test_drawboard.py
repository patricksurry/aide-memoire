import unittest
from subprocess import check_call, CalledProcessError
from glob import glob
import os,sys
from os import path

import drawboard

def removeImages(basename):
    for filename in glob(basename + '*.png') :
        os.remove( filename ) 
    
class NullWriter:
    def write(self, s):
        pass

class NoOutput:
    def __enter__(self):
        self.old_stderr = sys.stderr
        self.old_stdout = sys.stdout
        sys.stderr = NullWriter()
        sys.stdout = NullWriter()

    def __exit__(self, type, value, traceback):
        sys.stderr = self.old_stderr
        sys.stdout = self.old_stdout
        
class BasicTests(unittest.TestCase):
    def testSedData(self):
        self.assertTrue(path.isfile(drawboard.findSedData(drawboard.app_dirs)))
    
    def testImageDir(self):
        self.assertTrue(path.isdir(drawboard.getImageDir()))
            
    def testBgData(self):
        self.assertTrue(path.isfile(drawboard.findBgData()))
        
    def testArtLibrary(self):
        self.assertTrue(drawboard.ArtLibrary(
            [ drawboard.findSedData(drawboard.app_dirs),
              drawboard.findBgData() ],
            drawboard.getImageDir(),
            drawboard.base_url))

class ArgsTests(unittest.TestCase):
    def testHelp(self):
        with NoOutput():
            self.assertRaises(SystemExit, drawboard.parseArgs, (['-h']))
        
    def testShortValid(self):
        self.assertTrue(drawboard.parseArgs([
            '-a','/some/dir',
            '-w','1.5',
            '-p','letter',
            '-m','0.5',
            '-o','0.25',
            '-x','terrain,lines,rect_terrain,obstacle,unit,tags,text',
            'scenario.m44',
            'outputbase.png'
        ]))
        
    def testLongValid(self):
        self.assertTrue(drawboard.parseArgs([
            'scenario.m44',
            'outputbase.png',
            '--appdir','/some/dir',
            '--hexwidth','1.5',
            '--pagesize','letter',
            '--margin','0.5',
            '--overlap','0.25',
            '--xlayers','terrain,lines,rect_terrain,obstacle,unit,tags,text'
        ]))      
        
    def testBadPageChoice(self):
        with NoOutput():
            self.assertRaises(SystemExit, drawboard.parseArgs,
                (['-p','weirdpaper']))
            
    def testBadXLayerChoice(self):
        with NoOutput():
            self.assertRaises(SystemExit, drawboard.parseArgs,
                (['-x','terrain,weirdlayer']))
            
    def testBadArg(self):
        with NoOutput():
            self.assertRaises(SystemExit, drawboard.parseArgs,(['--badarg']))
    
class CommandLineTests(unittest.TestCase):
    def runArgs(self, arglist, ok=True):
        arglist = ['python','drawboard.py'] + arglist
        if ok:
            self.assertTrue(check_call(arglist) == 0)
        else:
            self.assertRaises(CalledProcessError, check_call, arglist)
        
    def testSimple(self):
        self.runArgs(['juno.m44'])
        removeImages('juno')
        
    def testOnePage(self):
        self.runArgs(['juno.m44','-p','none'])
        removeImages('juno')
        
    def testAllLayers(self):
        self.runArgs(['juno.m44','-x','none'])
        removeImages('juno')
        
    def testXOption(self):
        self.runArgs(['-x','none','juno.m44'])
        removeImages('juno')
        
    def testMissingScenario(self):
        self.runArgs(['foobar'], False)
        

class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.icons = drawboard.ArtLibrary(
            [ drawboard.findSedData(drawboard.app_dirs),
              drawboard.findBgData() ],
            drawboard.getImageDir(),
            drawboard.base_url)
        if not path.isdir('testimages'):
            os.mkdir('testimages')
    
    def tryScenario(self, scenario):
        board = drawboard.Board(scenario)
        self.assertTrue(board)
        board.render(self.icons, skipLayers='none')
        outbase = path.join('testimages',
            path.splitext(path.basename(scenario))[0])
        board.save(outbase, drawboard.page_sizes['letter'], 0.5, 0.25)
        board.save(outbase, None, None, None)
        removeImages(outbase)
        
if __name__ == '__main__':
    # add tests for each scenario
    for i,scenario in enumerate(glob('scenarios/*.m44')):
        def doit(s): return lambda self: self.tryScenario(s)
        setattr(ScenarioTests, 'test%d'%i, doit(scenario))

    unittest.main()
