import './style.css'
import * as THREE from 'three'

import { createScene } from './3DviewerUI/SceneSetup.js'
import { MeshLoader } from './3DviewerUI/MeshLoader.js'
import { SceneExplorer } from './3DviewerUI/SceneExplorer.js'
import { TransformHistory } from './3DviewerUI/TransformHistory.js'
import { exportVisibleSceneMeshes } from './3DviewerUI/SceneExporter.js'
import { MeshSnapper } from './3DviewerUI/MeshSnapper.js'
import { ReconstructionLibrary } from './3DviewerUI/ReconstructionLibrary.js'

import { VoxelBoundary } from './voxeltools/VoxelBoundary.js'
import { WorldVoxelGrid } from './voxeltools/WorldVoxelGrid.js'
import { VoxelBoundaryEditor } from './voxeltools/VoxelBoundaryEditor.js'
import { VoxelControls } from './voxeltools/VoxelControls.js'
import { exportVoxelBoundaries } from './voxeltools/VoxelBoundaryExporter.js'
import { VoxelResultMesh } from './voxeltools/VoxelResultMesh.js'

import { MLControls } from './machinelearning/MLControls.js'



//Create the main Three.js scene:
const {
    scene,
    camera,
    renderer,
    controls,
    transformControls,
    transformHelper
} = createScene(document.querySelector('#app'))

//UI:
const loadMeshButton = document.querySelector('#loadMeshButton')
const meshFileInput = document.querySelector('#meshFileInput')
const addVoxelBoundaryButton = document.querySelector('#addVoxelBoundaryButton')

//Track the currently selected object:
let selectedObject = null

//Voxelation:
let voxelBoundaryCount = 0
let boundaryEditor = null

//Create the editor helper systems:
const transformHistory = new TransformHistory()
const voxelControls = new VoxelControls(null, calculateApproxVolume)
const meshSnapper = new MeshSnapper() //This will be used by the boundaries to make it easier/faster to place them.
const initialVoxelSettings = voxelControls.getSettings()
const voxelResultMesh = new VoxelResultMesh()

//Voxel calculation results:
const voxelStatus = document.querySelector('#voxelCalculationStatus')
const voxelVolume = document.querySelector('#voxelVolume')
const voxelInverseVolume = document.querySelector('#voxelInverseVolume')
const voxelBoundaryVolume = document.querySelector('#voxelBoundaryVolume')
const voxelCount = document.querySelector('#voxelCount')
const voxelTriangles = document.querySelector('#voxelTriangles')

//Voxel Grid visualizer:
const voxelGridOrigin = new THREE.Vector3(0, 0, 0)
const worldVoxelGrid = new WorldVoxelGrid(voxelGridOrigin, initialVoxelSettings.minVoxelSize, initialVoxelSettings.maxVoxelSize)

//Create the scene explorer:
const sceneExplorer = new SceneExplorer(
    scene,
    document.querySelector('#sceneTree'),
    transformHelper,
    selectObject,
    deleteSceneObject,
    onObjectLockChanged
)

//Create the model loader:
const meshLoader = new MeshLoader(scene, loadMeshButton, meshFileInput, (loadedObject) => {
    meshSnapper.registerObject(loadedObject)
    sceneExplorer.refresh()
})

//Create the Reconstruction Library:
let mlControls = null

const reconstructionLibrary = new ReconstructionLibrary(scene, loadedGroup => {
        meshSnapper.registerObject(loadedGroup)
        sceneExplorer.refresh()
    }, () => mlControls?.refresh(),
    removedGroup => {
        deselectObject()
        meshSnapper.unregisterObject(removedGroup)
    }
)

//Initialize the Machine Learning UI:
mlControls = new MLControls(reconstructionLibrary, {
    onModelSelected: fitCameraToObject
})

//Tools tabs:
const voxelTabButton = document.querySelector('#voxelTabButton')
const mlTabButton = document.querySelector('#mlTabButton')

const voxelPane = document.querySelector('#voxelControls')
const mlPane = document.querySelector('#mlControls')

//Switch between the two Tools panels:
function activateTab(active) {
    const voxels = active === 'voxel'

    voxelPane.hidden = !voxels
    mlPane.hidden = voxels

    voxelTabButton.classList.toggle('active', voxels)
    mlTabButton.classList.toggle('active', !voxels)

    voxelTabButton.setAttribute('aria-selected', String(voxels))
    mlTabButton.setAttribute('aria-selected', String(!voxels))
}

