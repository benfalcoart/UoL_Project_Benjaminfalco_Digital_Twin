import * as THREE from 'three'

//This class represents the voxel boundary tool to limit the flood of voxels. 
//Mainly this is to stop them at holes and gaps in the meshes.
//Represents an editable voxel flood boundary:
export class VoxelBoundary extends THREE.Group {
    //Create the boundary and its visual helpers:
    constructor({
        name = 'Voxel Boundary', width = 2, height = 2, depth = 2, position = new THREE.Vector3()} = {}) {
        super()

        this.name = name
        this.isVoxelBoundary = true

        this.min = new THREE.Vector3(
            -width / 2,
            -height / 2,
            -depth / 2
        )

        this.max = new THREE.Vector3(
            width / 2,
            height / 2,
            depth / 2
        )

        this.position.copy(position)

        this.boxMesh = null
        this.outline = null
        this.centerMarker = null
        
        this.faceHandles = []
        this.editMode = false
        this.selectedFace = null

        //Voxel grid on the boundary:
        this.gridVisible = true
        this.gridObjects = []

        this.minVoxelColor = 0x2255aa
        this.maxVoxelColor = 0x66ccff

        this.build()
        this.buildFaceHandles()
    }

    //Build the boundary box, outline, and center marker:
    build() {
        this.clearVisuals()

        const size = this.getSize()

        const geometry = new THREE.BoxGeometry(1, 1, 1)

        const material = new THREE.MeshBasicMaterial({
            color: 0x00ffff,
            transparent: true,
            opacity: 0.08,
            depthWrite: false
        })

        this.boxMesh = new THREE.Mesh(geometry, material)
        this.boxMesh.scale.copy(size)
        this.boxMesh.name = `${this.name} Volume`

        const edges = new THREE.EdgesGeometry(geometry)

        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x00ffff
        })

        this.outline = new THREE.LineSegments(edges, lineMaterial)

        this.outline.name = `${this.name} Outline`

        const centerGeometry = new THREE.SphereGeometry(0.05, 12, 12)

        const centerMaterial = new THREE.MeshBasicMaterial({
            color: 0xffff00
        })

        this.centerMarker = new THREE.Mesh(
            centerGeometry,
            centerMaterial
        )

        this.centerMarker.name = `${this.name} Center`

        this.add(this.boxMesh,this.outline,this.centerMarker)

        //this.updateVisualPosition()
        this.updateBoundaryVisuals()
    }

    //Update the box visuals to match the current bounds:
    updateBoundaryVisuals() {
        const size = this.getSize()
        const center = this.getLocalCenter()

        this.boxMesh.scale.copy(size)
        this.boxMesh.position.copy(center)

        this.outline.scale.copy(size)
        this.outline.position.copy(center)

        this.centerMarker.position.copy(center)
    }

    //Rebuild the editable face handles:
    refreshFaceHandles() {
        this.buildFaceHandles()

        if (this.editMode) {
            this.faceHandles.forEach(handle => {
                handle.visible = true
            })
        }
    }


    //Rebuild the world grid projected onto the boundary:
    updateGridProjection(worldGrid, opacity = 0.15, voxelBoundaryColor ='#00FFFF',  minColor = '#2255aa', maxColor = '#66ccff') {
        this.clearGridProjection()

        this.updateMatrixWorld(true)
        this.setOutlineColor(voxelBoundaryColor)
        this.buildGridProjection(worldGrid, worldGrid.minVoxelSize, minColor, opacity)
        this.buildGridProjection(worldGrid, worldGrid.maxVoxelSize, maxColor, opacity)
        this.setGridVisible(this.gridVisible)
    }

    //Build one projected voxel grid size on the boundary:
    buildGridProjection(worldGrid, voxelSize, color, opacity) {
        const faces = this.getBoundaryFaces()
        const vertices = []

        faces.forEach(face => {
            const worldCorners = face.corners.map(point => this.localToWorld(point.clone()))

            for (const axis of ['x', 'y', 'z']) {
                const values = worldCorners.map(point => point[axis])
                const min = Math.min(...values)
                const max = Math.max(...values)

                const gridPositions = worldGrid.getGridPositions(min, max, voxelSize, axis)

                gridPositions.forEach(position => {
                    const segment = this.intersectFaceWithPlane(worldCorners, axis, position)

                    if (!segment) {
                        return
                    }

                    const pointA = this.worldToLocal(segment[0].clone())
                    const pointB = this.worldToLocal(segment[1].clone())

                    const offset = face.normal.clone().multiplyScalar(0.002)

                    pointA.add(offset)
                    pointB.add(offset)

                    vertices.push(
                        pointA.x, pointA.y, pointA.z,
                        pointB.x, pointB.y, pointB.z
                    )
                })
            }
        })

        if (vertices.length === 0) {
            return
        }

        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))

        const material = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity,
            depthWrite: false
        })

        const grid = new THREE.LineSegments(geometry, material)

        this.gridObjects.push(grid)
        this.add(grid)
    }

    //Return the six faces that make up the boundary box:
    getBoundaryFaces() {
        const min = this.min
        const max = this.max

        return [
            {
                normal: new THREE.Vector3(-1, 0, 0),
                corners: [
                    new THREE.Vector3(min.x, min.y, min.z),
                    new THREE.Vector3(min.x, max.y, min.z),
                    new THREE.Vector3(min.x, max.y, max.z),
                    new THREE.Vector3(min.x, min.y, max.z)
                ]
            },
            {
                normal: new THREE.Vector3(1, 0, 0),
                corners: [
                    new THREE.Vector3(max.x, min.y, min.z),
                    new THREE.Vector3(max.x, min.y, max.z),
                    new THREE.Vector3(max.x, max.y, max.z),
                    new THREE.Vector3(max.x, max.y, min.z)
                ]
            },
            {
                normal: new THREE.Vector3(0, -1, 0),
                corners: [
                    new THREE.Vector3(min.x, min.y, min.z),
                    new THREE.Vector3(min.x, min.y, max.z),
                    new THREE.Vector3(max.x, min.y, max.z),
                    new THREE.Vector3(max.x, min.y, min.z)
                ]
            },
            {
                normal: new THREE.Vector3(0, 1, 0),
                corners: [
                    new THREE.Vector3(min.x, max.y, min.z),
                    new THREE.Vector3(max.x, max.y, min.z),
                    new THREE.Vector3(max.x, max.y, max.z),
                    new THREE.Vector3(min.x, max.y, max.z)
                ]
            },
            {
                normal: new THREE.Vector3(0, 0, -1),
                corners: [
                    new THREE.Vector3(min.x, min.y, min.z),
                    new THREE.Vector3(max.x, min.y, min.z),
                    new THREE.Vector3(max.x, max.y, min.z),
                    new THREE.Vector3(min.x, max.y, min.z)
                ]
            },
            {
                normal: new THREE.Vector3(0, 0, 1),
                corners: [
                    new THREE.Vector3(min.x, min.y, max.z),
                    new THREE.Vector3(min.x, max.y, max.z),
                    new THREE.Vector3(max.x, max.y, max.z),
                    new THREE.Vector3(max.x, min.y, max.z)
                ]
            }
        ]
    }

    //Find where a world grid plane crosses a boundary face:
    intersectFaceWithPlane(corners, axis, value) {
        const epsilon = 0.00001
        const points = []

        const allOnPlane = corners.every(point => Math.abs(point[axis] - value) < epsilon)

        if (allOnPlane) {
            return null
        }

        const edges = [
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0]
        ]

        edges.forEach(([a, b]) => {
            const start = corners[a]
            const end = corners[b]

            const startDistance = start[axis] - value
            const endDistance = end[axis] - value

            if (Math.abs(startDistance) < epsilon) {
                this.addUniquePoint(points, start)
            }

            if (Math.abs(endDistance) < epsilon) {
                this.addUniquePoint(points, end)
            }

            if (startDistance * endDistance < 0) {
                const t = (value - start[axis]) / (end[axis] - start[axis])
                const point = start.clone().lerp(end, t)

                this.addUniquePoint(points, point)
            }
        })

        if (points.length < 2) {
            return null
        }

        if (points.length === 2) {
            return points
        }

        return this.findFarthestPoints(points)
    }

    //Remove and dispose the boundary visuals:
    clearVisuals() {
        for (const child of [...this.children]) {
            child.geometry?.dispose()

            if (Array.isArray(child.material)) {
                child.material.forEach(material => material.dispose())
            }
            else {
                child.material?.dispose()
            }

            this.remove(child)
        }
    }    

    //Remove and dispose the projected voxel grid:
    clearGridProjection() {
        this.gridObjects.forEach(grid => {
            this.remove(grid)
            grid.geometry?.dispose()
            grid.material?.dispose()
        })

        this.gridObjects = []
    }

    //Add an intersection point if it is not already stored:
    addUniquePoint(points, point) {
        const duplicate = points.some(existing => existing.distanceToSquared(point) < 0.0000001)

        if (!duplicate) {
            points.push(point.clone())
        }
    }

    //Find the two points that form the longest line segment:
    findFarthestPoints(points) {
        let result = [points[0], points[1]]
        let longestDistance = 0

        for (let a = 0; a < points.length; a++) {
            for (let b = a + 1; b < points.length; b++) {
                const distance = points[a].distanceToSquared(points[b])

                if (distance > longestDistance) {
                    longestDistance = distance
                    result = [points[a], points[b]]
                }
            }
        }

        return result
    }

    //Show or hide the projected voxel grid:
    setGridVisible(visible) {
        this.gridVisible = visible

        this.gridObjects.forEach(grid => {
            grid.visible = visible
        })
    }

    //Get the current local size of the boundary:
    getSize() {
        return new THREE.Vector3().subVectors(
            this.max,
            this.min
        )
    }

    //Get the center of the boundary in local space:
    getLocalCenter() {
        return new THREE.Vector3()
            .addVectors(this.min, this.max)
            .multiplyScalar(0.5)
    }

    //Get the center of the boundary in world space:
    getWorldCenter() {
        return this.localToWorld(
            this.getLocalCenter()
        )
    }

    //Set the boundary outline color:
    setOutlineColor(color) {
        if (this.outline) {
            this.outline.material.color.set(color)
        }
    }

    //Replace the minimum and maximum boundary values:
    setBounds(min, max) {
        this.min.copy(min)
        this.max.copy(max)

        this.build()
    }

    //Move one side of the boundary along an axis:
    moveFace(axis, side, distance) {
        if (side === 'min') {
            this.min[axis] += distance
        }
        else {
            this.max[axis] += distance
        }

        this.build()
    }

    //Move the boundary visuals to the current local center:
    updateVisualPosition() {
        const center = this.getLocalCenter()

        if (this.boxMesh) {
            this.boxMesh.position.copy(center)
        }

        if (this.outline) {
            this.outline.position.copy(center)
        }

        if (this.centerMarker) {
            this.centerMarker.position.copy(center)
        }
    }

    //Build the six invisible handles used to edit the box:
    buildFaceHandles() {
        this.faceHandles.forEach(handle => {
            this.remove(handle)
            handle.geometry?.dispose()
            handle.material?.dispose()
        })

        this.faceHandles = []

        const size = this.getSize()
        const center = this.getLocalCenter()
        const thickness = 0.03

        const faces = [
            {
                axis: 'x',
                side: 'max',
                position: new THREE.Vector3(this.max.x, center.y, center.z),
                size: new THREE.Vector3(thickness, size.y, size.z)
            },
            {
                axis: 'x',
                side: 'min',
                position: new THREE.Vector3(this.min.x, center.y, center.z),
                size: new THREE.Vector3(thickness, size.y, size.z)
            },
            {
                axis: 'y',
                side: 'max',
                position: new THREE.Vector3(center.x, this.max.y, center.z),
                size: new THREE.Vector3(size.x, thickness, size.z)
            },
            {
                axis: 'y',
                side: 'min',
                position: new THREE.Vector3(center.x, this.min.y, center.z),
                size: new THREE.Vector3(size.x, thickness, size.z)
            },
            {
                axis: 'z',
                side: 'max',
                position: new THREE.Vector3(center.x, center.y, this.max.z),
                size: new THREE.Vector3(size.x, size.y, thickness)
            },
            {
                axis: 'z',
                side: 'min',
                position: new THREE.Vector3(center.x, center.y, this.min.z),
                size: new THREE.Vector3(size.x, size.y, thickness)
            }
        ]

        faces.forEach(face => {
            const geometry = new THREE.BoxGeometry(face.size.x, face.size.y, face.size.z)

            const material = new THREE.MeshBasicMaterial({
                color: 0xffaa00,
                transparent: true,
                opacity: 0,
                depthWrite: false
            })

            const handle = new THREE.Mesh(geometry, material)

            handle.position.copy(face.position)
            handle.userData.voxelFace = true
            handle.userData.axis = face.axis
            handle.userData.side = face.side
            handle.visible = this.editMode

            this.faceHandles.push(handle)
            this.add(handle)
        })
    }

    //Move the object pivot back to the center of the boundary:
    recenterPivot() {
        const center = this.getLocalCenter()

        if (center.lengthSq() === 0) {
            return
        }

        const worldOffset = center.clone()
        worldOffset.multiply(this.scale)
        worldOffset.applyQuaternion(this.quaternion)

        this.position.add(worldOffset)

        this.min.sub(center)
        this.max.sub(center)

        this.updateBoundaryVisuals()
        this.buildFaceHandles()
    }

    //Enable or disable boundary face editing:
    setEditMode(enabled) {
        this.editMode = enabled

        this.faceHandles.forEach(handle => {
            handle.visible = enabled
        })

        if (!enabled) {
            this.selectFace(null)
        }
    }

    //Highlight the currently selected face handle:
    selectFace(handle) {
        this.selectedFace = handle

        this.faceHandles.forEach(face => {
            face.material.opacity = face === handle ? 0.3 : 0
        })
    }

    

    //Convert the boundary data into a simple object:
    toJSON() {
        return {
            name: this.name,
            position: this.position.toArray(),
            quaternion: this.quaternion.toArray(),
            min: this.min.toArray(),
            max: this.max.toArray()
        }
    }
}

