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
export async function exportVisibleSceneMeshes(scene, transformHelper) {
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

        if (isChildOf(object, transformHelper)) {
            return
        }
        //Exclude the voxel mesh visualization from future volume calculations.
        if (object.userData.excludeFromExport) {
            return
        }

        console.log('Exporting mesh:', object.name)
        //Properly send all transformations to the server.
        const geometry = object.geometry.clone()
        geometry.applyMatrix4(object.matrixWorld)

        const material = Array.isArray(object.material) ? object.material.map(material => material.clone()) : object.material.clone()

        const clone = new THREE.Mesh(geometry, material)
        clone.name = object.name
        exportScene.add(clone)
    })

    const exporter = new GLTFExporter()
    const arrayBuffer = await exporter.parseAsync(exportScene, {
        binary: true
    })

    return new Blob([arrayBuffer], {
        type: 'model/gltf-binary'
    })

    //Checks if an object (child) belongs to another object (parent):
    function isChildOf(object, parent) {
        let current = object

        while (current) {
            if (current === parent) {
                return true
            }

            current = current.parent
        }

        return false
    }
}