voxelTabButton.addEventListener('click', () => activateTab('voxel'))
mlTabButton.addEventListener('click', () => activateTab('ml'))

//Frame the camera around a loaded reconstruction:
function fitCameraToObject(object) {
    const bounds = new THREE.Box3().setFromObject(object)

    if (bounds.isEmpty()) return

    const center = bounds.getCenter(new THREE.Vector3())
    const radius = Math.max(0.5, bounds.getBoundingSphere(new THREE.Sphere()).radius)

    camera.position.copy(center.clone().add(new THREE.Vector3(radius * 1.8, radius * 1.2, radius * 1.8)))
    camera.near = Math.max(0.001, radius / 10000)
    camera.far = Math.max(1000, radius * 100)
    camera.updateProjectionMatrix()

    controls.target.copy(center)
    controls.update()
}

//Create the voxel boundary editor:
boundaryEditor = new VoxelBoundaryEditor({
    camera,
    renderer,
    transformControls,
    transformHistory,
    worldVoxelGrid,
    meshSnapper,
    getGridSettings: () => voxelControls.getSettings(),
    onSelect: selectObject,
    onDeselect: deselectObject
})

//Update the voxel grid when the UI settings change:
voxelControls.setOnChange((settings) => {
    worldVoxelGrid.setVoxelSizes(settings.minVoxelSize, settings.maxVoxelSize)
    updateBoundaryGridProjections()
})

/*
//Test Cube (remove later?)
const geometry = new THREE.BoxGeometry(2, 2, 2)
const material = new THREE.MeshStandardMaterial({
    color: 0x4da6ff
})

const cube = new THREE.Mesh(geometry, material)
cube.name = 'Test Cube'
cube.position.y = 1

scene.add(cube);
*/
//Select an object and attach the transform controls:
function selectObject(object) {
    selectedObject = object

    if (selectedObject && !isObjectLocked(selectedObject)) {
        transformControls.attach(selectedObject)
    }
    else {
        transformControls.detach()
    }

    boundaryEditor?.setSelectedObject(selectedObject)
    sceneExplorer.setSelectedObject(selectedObject)
}

//Clear the current selection:
function deselectObject() {
    selectObject(null)
}

//Check if an object or one of its parents is locked.
function isObjectLocked(object) {
    let current = object

    while (current) {
        if (current.userData?.locked === true) return true
        current = current.parent
    }

    return false
}

//Respond when the lock button changes an object's state.
function onObjectLockChanged(object) {
    if (object.userData.locked && boundaryEditor?.editingBoundary === object) {
        boundaryEditor.exitBoundaryEditMode()
    }

    if (selectedObject && isObjectLocked(selectedObject)) {
        transformControls.detach()
    }
    else if (selectedObject && !boundaryEditor?.editingBoundary) {
        transformControls.attach(selectedObject)
    }

    //Remove old transform history for newly locked objects.
    if (object.userData.locked) {
        const isContained = candidate => {
            let current = candidate

            while (current) {
                if (current === object) return true
                current = current.parent
            }

            return false
        }

        transformHistory.undoStack = transformHistory.undoStack.filter(state => !isContained(state.object))
        transformHistory.redoStack = transformHistory.redoStack.filter(state => !isContained(state.object))

        if (isContained(transformHistory.startState?.object)) {
            transformHistory.startState = null
        }
    }
}

//Remove an object from the scene:
function deleteSceneObject(object) {
    if (!object || object.isLight || !object.parent) return

    //Collect the object and its children/grandchildren/descendants.
    const removed = new Set()
    object.traverse(child => removed.add(child))

    //Exit voxel boundary edit mode before removing its handles.
    if (boundaryEditor?.editingBoundary && removed.has(boundaryEditor.editingBoundary)) {
        boundaryEditor.exitBoundaryEditMode()
    }

    //Detach the transform gizmo if its object is being removed.
    if (removed.has(selectedObject)) {
        deselectObject()
    }

    //Remove stale transform history entries.
    transformHistory.undoStack = transformHistory.undoStack.filter(state => !removed.has(state.object))
    transformHistory.redoStack = transformHistory.redoStack.filter(state => !removed.has(state.object))

    if (removed.has(transformHistory.startState?.object)) {
        transformHistory.startState = null
    }

    if (object === reconstructionLibrary.group) {
        //The reconstruction library owns its GLB and overlay resources.
        reconstructionLibrary.clearLoaded()
        reconstructionLibrary.activeVariant = 'original'
        mlControls.modelSelect.value = ''
        mlControls.refresh()
    }
    else {
        //Remove this object from the BVH snapping targets.
        meshSnapper.unregisterObject(object)

        object.removeFromParent()
        disposeRemovedObject(object)
    }

    sceneExplorer.refresh()
}

