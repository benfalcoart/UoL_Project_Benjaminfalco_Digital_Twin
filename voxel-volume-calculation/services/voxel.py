import numpy as np

class Voxel:
    def __init__(self, center, size, depth=0):
        #make it 64 bit just incase.
        self.center = np.asarray(center, dtype=np.float64)
        self.size = size
        self.depth = depth
        self.children = []
        self.blocked = False

    #Get the minimum corner:
    def getMin(self):
        return self.center - self.size / 2

    #Get the maximum corner:
    def getMax(self):
        return self.center + self.size / 2

    #Get the volume:
    def getVolume(self):
        return self.size ** 3

    #Split the voxel into eight child voxels:
    def split(self):
        childSize = self.size / 2
        offset = childSize / 2
        children = []

        for x in [-offset, offset]:
            for y in [-offset, offset]:
                for z in [-offset, offset]:
                    center = self.center + np.array([x, y, z])

                    children.append(Voxel(center, childSize, self.depth + 1))

        return children

    #Convert voxel data for the web viewer:
    def toDict(self):
        return {
            "center": self.center.tolist(),
            "size": self.size,
            "depth": self.depth
        }