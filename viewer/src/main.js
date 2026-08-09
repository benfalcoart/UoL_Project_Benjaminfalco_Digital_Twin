import './style.css'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
//Model Loaders:
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'

const scene = new THREE.Scene()
scene.background = new THREE.Color(0x202020) //Nice Grey background.


//UI:
const loadMeshButton = document.querySelector('#loadMeshButton')
const meshFileInput = document.querySelector('#meshFileInput')

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

//Lights:
const ambientLight = new THREE.AmbientLight(0xffffff, 1.5)
ambientLight.name = 'Ambient Light'
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 2)
directionalLight.name = 'Directional Light'
directionalLight.position.set(5, 10, 5)
scene.add(directionalLight);

//Grid:
const grid = new THREE.GridHelper(20, 20)
grid.name = 'Grid Helper'
scene.add(grid);

//Test Cube (TODO: remove later?)
const geometry = new THREE.BoxGeometry(2, 2, 2)
const material = new THREE.MeshStandardMaterial({
    color: 0x4da6ff
})

const cube = new THREE.Mesh(geometry, material)
cube.name = 'Test Cube'
cube.position.y = 1

scene.add(cube);

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight
    camera.updateProjectionMatrix()

    renderer.setSize(window.innerWidth, window.innerHeight)
})

//Update the Scene Explorer list after the initial obejcts have been added:
updateSceneExplorer();

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
                updateSceneExplorer();
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
                updateSceneExplorer();
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
                geometry.computeVertexNormals()

                const material = new THREE.MeshStandardMaterial({
                    color: 0xcccccc
                })

                const mesh = new THREE.Mesh(
                    geometry,
                    material
                )
                mesh.name = file.name;
                scene.add(mesh);
                updateSceneExplorer();
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

//Update the Scene explorer. This should be called anytime a mesh is added.
function updateSceneExplorer() {
    const sceneTree = document.querySelector('#sceneTree')

    sceneTree.innerHTML = ''

    scene.children.forEach((object) => {
        const item = createSceneItem(object)
        sceneTree.appendChild(item)
    })
}
//This adds a new item to the scene list:
function createSceneItem(object) {
    const item = document.createElement('div')
    item.classList.add('scene-item')

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

    item.appendChild(visibilityCheckbox)
    item.appendChild(name)

    return item
}
//THREE.js render loop:
renderer.setAnimationLoop(animate)