//Properly dispose of geometry, materials, and textures owned by a removed object:
function disposeRemovedObject(object) {
    const geometries = new Set()
    const materials = new Set()
    const textures = new Set()

    object.traverse(child => {
        if (child.geometry) {
            geometries.add(child.geometry)
        }

        const childMaterials = Array.isArray(child.material) ? child.material : [child.material]

        for (const material of childMaterials) {
            if (!material) continue

            materials.add(material)
            for (const value of Object.values(material)) {
                if (value?.isTexture) {
                    textures.add(value)
                }
            }
        }
    })

    for (const geometry of geometries) {
        geometry.disposeBoundsTree?.()
        geometry.dispose()
    }

    for (const material of materials) {
        material.dispose()
    }

    for (const texture of textures) {
        texture.dispose()
    }
}

//Add a new voxel boundary to the scene:
addVoxelBoundaryButton.addEventListener('click', () => {
    voxelBoundaryCount++

    const boundary = new VoxelBoundary({
        name: `Voxel Boundary ${voxelBoundaryCount}`,
        width: 2,
        height: 2,
        depth: 2,
        position: new THREE.Vector3(0, 1, 0)
    })

    scene.add(boundary)
    updateBoundaryGridProjection(boundary)

    selectObject(boundary)
    sceneExplorer.refresh()
})

//Update the projected voxel grid for one boundary:
function updateBoundaryGridProjection(boundary) {
    const settings = voxelControls.getSettings()

    boundary.updateGridProjection(worldVoxelGrid, settings.voxelGridOpacity, settings.voxelBoundaryColor, settings.minVoxelColor, settings.maxVoxelColor)
}

//Update the projected voxel grids for all boundaries:
function updateBoundaryGridProjections() {
    scene.children.forEach(object => {
        if (object.isVoxelBoundary) {
            updateBoundaryGridProjection(object)
        }
    })
}

//Calculate volume through the Python voxel API:
async function calculateApproxVolume() {
    const button = document.querySelector('#calculateVoxelVolumeButton')
    button.disabled = true
    voxelStatus.textContent = 'Calculating volume...'

    try {
        const meshFile = await exportVisibleSceneMeshes(scene, transformHelper)
        const boundaryFile = exportVoxelBoundaries(scene, voxelControls.getSettings())

        const formData = new FormData()
        formData.append('mesh', meshFile, 'scene.glb')
        formData.append('boundaries', boundaryFile, 'boundaries.json')

        const response = await fetch('http://127.0.0.1:8000/api/volume', {
            method: 'POST',
            body: formData
        })

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
        }

        const result = await response.json()

        voxelVolume.textContent = result.volume == null ? '--' : Number(result.volume).toLocaleString(undefined, { maximumFractionDigits: 5 }) + " units³"
        voxelInverseVolume.textContent = result.inverseVolume == null ? '--' : Number(result.inverseVolume).toLocaleString(undefined, { maximumFractionDigits: 5 }) + " units³"
        voxelBoundaryVolume.textContent = result.sampledBoundaryVolume == null ? '--' : Number(result.sampledBoundaryVolume).toLocaleString(undefined, { maximumFractionDigits: 5 }) + " units³"

        voxelCount.textContent = result.voxelCount == null ? '--' : Number(result.voxelCount).toLocaleString()
        voxelTriangles.textContent = result.mesh?.triangleCount == null ? '--' : Number(result.mesh.triangleCount).toLocaleString()

        voxelStatus.textContent = 'Calculation complete. Volumes are measured in cubic model units.'

        if (result.mesh) {
            const resultMesh = voxelResultMesh.create(result.mesh)
            scene.add(resultMesh)
            sceneExplorer.refresh()
        }
    }
    catch (error) {
        voxelStatus.textContent = `Volume calculation failed: ${error.message}. Check that the voxel API is running.`
        console.error('Volume calculation failed:', error)
    }
    finally {
        button.disabled = false
    }
}

//Update the Voxel grids (and scene explorer) after the initial obejcts have been added:
sceneExplorer.refresh();
