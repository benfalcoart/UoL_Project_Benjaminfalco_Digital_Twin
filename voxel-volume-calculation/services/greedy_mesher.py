class GreedyMesher:
    def build(self, voxels):
        positions = []
        indices = []

        voxelsByDepth = {}

        #Group voxels by subdivision depth:
        for voxel in voxels:
            voxelsByDepth.setdefault(voxel.depth, []).append(voxel)

        for depth, depthVoxels in sorted(voxelsByDepth.items()):
            print(f"Greedy meshing depth {depth}: {len(depthVoxels)} voxels")
            self.meshDepth(depthVoxels, positions, indices)

        return {
            "positions": positions,
            "indices": indices,
            "vertexCount": len(positions) // 3,
            "triangleCount": len(indices) // 3
        }

    #Generate the visible faces for one voxel depth:
    def meshDepth(self, voxels, positions, indices):
        if not voxels:
            return

        voxelSize = voxels[0].size
        lookup = {self.getVoxelGridKey(voxel) for voxel in voxels}
        planes = {}

        for x, y, z in lookup:
            #Positive X:
            if (x + 1, y, z) not in lookup:
                planes.setdefault(("x", 1, x + 1), set()).add((y, z))
            #Negative X:
            if (x - 1, y, z) not in lookup:
                planes.setdefault(("x", -1, x), set()).add((y, z))
            #Positive Y:
            if (x, y + 1, z) not in lookup:
                planes.setdefault(("y", 1, y + 1), set()).add((x, z))
            #Negative Y:
            if (x, y - 1, z) not in lookup:
                planes.setdefault(("y", -1, y), set()).add((x, z))
            #Positive Z:
            if (x, y, z + 1) not in lookup:
                planes.setdefault(("z", 1, z + 1), set()).add((x, y))
            #Negative Z:
            if (x, y, z - 1) not in lookup:
                planes.setdefault(("z", -1, z), set()).add((x, y))

        #Greedy merge the exposed cells on every plane:
        for (axis, direction, plane), cells in planes.items():
            self.meshPlane(axis, direction, plane, cells, voxelSize, positions, indices)

    #Greedy merge a 2D plane of voxel faces:
    def meshPlane(self, axis, direction, plane, cells, voxelSize, positions, indices):
        cells = set(cells)

        while cells:
            u, v = min(cells, key=lambda point: (point[1], point[0]))
            width = 1
            while (u + width, v) in cells:
                width += 1

            height = 1
            while True:
                nextV = v + height
                if all((currentU, nextV) in cells for currentU in range(u, u + width)):
                    height += 1
                else:
                    break

            for currentU in range(u, u + width):
                for currentV in range(v, v + height):
                    cells.remove((currentU, currentV))

            self.addQuad(axis, direction, plane, u, v, width, height, voxelSize, positions, indices)

    #Add one merged quad to the mesh:
    def addQuad(self, axis, direction, plane, u, v, width, height, voxelSize, positions, indices):
        planePosition = plane * voxelSize
        uMin = u * voxelSize
        uMax = (u + width) * voxelSize
        vMin = v * voxelSize
        vMax = (v + height) * voxelSize

        if axis == "x":
            if direction > 0:
                vertices = [
                    (planePosition, uMin, vMin),
                    (planePosition, uMax, vMin),
                    (planePosition, uMax, vMax),
                    (planePosition, uMin, vMax)
                ]
            else:
                vertices = [
                    (planePosition, uMin, vMin),
                    (planePosition, uMin, vMax),
                    (planePosition, uMax, vMax),
                    (planePosition, uMax, vMin)
                ]

        elif axis == "y":
            if direction > 0:
                vertices = [
                    (uMin, planePosition, vMin),
                    (uMin, planePosition, vMax),
                    (uMax, planePosition, vMax),
                    (uMax, planePosition, vMin)
                ]
            else:
                vertices = [
                    (uMin, planePosition, vMin),
                    (uMax, planePosition, vMin),
                    (uMax, planePosition, vMax),
                    (uMin, planePosition, vMax)
                ]

        else:
            if direction > 0:
                vertices = [
                    (uMin, vMin, planePosition),
                    (uMax, vMin, planePosition),
                    (uMax, vMax, planePosition),
                    (uMin, vMax, planePosition)
                ]
            else:
                vertices = [
                    (uMin, vMin, planePosition),
                    (uMin, vMax, planePosition),
                    (uMax, vMax, planePosition),
                    (uMax, vMin, planePosition)
                ]

        baseIndex = len(positions) // 3

        for vertex in vertices:
            positions.extend(vertex)

        indices.extend([
            baseIndex,
            baseIndex + 1,
            baseIndex + 2,
            baseIndex,
            baseIndex + 2,
            baseIndex + 3
        ])

    #Create an integer grid key for a voxel:
    def getVoxelGridKey(self, voxel):
        size = voxel.size
        halfSize = size / 2

        return (
            int(round((voxel.center[0] - halfSize) / size)),
            int(round((voxel.center[1] - halfSize) / size)),
            int(round((voxel.center[2] - halfSize) / size))
        )