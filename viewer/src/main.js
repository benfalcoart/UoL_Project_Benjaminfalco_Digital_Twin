import './style.css'
import * as THREE from 'three'
//Controls:
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { TransformControls } from 'three/addons/controls/TransformControls.js'
//Model Loaders:
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'



const scene = new THREE.Scene()
scene.background = new THREE.Color(0x202020) //Nice Grey background.


//UI:
const loadMeshButton = document.querySelector('#loadMeshButton')
const meshFileInput = document.querySelector('#meshFileInput')

const minVoxelSlider = document.querySelector('#minVoxelSize')
const maxVoxelSlider = document.querySelector('#maxVoxelSize')

const minVoxelValue = document.querySelector('#minVoxelValue')
const maxVoxelValue = document.querySelector('#maxVoxelValue')

let minVoxelSize = Number(minVoxelSlider.value)
let maxVoxelSize = Number(maxVoxelSlider.value)


const camera = new THREE.PerspectiveCamera(
    60,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
)
//Camera start pos:
camera.position.set(4, 3, 6);

const renderer = new THREE.WebGLRenderer({ antialias: true })
renderer.setSize(window.innerWidth, window.innerHeight)
renderer.setPixelRatio(window.devicePixelRatio);

document.querySelector('#app').appendChild(renderer.domElement)
//Camera controls:
const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true

const transformControls = new TransformControls(camera, renderer.domElement)

const transformHelper = transformControls.getHelper()
scene.add(transformHelper)

transformControls.addEventListener('dragging-changed', (event) => {
    controls.enabled = !event.value
});

transformControls.addEventListener('mouseDown', () => {
    if (!selectedObject) {
        return
    }

    transformStartState = captureTransform(selectedObject)
})

transformControls.addEventListener('mouseUp', () => {
    if (!selectedObject || !transformStartState) {
        return
    }

    const transformEndState = captureTransform(selectedObject)

    if (!transformsEqual(transformStartState, transformEndState)) {
        undoStack.push(transformStartState)
        redoStack.length = 0
    }

    transformStartState = null

    updateVoxelGrids()
})

//Lights:
const ambientLight = new THREE.AmbientLight(0xffffff, 1.5)
ambientLight.name = 'Ambient Light'
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 2)
directionalLight.name = 'Directional Light'
directionalLight.position.set(5, 10, 5)
scene.add(directionalLight);

//Grid:
//const grid = new THREE.GridHelper(20, 20)
//grid.name = 'Grid Helper'
//scene.add(grid);
const undoStack = []
const redoStack = []

let transformStartState = null
let selectedObject = null

//Voxel Grid visualizer idea test:
let voxelGrids = [];
//voxel grid colors:
const minVoxelColor = 0x2255aa //dark blue
const maxVoxelColor = 0x66ccff //light blue
let voxelSize = maxVoxelSize;


//Test Cube (TODO: remove later?)
const geometry = new THREE.BoxGeometry(2, 2, 2)
const material = new THREE.MeshStandardMaterial({
    color: 0x4da6ff
})

const cube = new THREE.Mesh(geometry, material)
cube.name = 'Test Cube'
cube.position.y = 1

scene.add(cube);

//Keep renderer at the size of the window.
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight
    camera.updateProjectionMatrix()

    renderer.setSize(window.innerWidth, window.innerHeight)
})

function selectObject(object) {
    selectedObject = object

    if (selectedObject) {
        transformControls.attach(selectedObject)
    }
    else {
        transformControls.detach()
    }

    updateSceneExplorer()
}

function deselectObject() {
    selectObject(null)
}

//Update the Voxel grids (and scene explorer) after the initial obejcts have been added:
updateSceneExplorer();
updateVoxelGrids();

function animate() {
    controls.update()

    renderer.render(scene, camera)
}

//Loading Mesh from Computer:
loadMeshButton.addEventListener('click', () => {
    meshFileInput.click()
})

