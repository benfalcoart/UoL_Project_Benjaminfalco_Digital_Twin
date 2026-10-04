import numpy as np
import torch


class MeshCollision:
    def __init__(self, mesh):
        self.mesh = mesh
        self.triangles = np.asarray(mesh.triangles, dtype=np.float32)
        self.useCuda = torch.cuda.is_available()
        self.device = torch.device("cuda" if self.useCuda else "cpu")

        if self.useCuda:
            print(f"Using CUDA voxel collision: {torch.cuda.get_device_name(0)}")
            self.trianglesCuda = torch.from_numpy(self.triangles).to(self.device)
        else:
            print("Using CPU voxel collision")
            self.trianglesCuda = None

        #Build the triangle spatial index:
        self.tree = mesh.triangles_tree

        print("Triangle spatial index built")

    #Find triangle candidates that overlap a voxel.
    #This is badly needed so we dont have to loop through trillions of voxel/tri collisions:
    def getCandidateTriangles(self, voxel):
        voxelMin = voxel.getMin()
        voxelMax = voxel.getMax()

        bounds = (voxelMin[0], voxelMin[1], voxelMin[2], voxelMax[0], voxelMax[1], voxelMax[2])

        return list(self.tree.intersection(bounds))

    #Check if a triangle ACTUALLY intersects a voxel:
    def triangleIntersectsVoxel(self, triangle, voxel):
        boxCenter = voxel.center
        boxHalfSize = np.array([voxel.size / 2] * 3)

        vertices = triangle - boxCenter

        edges = [
            vertices[1] - vertices[0],
            vertices[2] - vertices[1],
            vertices[0] - vertices[2]
        ]

        axes = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0])
        ]

        triangleNormal = np.cross(edges[0], edges[1])
        testAxes = axes + [triangleNormal]

        for edge in edges:
            for axis in axes:
                crossAxis = np.cross(edge, axis)

                if np.dot(crossAxis, crossAxis) > 1e-12:
                    testAxes.append(crossAxis)

        for axis in testAxes:
            if np.dot(axis, axis) < 1e-12:
                continue

            projections = vertices @ axis
            triangleMin = projections.min()
            triangleMax = projections.max()

            radius = boxHalfSize[0] * abs(axis[0]) + boxHalfSize[1] * abs(axis[1]) + boxHalfSize[2] * abs(axis[2])

            if triangleMin > radius or triangleMax < -radius:
                return False

        return True

    #Check a batch of triangle/voxel pairs on CUDA:
    def triangleVoxelBatchCuda(self, triangles, centers, sizes):
        vertices = triangles - centers[:, None, :]

        edge0 = vertices[:, 1] - vertices[:, 0]
        edge1 = vertices[:, 2] - vertices[:, 1]
        edge2 = vertices[:, 0] - vertices[:, 2]

        edges = torch.stack([edge0, edge1, edge2], dim=1)
        pairCount = triangles.shape[0]

        boxAxes = torch.eye(3, dtype=torch.float32, device=self.device).unsqueeze(0).expand(pairCount, -1, -1)
        triangleNormal = torch.cross(edge0, edge1, dim=1).unsqueeze(1)

        expandedEdges = edges[:, :, None, :].expand(-1, -1, 3, -1)
        expandedAxes = boxAxes[:, None, :, :].expand(-1, 3, -1, -1)
        crossAxes = torch.cross(expandedEdges, expandedAxes, dim=3).reshape(pairCount, 9, 3)

        testAxes = torch.cat([boxAxes, triangleNormal, crossAxes], dim=1)

        axisLengthSquared = torch.sum(testAxes * testAxes, dim=2)
        validAxes = axisLengthSquared > 1e-12

        projections = torch.einsum('pvc,pac->pva', vertices, testAxes)
        triangleMin = projections.min(dim=1).values
        triangleMax = projections.max(dim=1).values

        halfSize = sizes / 2
        radius = torch.abs(testAxes[:, :, 0]) * halfSize[:, None] + torch.abs(testAxes[:, :, 1]) * halfSize[:, None] + torch.abs(testAxes[:, :, 2]) * halfSize[:, None]

        separated = (triangleMin > radius) | (triangleMax < -radius)
        separated &= validAxes

        return ~torch.any(separated, dim=1)

    #Check many voxels against the mesh:
    def intersectsVoxels(self, voxels):
        if not voxels:
            return np.zeros(0, dtype=bool)

        if not self.useCuda:
            return np.array([self.intersectsVoxel(voxel) for voxel in voxels], dtype=bool)

        voxelIndices = []
        triangleIndices = []

        #Use the CPU spatial index to find candidate triangle pairs:
        for voxelIndex, voxel in enumerate(voxels):
            candidates = self.getCandidateTriangles(voxel)

            for triangleIndex in candidates:
                voxelIndices.append(voxelIndex)
                triangleIndices.append(triangleIndex)

        results = np.zeros(len(voxels), dtype=bool)

        if not triangleIndices:
            return results

        centers = np.asarray([voxel.center for voxel in voxels], dtype=np.float32)
        sizes = np.asarray([voxel.size for voxel in voxels], dtype=np.float32)

        voxelIndices = np.asarray(voxelIndices, dtype=np.int64)
        triangleIndices = np.asarray(triangleIndices, dtype=np.int64)

        #Process collision pairs in batches to limit GPU memory usage:
        batchSize = 250000

        for start in range(0, len(triangleIndices), batchSize):
            end = min(start + batchSize, len(triangleIndices))

            batchVoxelIndices = voxelIndices[start:end]
            batchTriangleIndices = triangleIndices[start:end]

            triangleTensor = self.trianglesCuda[torch.from_numpy(batchTriangleIndices).to(self.device)]
            centerTensor = torch.from_numpy(centers[batchVoxelIndices]).to(self.device)
            sizeTensor = torch.from_numpy(sizes[batchVoxelIndices]).to(self.device)

            collisions = self.triangleVoxelBatchCuda(triangleTensor, centerTensor, sizeTensor).cpu().numpy()

            np.logical_or.at(results, batchVoxelIndices, collisions)

        return results

    #Check if a voxel intersects any mesh surface:
    def intersectsVoxel(self, voxel):
        candidates = self.getCandidateTriangles(voxel)

        for triangleIndex in candidates:
            triangle = self.triangles[triangleIndex]

            if self.triangleIntersectsVoxel(triangle, voxel):
                return True

        return False