//Create a simple flat voxel grid:
export function createVoxelGrid(sizeA, sizeB, cellsA, cellsB, plane, color) {
        const vertices = []
    
        //Extents (half the dimensions of the grid so its centered arround the origin.):
        const extentsA = sizeA / 2
        const extentsB = sizeB / 2
    
        //The distance between each grid line along the two dimensions
        const stepA = sizeA / cellsA
        const stepB = sizeB / cellsB
    
        //Create a set of parallel grid lines:
        for (let i = 0; i <= cellsA; i++) {
            const a = -extentsA + i * stepA
    
            //Floor Grid
            if (plane === 'XZ') {
                vertices.push(
                    a, 0, -extentsB,
                    a, 0, extentsB
                )
            }
            //Back Grid
            else if (plane === 'XY') {
                vertices.push(
                    a, -extentsB, 0,
                    a, extentsB, 0
                )
            }
            //Side Grid
            else if (plane === 'YZ') {
                vertices.push(
                    0, -extentsB, a,
                    0, extentsB, a
                )
            }
        }
        ///Create a second set of parallel lines perpendicular to the first set above to form a grid.
        for (let i = 0; i <= cellsB; i++) {
            const b = -extentsB + i * stepB
    
            //Floor grid
            if (plane === 'XZ') {
                vertices.push(
                    -extentsA, 0, b,
                    extentsA, 0, b
                )
            }
            //Back grid
            else if (plane === 'XY') {
                vertices.push(
                    -extentsA, b, 0,
                    extentsA, b, 0
                )
            }
            //Side Grid.
            else if (plane === 'YZ') {
                vertices.push(
                    0, b, -extentsA,
                    0, b, extentsA
                )
            }
        }
        //Convert the generated Vertex positions into geo that three.js can render:
        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    
        //Material Used to render the lines. Use the passed in color:
        const material = new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity: 0.12,
            depthWrite: false
        })
    
        return new THREE.LineSegments(geometry, material);
    }