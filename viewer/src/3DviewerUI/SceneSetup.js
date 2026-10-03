import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { TransformControls } from 'three/addons/controls/TransformControls.js'

//Create the Three.js scene and viewer controls:
export function createScene(appElement) {
    //Create the scene:
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x202020) //Nice Grey background.

    //Create the camera:
    const camera = new THREE.PerspectiveCamera(
        60,
        window.innerWidth / window.innerHeight,
        0.1,
        1000
    )
    //Camera start pos:
    camera.position.set(4, 3, 6);

    //Create the renderer:
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setPixelRatio(window.devicePixelRatio);

    appElement.appendChild(renderer.domElement)

    //Camera controls:
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = false

    //Create the object transform controls:
    const transformControls = new TransformControls(camera, renderer.domElement)

    const transformHelper = transformControls.getHelper()
    scene.add(transformHelper)

    transformControls.addEventListener('dragging-changed', (event) => {
        controls.enabled = !event.value
    });

    //Lights:
    //Add the scene lighting:
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

    //Keep renderer at the size of the window.
    //Keep the renderer the same size as the browser window:
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight
        camera.updateProjectionMatrix()

        renderer.setSize(window.innerWidth, window.innerHeight)
    })

    //Render the scene each frame:
    function animate() {
        controls.update()

        renderer.render(scene, camera)
    }

    //THREE.js render loop:
    //Start the render loop:
    renderer.setAnimationLoop(animate)

    return {
        scene,
        camera,
        renderer,
        controls,
        transformControls,
        transformHelper
    }
}
