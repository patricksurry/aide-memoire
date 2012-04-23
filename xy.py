class XY(tuple):
    def __new__(cls,x,y):
        return tuple.__new__(cls,(x,y))
       
    @property
    def x(self):
        return self[0]
        
    @property
    def y(self):
        return self[1]
        
    def swap(self):
        return XY(self.y,self.x)

    def dot(self, (x,y)):
        return XY(self.x * x, self.y * y)
        
    def doti(self, xy):
        return self.dot(xy).ints()
        
    def ints(self):
        return XY(int(self.x), int(self.y))
        
    def __neg__(self):
        return XY(- self.x, - self.y)
        
    def __add__(self, (x,y)):
        return XY(self.x + x, self.y + y)
        
    def __sub__(self, (x,y)):
        return XY(self.x - x, self.y - y)
        
    def __mul__(self, factor):
        return XY(self.x * factor, self.y * factor)
    
    def __div__(self, factor):
        return XY(self.x / factor, self.y / factor)
        
if __name__ == '__main__':
    xy1 = XY(3., 2)
    xy2 = XY(5., 7)
    
    print 'xy1 =', xy1, 'xy2 =', xy2
    print 'xy1 + xy2 =', xy1 + xy2
    print 'xy1 - xy2 =', xy1 - xy2
    print '-xy1 =', -xy1
    print 'xy1 * 3 =', xy1 * 3
    print 'xy1 / 3 =', xy1 / 3
    print 'xy1 + (1,1) =', xy1 + (1,1)
    
    
