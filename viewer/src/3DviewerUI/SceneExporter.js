import * as THREE from 'three'
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js'

//Checks if an object and all its parents are visible:
function isVisibleInScene(object) {
    let current = object

    while (current) {
        if (!current.visible) {
            return false
        }

        current = current.parent
    }

    return true
}

//Checks if the object belongs to a voxel boundary:
function isVoxelBoundaryObject(object) {
    let current = object

    while (current) {
        if (current.isVoxelBoundary) {
            return true
        }

        current = current.parent
    }

    return false
}

//Exports all visible mesh objects into one GLB file:
export async function exportVisibleSceneMeshes(scene) {
    const exportScene = new THREE.Scene()

    scene.updateMatrixWorld(true)

    scene.traverse(object => {
        if (!object.isMesh) {
            return
        }

        if (!isVisibleInScene(object)) {
            return
        }

        if (isVoxelBoundaryObject(object)) {
            return
        }

        const clone = object.clone()
        clone.applyMatrix4(object.matrixWorld)

        exportScene.add(clone)
    })

    const exporter = new GLTFExporter()

    const arrayBuffer = await exporter.parseAsync(exportScene, {
        binary: true
    })

    return new Blob([arrayBuffer], {
        type: 'model/gltf-binary'
    })
}