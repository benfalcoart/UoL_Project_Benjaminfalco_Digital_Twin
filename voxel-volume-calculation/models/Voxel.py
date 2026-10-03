class Voxel:
    def __init__(self, center, size, depth=0):
        self.center = center
        self.size = size
        self.depth = depth
        self.children = []
    #Split the voxel into eight smaller voxels:
    def split(self):
        childSize = self.size / 2
        offset = childSize / 2
        children = []

        for x in [-offset, offset]:
            for y in [-offset, offset]:
                for z in [-offset, offset]:
                    children.append(
                        Voxel(
                            self.center + np.array([x, y, z]),
                            childSize,
                            self.depth + 1
                        )
                    )

        return children