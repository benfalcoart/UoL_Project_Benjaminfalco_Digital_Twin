from pathlib import Path
import numpy as np
import trimesh
from services.voxel import Voxel
from services.mesh_collision import MeshCollision
from services.greedy_mesher import GreedyMesher
from collections import deque


class VolumeCalculator:
    def calculate(self, meshPath: Path, boundaryData: dict):
        mesh = self.loadMesh(meshPath)
        voxelSettings = boundaryData.get("voxelSettings", {})
        print(voxelSettings)
        maxVoxelSize = float(voxelSettings.get("maxVoxelSize", 0.1))
        subdivisionDepth = int(voxelSettings.get("subdivisionDepth", 3))
        boundaries = boundaryData.get("boundaries", [])
        collision = MeshCollision(mesh)

        resultVoxels = []

        for boundary in boundaries:
            print(f"Processing the boundary: {boundary['name']}")

            leaves = self.buildAdaptiveVoxels(boundary, collision, maxVoxelSize, subdivisionDepth)
            freeVoxels = [voxel for voxel in leaves if not voxel.blocked]

            print(f"Free voxels before flooding: {len(freeVoxels)}")

            floodedVoxels = self.floodFillVoxels(freeVoxels, boundary, maxVoxelSize)

            print(f"Flooded voxels: {len(floodedVoxels)}")

            resultVoxels.extend(floodedVoxels)

        volume = sum(voxel.getVolume() for voxel in resultVoxels)

        print(f"Generated voxels: {len(resultVoxels)}")
        print(f"Preliminary volume: {volume}")

        mesher = GreedyMesher()
        meshData = mesher.build(resultVoxels)

        print(f"Greedy mesh vertices: {meshData['vertexCount']}")
        print(f"Greedy mesh triangles: {meshData['triangleCount']}")

        return {
            "status": "voxelized",
            "volume": volume,
            "voxelCount": len(resultVoxels),
            "mesh": meshData
        }

    #Load the uploaded mesh:
    def loadMesh(self, meshPath: Path):
        loaded = trimesh.load(meshPath)

        if isinstance(loaded, trimesh.Scene):
            print("Meshes received:")

            for name, geometry in loaded.geometry.items():
                print(f"- {name}")

            meshes = []

            for geometry in loaded.geometry.values():
                if isinstance(geometry, trimesh.Trimesh):
                    meshes.append(geometry)

            if not meshes:
                raise ValueError("No mesh geometry found in uploaded GLB")

            loaded = trimesh.util.concatenate(meshes)

        if not isinstance(loaded, trimesh.Trimesh):
            raise ValueError("Uploaded file did not contain a valid triangle mesh")

        loaded.remove_unreferenced_vertices()

        return loaded

    #Build adaptive voxels using batch collision tests:
    def subdivideVoxels(self, rootVoxels, collision, subdivisionDepth):
        currentVoxels = rootVoxels
        finishedVoxels = []
        for depth in range(subdivisionDepth + 1):
            print(f"Processing depth {depth}: {len(currentVoxels)} voxels")
            collisions = collision.intersectsVoxels(currentVoxels)
            nextVoxels = []
            for voxel, intersects in zip(currentVoxels, collisions):
                if not intersects:
                    finishedVoxels.append(voxel)
                    continue
                if voxel.depth >= subdivisionDepth:
                    voxel.blocked = True
                    finishedVoxels.append(voxel)
                    continue
                nextVoxels.extend(voxel.split())
            currentVoxels = nextVoxels
            if not currentVoxels:
                break
        return finishedVoxels

    #Build an adaptive voxel map inside a boundary:
    def buildAdaptiveVoxels(self, boundary, collision, maxVoxelSize, subdivisionDepth):
        rootVoxels = self.createRootVoxels(boundary, maxVoxelSize)
        print(f"Root voxels: {len(rootVoxels)}")
        return self.subdivideVoxels(rootVoxels, collision, subdivisionDepth)

    #Convert a quaternion into a rotation matrix:
    #adapted from: https://stackoverflow.com/questions/1556260/convert-quaternion-rotation-to-rotation-matrix
    def quaternionToMatrix(self, quaternion):
        x, y, z, w = quaternion

        return np.array([
            [
                1 - 2 * (y * y + z * z),
                2 * (x * y - z * w),
                2 * (x * z + y * w)
            ],
            [
                2 * (x * y + z * w),
                1 - 2 * (x * x + z * z),
                2 * (y * z - x * w)
            ],
            [
                2 * (x * z - y * w),
                2 * (y * z + x * w),
                1 - 2 * (x * x + y * y)
            ]
        ])

    #Check if a world-space point is inside a voxel boundary:
    def pointInsideBoundary(self, point, boundary):
        position = np.asarray(boundary["position"], dtype=np.float64)
        minimum = np.asarray(boundary["min"], dtype=np.float64)
        maximum = np.asarray(boundary["max"], dtype=np.float64)

        rotation = self.quaternionToMatrix(boundary["quaternion"])
        localPoint = rotation.T @ (point - position)
        return np.all(localPoint >= minimum) and np.all(localPoint <= maximum)

    #Find the world-space centre of a boundary:
    def getBoundaryCenter(self, boundary):
        position = np.asarray(boundary["position"], dtype=np.float64)
        minimum = np.asarray(boundary["min"], dtype=np.float64)
        maximum = np.asarray(boundary["max"], dtype=np.float64)

        localCenter = (minimum + maximum) / 2
        rotation = self.quaternionToMatrix(boundary["quaternion"])
        return position + rotation @ localCenter

    #Get the world-space corners of a given boundary:
    def getBoundaryWorldCorners(self, boundary):
        position = np.asarray(boundary["position"], dtype=np.float64)
        minimum = np.asarray(boundary["min"], dtype=np.float64)
        maximum = np.asarray(boundary["max"], dtype=np.float64)
        rotation = self.quaternionToMatrix(boundary["quaternion"])

        corners = []

        for x in [minimum[0], maximum[0]]:
            for y in [minimum[1], maximum[1]]:
                for z in [minimum[2], maximum[2]]:
                    local = np.array([x, y, z])
                    corners.append(position + rotation @ local)

        return np.asarray(corners)

    #Create the maximum-size world-grid voxels covering a boundary:
    def createRootVoxels(self, boundary, voxelSize):
        corners = self.getBoundaryWorldCorners(boundary)

        worldMin = corners.min(axis=0)
        worldMax = corners.max(axis=0)

        start = np.floor(worldMin / voxelSize).astype(int)
        end = np.ceil(worldMax / voxelSize).astype(int)

        voxels = []

        for x in range(start[0], end[0] + 1):
            for y in range(start[1], end[1] + 1):
                for z in range(start[2], end[2] + 1):
                    center = np.array([
                        (x + 0.5) * voxelSize,
                        (y + 0.5) * voxelSize,
                        (z + 0.5) * voxelSize
                    ])

                    if self.pointInsideBoundary(center, boundary):
                        voxels.append(Voxel(center, voxelSize, 0))

        return voxels

    #Extract voxels that have at least one exposed face.
    #This is needed to generate the voxel mesh in Three.js. We only want to get the surface not the entire voxel structure.
    def extractSurfaceVoxels(self, voxels):
        surfaceVoxels = []

        #Group voxels by depth so same-sized neighbors are fast to find:
        voxelsByDepth = {}

        for voxel in voxels:
            voxelsByDepth.setdefault(voxel.depth, []).append(voxel)

        #Create lookup tables for each depth:
        lookups = {}

        for depth, depthVoxels in voxelsByDepth.items():
            lookup = {}

            for voxel in depthVoxels:
                key = self.getVoxelGridKey(voxel)
                lookup[key] = voxel

            lookups[depth] = lookup

        for voxel in voxels:
            if self.voxelHasExposedFace(voxel, lookups):
                surfaceVoxels.append(voxel)

        return surfaceVoxels

    #Create an integer grid key for a voxel:
    def getVoxelGridKey(self, voxel):
        size = voxel.size

        return (round(voxel.center[0] / size), round(voxel.center[1] / size), round(voxel.center[2] / size))

    #Check if a voxel has at least one exposed face:
    def voxelHasExposedFace(self, voxel, lookups):
        lookup = lookups.get(voxel.depth, {})
        key = self.getVoxelGridKey(voxel)

        directions = [
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1)
        ]

        for direction in directions:
            neighborKey = (key[0] + direction[0], key[1] + direction[1], key[2] + direction[2])

            if neighborKey not in lookup:
                return True

        return False

    #Create a hierarchical grid key for an adaptive voxel:
    def getVoxelTreeKey(self, voxel):
        size = voxel.size
        halfSize = size / 2

        x = int(round((voxel.center[0] - halfSize) / size))
        y = int(round((voxel.center[1] - halfSize) / size))
        z = int(round((voxel.center[2] - halfSize) / size))

        return (voxel.depth, x, y, z)

    #Build lookup tables for the adaptive voxel hierarchy:
    def buildVoxelLookup(self, voxels):
        leafLookup = {}
        nodeKeys = set()

        for voxel in voxels:
            depth, x, y, z = self.getVoxelTreeKey(voxel)
            leafLookup[(depth, x, y, z)] = voxel

            currentDepth = depth
            currentX = x
            currentY = y
            currentZ = z

            while True:
                nodeKeys.add((currentDepth, currentX, currentY, currentZ))

                if currentDepth == 0:
                    break

                currentX //= 2
                currentY //= 2
                currentZ //= 2
                currentDepth -= 1

        return leafLookup, nodeKeys

    #Find a leaf voxel that contains a given hierarchical cell:
    def findCoveringLeaf(self, depth, x, y, z, leafLookup):
        currentDepth = depth
        currentX = x
        currentY = y
        currentZ = z

        while True:
            key = (currentDepth, currentX, currentY, currentZ)

            if key in leafLookup:
                return leafLookup[key]

            if currentDepth == 0:
                break

            currentX //= 2
            currentY //= 2
            currentZ //= 2
            currentDepth -= 1

        return None

    #Collect smaller leaf voxels touching one face of a hierarchical cell:
    def collectFaceLeaves(self, depth, x, y, z, axis, direction, leafLookup, nodeKeys):
        key = (depth, x, y, z)

        if key in leafLookup:
            return [leafLookup[key]]

        if key not in nodeKeys:
            return []

        touchingSide = 0 if direction > 0 else 1
        neighbors = []

        for a in [0, 1]:
            for b in [0, 1]:
                if axis == 0:
                    childX = x * 2 + touchingSide
                    childY = y * 2 + a
                    childZ = z * 2 + b
                elif axis == 1:
                    childX = x * 2 + a
                    childY = y * 2 + touchingSide
                    childZ = z * 2 + b
                else:
                    childX = x * 2 + a
                    childY = y * 2 + b
                    childZ = z * 2 + touchingSide

                neighbors.extend(self.collectFaceLeaves(depth + 1, childX, childY, childZ, axis, direction, leafLookup, nodeKeys))

        return neighbors

    #Find all free voxels sharing a face with a voxel:
    def getVoxelNeighbors(self, voxel, leafLookup, nodeKeys):
        depth, x, y, z = self.getVoxelTreeKey(voxel)

        directions = [
            (0, 1),
            (0, -1),
            (1, 1),
            (1, -1),
            (2, 1),
            (2, -1)
        ]

        for axis, direction in directions:
            neighborX = x
            neighborY = y
            neighborZ = z

            if axis == 0:
                neighborX += direction
            elif axis == 1:
                neighborY += direction
            else:
                neighborZ += direction

            #Check for a same-size or larger neighboring leaf:
            neighbor = self.findCoveringLeaf(depth, neighborX, neighborY, neighborZ, leafLookup)

            if neighbor is not None:
                yield neighbor
                continue

            #Check for smaller neighboring leaves:
            smallerNeighbors = self.collectFaceLeaves(depth, neighborX, neighborY, neighborZ, axis, direction, leafLookup, nodeKeys)

            for smallerNeighbor in smallerNeighbors:
                yield smallerNeighbor

    #Find the free voxel containing or nearest to the boundary centre:
    def findFloodSeed(self, voxels, boundary, maxVoxelSize, leafLookup):
        center = self.getBoundaryCenter(boundary)

        depths = sorted({voxel.depth for voxel in voxels})

        #First try to find the leaf that directly contains the centre:
        for depth in depths:
            size = maxVoxelSize / (2 ** depth)

            x = int(np.floor(center[0] / size))
            y = int(np.floor(center[1] / size))
            z = int(np.floor(center[2] / size))

            voxel = leafLookup.get((depth, x, y, z))

            if voxel is not None:
                return voxel

        #If the centre lies inside a blocked surface voxel, use the nearest free voxel:
        centers = np.asarray([voxel.center for voxel in voxels], dtype=np.float32)
        center = np.asarray(center, dtype=np.float32)

        distances = np.sum((centers - center) ** 2, axis=1)
        nearestIndex = int(np.argmin(distances))

        return voxels[nearestIndex]

    #Flood through all free voxels connected to the boundary centre:
    def floodFillVoxels(self, voxels, boundary, maxVoxelSize):
        if not voxels:
            return []

        print("Building adaptive voxel lookup...")
        leafLookup, nodeKeys = self.buildVoxelLookup(voxels)
        print("Finding flood seed...")
        seed = self.findFloodSeed(voxels, boundary, maxVoxelSize, leafLookup)
        print(f"Flood seed: {seed.center}, depth {seed.depth}, size {seed.size}")

        queue = deque([seed])
        visited = {self.getVoxelTreeKey(seed)}
        flooded = []

        while queue:
            voxel = queue.popleft()
            flooded.append(voxel)

            for neighbor in self.getVoxelNeighbors(voxel, leafLookup, nodeKeys):
                key = self.getVoxelTreeKey(neighbor)
                if key in visited:
                    continue

                visited.add(key)
                queue.append(neighbor)

            if len(flooded) % 100000 == 0:
                print(f"Flooded {len(flooded)} voxels...")

        return flooded