import * as THREE from 'three'

//This class represents the voxel boundary tool to limit the flood of voxels. 
//Mainly this is to stop them at holes and gaps in the meshes.
export class VoxelBoundary extends THREE.Group {
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

        this.build()
    }

    build() {
        this.clearVisuals()

        const size = this.getSize()

        const geometry = new THREE.BoxGeometry(
            size.x,
            size.y,
            size.z
        )

        const material = new THREE.MeshBasicMaterial({
            color: 0x00ffff,
            transparent: true,
            opacity: 0.08,
            depthWrite: false
        })

        this.boxMesh = new THREE.Mesh(geometry, material)
        this.boxMesh.name = `${this.name} Volume`

        const edges = new THREE.EdgesGeometry(geometry)

        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x00ffff
        })

        this.outline = new THREE.LineSegments(
            edges,
            lineMaterial
        )

        this.outline.name = `${this.name} Outline`

        const centerGeometry = new THREE.SphereGeometry(
            0.05,
            12,
            12
        )

        const centerMaterial = new THREE.MeshBasicMaterial({
            color: 0xffff00
        })

        this.centerMarker = new THREE.Mesh(
            centerGeometry,
            centerMaterial
        )

        this.centerMarker.name = `${this.name} Center`

        this.add(
            this.boxMesh,
            this.outline,
            this.centerMarker
        )

        this.updateVisualPosition()
    }

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

    getSize() {
        return new THREE.Vector3().subVectors(
            this.max,
            this.min
        )
    }

    getLocalCenter() {
        return new THREE.Vector3()
            .addVectors(this.min, this.max)
            .multiplyScalar(0.5)
    }

    getWorldCenter() {
        return this.localToWorld(
            this.getLocalCenter()
        )
    }

    setBounds(min, max) {
        this.min.copy(min)
        this.max.copy(max)

        this.build()
    }

    moveFace(axis, side, distance) {
        if (side === 'min') {
            this.min[axis] += distance
        }
        else {
            this.max[axis] += distance
        }

        this.build()
    }

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