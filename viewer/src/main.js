import './style.css'
import * as THREE from 'three'

import { createScene } from './3DviewerUI/SceneSetup.js'
import { MeshLoader } from './3DviewerUI/MeshLoader.js'
import { SceneExplorer } from './3DviewerUI/SceneExplorer.js'
import { TransformHistory } from './3DviewerUI/TransformHistory.js'
import { exportVisibleSceneMeshes } from './3DviewerUI/SceneExporter.js'
import { MeshSnapper } from './3DviewerUI/MeshSnapper.js'

import { VoxelBoundary } from './voxeltools/VoxelBoundary.js'
import { WorldVoxelGrid } from './voxeltools/WorldVoxelGrid.js'
import { VoxelBoundaryEditor } from './voxeltools/VoxelBoundaryEditor.js'
import { VoxelControls } from './voxeltools/VoxelControls.js'
import { exportVoxelBoundaries } from './voxeltools/VoxelBoundaryExporter.js'

//Create the main Three.js scene:
const {
    scene,
    camera,
    renderer,
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

//Voxel Grid visualizer idea test:
const voxelGridOrigin = new THREE.Vector3(0, 0, 0)
const worldVoxelGrid = new WorldVoxelGrid(voxelGridOrigin, initialVoxelSettings.minVoxelSize, initialVoxelSettings.maxVoxelSize)

//Create the scene explorer:
const sceneExplorer = new SceneExplorer(
    scene,
    document.querySelector('#sceneTree'),
    transformHelper,
    selectObject
)

//Create the model loader:
const meshLoader = new MeshLoader(scene, loadMeshButton, meshFileInput, (loadedObject) => {
    meshSnapper.registerObject(loadedObject)
    sceneExplorer.refresh()
})

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

    if (selectedObject) {
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

//TODO: Write Python API for doing volume calculates. Is probably too heavy for browser.
async function calculateApproxVolume() {
    const meshFile = await exportVisibleSceneMeshes(scene, transformHelper)
    const boundaryFile = exportVoxelBoundaries(scene,voxelControls.getSettings())

    //console.log(voxelSettings)

    const formData = new FormData()
    formData.append('mesh', meshFile, 'scene.glb')
    formData.append('boundaries', boundaryFile, 'boundaries.json')

    const response = await fetch('http://127.0.0.1:8000/api/volume', {
        method: 'POST',
        body: formData
    })

    if (!response.ok) {
        console.error('Volume calculation failed')
        return
    }

    const result = await response.json()

    console.log(result)
}

//Update the Voxel grids (and scene explorer) after the initial obejcts have been added:
sceneExplorer.refresh();
