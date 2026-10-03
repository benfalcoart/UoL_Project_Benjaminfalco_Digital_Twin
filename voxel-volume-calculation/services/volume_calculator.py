from pathlib import Path
import numpy as np
import trimesh


class VolumeCalculator:
    def calculate(self, meshPath: Path, boundaryData: dict):
        mesh = self.loadMesh(meshPath)
        voxelSettings = boundaryData.get("voxelSettings", {})

        maxVoxelSize = float(voxelSettings.get("maxVoxelSize", 0.1))
        subdivisionDepth = int(voxelSettings.get("subdivisionDepth", 0))

        #valdiate the the info from the viewer.
        if subdivisionDepth < 0:
            raise ValueError("Subdivision depth cannot be negative")

        if subdivisionDepth > 10:
            raise ValueError("Subdivision depth is too large")

        minVoxelSize = maxVoxelSize / (2 ** subdivisionDepth)

        boundaries = boundaryData.get("boundaries", [])

        #Print the data we received to calculate volume:
        print(f"Vertices: {len(mesh.vertices)}")
        print(f"Triangles: {len(mesh.faces)}")
        print(f"Boundaries: {len(boundaries)}")
        print(f"Max Voxel Size: {maxVoxelSize}")
        print(f"Subdivision Depth: {subdivisionDepth}")
        print(f"Min Voxel Size: {minVoxelSize}")

        return {
            "status": "mesh loaded",
            "vertices": len(mesh.vertices),
            "triangles": len(mesh.faces),
            "boundaryCount": len(boundaries),
            "maxVoxelSize": maxVoxelSize,
            "subdivisionDepth": subdivisionDepth,
            "minVoxelSize": minVoxelSize
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