//Button event to load a mesh from file. (TODO: Add a load from Server option when digital twins are available.)
meshFileInput.addEventListener('change', () => {
    const file = meshFileInput.files[0]

    if (!file) {
        return
    }

    const extension = file.name
        .split('.')
        .pop()
        .toLowerCase()

    const url = URL.createObjectURL(file)

    if (extension === 'glb' || extension === 'gltf') {
        const loader = new GLTFLoader()

        loader.load(
            url,
            (gltf) => {
                gltf.scene.name = file.name
                scene.add(gltf.scene);
                updateVoxelGrids();
                URL.revokeObjectURL(url);
            },
            undefined,
            handleLoadError
        )
    }
    else if (extension === 'obj') {
        const loader = new OBJLoader()

        loader.load(
            url,
            (object) => {
                object.name = file.name;
                scene.add(object);
                updateVoxelGrids();
                URL.revokeObjectURL(url)
            },
            undefined,
            handleLoadError
        )
    }
    else if (extension === 'ply') {
        const loader = new PLYLoader()

        loader.load(
            url,
            (geometry) => {
                geometry.computeVertexNormals();

                const material = new THREE.MeshStandardMaterial({
                    color: 0xcccccc
                });

                const mesh = new THREE.Mesh(
                    geometry,
                    material
                );
                mesh.name = file.name;
                scene.add(mesh);
                updateVoxelGrids();
                URL.revokeObjectURL(url)
            },
            undefined,
            handleLoadError
        )
    }
})

//Model Errors:
function handleLoadError(error) {
    console.error('Failed to load model:', error)
}

//Voxel slider:
minVoxelSlider.addEventListener('input', () => {
    minVoxelSize = Number(minVoxelSlider.value)

    if (minVoxelSize > maxVoxelSize) {
        minVoxelSize = maxVoxelSize
        minVoxelSlider.value = maxVoxelSize
    }

    minVoxelValue.textContent = minVoxelSize.toFixed(3)

    updateVoxelization()
})

maxVoxelSlider.addEventListener('input', () => {
    maxVoxelSize = Number(maxVoxelSlider.value)

    if (maxVoxelSize < minVoxelSize) {
        maxVoxelSize = minVoxelSize
        maxVoxelSlider.value = minVoxelSize
    }

    maxVoxelValue.textContent = maxVoxelSize.toFixed(3)

    updateVoxelization()
})
//TODO: Voxelize here? (either in browser or in a python script if too slow.)
function updateVoxelization() {
    updateVoxelGrids();
}

//Update the Scene explorer. This should be called anytime a mesh is added.
function updateSceneExplorer() {
    const sceneTree = document.querySelector('#sceneTree')

    sceneTree.innerHTML = ''

    scene.children.forEach((object) => {
        if (object === transformControls.getHelper()) {
            return
        }

        if (voxelGrids.includes(object)) {
            return
        }

        const item = createSceneItem(object)
        sceneTree.appendChild(item)
    })
}
//This adds a new item to the scene list:
function createSceneItem(object) {
    const item = document.createElement('div')
    item.classList.add('scene-item')

    if (object === selectedObject) {
        item.classList.add('selected')
    }

    const visibilityCheckbox = document.createElement('input')
    visibilityCheckbox.type = 'checkbox'
    visibilityCheckbox.checked = object.visible

    visibilityCheckbox.addEventListener('change', (event) => {
        event.stopPropagation()
        object.visible = visibilityCheckbox.checked
    })

    const name = document.createElement('span')
    name.classList.add('scene-item-name')
    name.textContent = object.name || object.type

    item.addEventListener('click', () => {
        selectObject(object)
    })

    item.appendChild(visibilityCheckbox)
    item.appendChild(name)

    return item
}
function createVoxelGrid(sizeA, sizeB, cellsA, cellsB, plane, color) {
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
        color: color
    })

    return new THREE.LineSegments(geometry, material);
}

function updateVoxelGrids() {
    voxelGrids.forEach(grid => scene.remove(grid));
    voxelGrids = [];

    const meshes = [];

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

    scene.traverse((object) => {
        if (!object.isMesh) {
            return
        }

        if (isChildOf(object, transformHelper)) {
            return
        }

        if (!isVisibleInScene(object)) {
            return
        }

        meshes.push(object)
    })

    if (meshes.length === 0) {
        updateSceneExplorer()
        return
    }

    const bounds = new THREE.Box3()

    meshes.forEach((mesh) => {
        bounds.expandByObject(mesh)
    })

    createVoxelGridBox(
        bounds,
        minVoxelSize,
        maxVoxelSize,
        maxVoxelSize * 2,
        minVoxelColor,
        'Min Voxel'
    )

    createVoxelGridBox(
        bounds,
        maxVoxelSize,
        maxVoxelSize,
        maxVoxelSize * 2,
        maxVoxelColor,
        'Max Voxel'
    )

    updateSceneExplorer()
}

