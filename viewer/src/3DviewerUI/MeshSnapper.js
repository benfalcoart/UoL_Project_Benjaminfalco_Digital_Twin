import * as THREE from 'three'
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh'

//Add BVH support to Three.js geometry and meshes:
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree
THREE.Mesh.prototype.raycast = acceleratedRaycast


export class MeshSnapper {
    constructor() {
        this.meshes = []
        this.raycaster = new THREE.Raycaster()

        //We only need the nearest surface from the caster:
        this.raycaster.firstHitOnly = true
    }

    //Register all meshes contained inside a loaded model:
    registerObject(object) {
        object.traverse(child => {
            if (!child.isMesh || !child.geometry) {
                return
            }
            //Build the BVH once:
            if (!child.geometry.boundsTree) {
                console.log(`Building snap BVH: ${child.name || 'Unnamed Mesh'}`)
                child.geometry.computeBoundsTree()
            }
            if (!this.meshes.includes(child)) {
                this.meshes.push(child)
            }
        })
        console.log(`MeshSnapper now contains ${this.meshes.length} meshes`)
    }

    //Remove a model from the snap targets:
    unregisterObject(object) {
        const removeMeshes = new Set()

        object.traverse(child => {
            if (child.isMesh) {
                removeMeshes.add(child)
            }
        })

        this.meshes = this.meshes.filter(mesh => !removeMeshes.has(mesh))
    }

    //Remove all current snap targets:
    clear() {
        this.meshes = []
    }

    //Find the nearest mesh surface along a world-space direction:
    findSurface(origin, direction, maxDistance = Infinity) {
        const snapDirection = direction.clone().normalize()

        //Move a tiny amount away from the starting point to avoid hitting the starting surface:
        const rayOrigin = origin.clone().addScaledVector(snapDirection, 0.00001)

        this.raycaster.set(rayOrigin, snapDirection)
        this.raycaster.near = 0
        this.raycaster.far = maxDistance

        const visibleMeshes = this.meshes.filter(mesh => this.isVisibleInScene(mesh))
        if (visibleMeshes.length === 0) {
            return null
        }

        const hits = this.raycaster.intersectObjects(visibleMeshes, false)
        if (hits.length === 0) {
            return null
        }

        return hits[0]
    }

    //Check the object and all parents for visibility:
    isVisibleInScene(object) {
        let current = object

        while (current) {
            if (!current.visible) {
                return false
            }
            current = current.parent
        }
        return true
    }
}