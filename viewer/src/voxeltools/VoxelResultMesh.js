import * as THREE from 'three'


export class VoxelResultMesh {
    constructor() {
        this.mesh = null
    }

    //Create a renderable mesh from voxel mesh data:
    create(meshData) {
        this.dispose()

        const geometry = new THREE.BufferGeometry()

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(meshData.positions, 3))
        geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(meshData.indices), 1))

        geometry.computeVertexNormals()
        geometry.computeBoundingBox()
        geometry.computeBoundingSphere()

        const material = new THREE.MeshStandardMaterial({
            color: 0x44cc88,
            roughness: 0.8,
            metalness: 0,
            opacity: 0.65,
            side: THREE.DoubleSide
        })

        this.mesh = new THREE.Mesh(geometry, material)
        this.mesh.name = 'Calculated Voxel Volume'

        //Do not send the calculated result back to Python on the next calculation:
        this.mesh.userData.excludeFromExport = true

        return this.mesh
    }

    //Remove the previous calculated mesh:
    dispose() {
        if (!this.mesh) {
            return
        }

        this.mesh.removeFromParent()
        this.mesh.geometry.dispose()
        this.mesh.material.dispose()
        this.mesh = null
    }
}