function createVoxelGridBox(bounds, voxelSize, maxVoxelSize, padding, color, name) {   

    const size = new THREE.Vector3()
    bounds.getSize(size)

    //Round each dimension up to the nearest voxel boundary. (use the max so we can clamp the minimum to the max grid)
    const width = Math.ceil((size.x + padding * 2) / maxVoxelSize) * maxVoxelSize
    const height = Math.ceil((size.y + padding * 2) / maxVoxelSize) * maxVoxelSize
    const depth = Math.ceil((size.z + padding * 2) / maxVoxelSize) * maxVoxelSize

    //Calculate the number of cells required along each axis.
    const xCells = Math.max(1, Math.round(width / voxelSize))
    const yCells = Math.max(1, Math.round(height / voxelSize))
    const zCells = Math.max(1, Math.round(depth / voxelSize))

    //Bottom-left-back corner of the voxel grid.
    const corner = new THREE.Vector3(
        bounds.min.x - padding,
        bounds.min.y - padding,
        bounds.min.z - padding
    )

    //Floor:
    const floorGrid = createVoxelGrid(width, depth, xCells, zCells, 'XZ', color);
    floorGrid.name = `${name} Grid Floor`
    floorGrid.position.set(
        corner.x + width / 2,
        corner.y,
        corner.z + depth / 2
    )

    //Back:
    const backGrid = createVoxelGrid(width, height, xCells, yCells, 'XY', color);
    backGrid.name = `${name} Grid Back`
    backGrid.position.set(
        corner.x + width / 2,
        corner.y + height / 2,
        corner.z
    )

    //Side:
    const sideGrid = createVoxelGrid(depth, height, zCells, yCells, 'YZ', color);
    sideGrid.name = `${name} Grid Side`
    sideGrid.position.set(
        corner.x,
        corner.y + height / 2,
        corner.z + depth / 2
    )

    voxelGrids.push(floorGrid, backGrid, sideGrid);
    scene.add(floorGrid, backGrid, sideGrid);
}

//HOTKEY Listners:
window.addEventListener('keydown', (event) => {
    const key = event.key.toLowerCase()

    if (event.ctrlKey && key === 'z' && !event.shiftKey) {
        event.preventDefault()
        undo()
        return
    }

    if (
        (event.ctrlKey && event.shiftKey && key === 'z') ||
        (event.ctrlKey && key === 'y')
    ) {
        event.preventDefault()
        redo()
        return
    }

    if (!selectedObject) {
        return
    }

    switch (key) {
        case 'w':
            transformControls.setMode('translate')
            break

        case 'e':
            transformControls.setMode('rotate')
            break

        case 'r':
            transformControls.setMode('scale')
            break

        case 'escape':
            deselectObject()
            break
    }
})

function captureTransform(object) {
    return {
        object,
        position: object.position.clone(),
        quaternion: object.quaternion.clone(),
        scale: object.scale.clone()
    }
}

function restoreTransform(state) {
    state.object.position.copy(state.position)
    state.object.quaternion.copy(state.quaternion)
    state.object.scale.copy(state.scale)

    state.object.updateMatrixWorld(true)
}

function transformsEqual(a, b) {
    return (
        a.position.equals(b.position) &&
        a.quaternion.equals(b.quaternion) &&
        a.scale.equals(b.scale)
    )
}

function undo() {
    if (undoStack.length === 0) {
        return
    }

    const action = undoStack.pop()

    const currentState = captureTransform(action.object)
    redoStack.push(currentState)

    restoreTransform(action)

    selectObject(action.object)
    updateVoxelGrids()
}

function redo() {
    if (redoStack.length === 0) {
        return
    }

    const action = redoStack.pop()

    const currentState = captureTransform(action.object)
    undoStack.push(currentState)

    restoreTransform(action)

    selectObject(action.object)
    updateVoxelGrids()
}

//THREE.js render loop:
renderer.setAnimationLoop(animate)