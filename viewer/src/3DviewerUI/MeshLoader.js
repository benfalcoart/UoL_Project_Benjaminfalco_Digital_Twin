import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'

//Loading Mesh from Computer:
//Loads supported mesh files into the scene:
export class MeshLoader {
    //Store the loader references and setup the UI events:
    constructor(scene, loadButton, fileInput, onObjectAdded = null) {
        this.scene = scene
        this.loadButton = loadButton
        this.fileInput = fileInput
        this.onObjectAdded = onObjectAdded

        this.loadButton.addEventListener('click', () => {
            this.fileInput.click()
        })

        this.fileInput.addEventListener('change', () => {
            this.loadSelectedFile()
        })
    }

    //Button event to load a mesh from file. (TODO: Add a load from Server option when digital twins are available.)
    //Load the file selected by the user:
    loadSelectedFile() {
        const file = this.fileInput.files[0]

        if (!file) {
            return
        }

        const extension = file.name.split('.').pop().toLowerCase()
        const url = URL.createObjectURL(file)

        if (extension === 'glb' || extension === 'gltf') {
            this.loadGLTF(file, url)
        }
        else if (extension === 'obj') {
            this.loadOBJ(file, url)
        }
        else if (extension === 'ply') {
            this.loadPLY(file, url)
        }
    }

    //Load a GLB or GLTF model:
    loadGLTF(file, url) {
        const loader = new GLTFLoader()

        loader.load(url, (gltf) => {
            gltf.scene.name = file.name
            this.scene.add(gltf.scene)
            this.objectAdded(gltf.scene)
            URL.revokeObjectURL(url)
        }, undefined, this.handleLoadError)
    }

    //Load an OBJ model:
    loadOBJ(file, url) {
        const loader = new OBJLoader()

        loader.load(url, (object) => {
            object.name = file.name
            this.scene.add(object)
            this.objectAdded(object)
            URL.revokeObjectURL(url)
        }, undefined, this.handleLoadError)
    }

    //Load a PLY model:
    loadPLY(file, url) {
        const loader = new PLYLoader()

        loader.load(url, (geometry) => {
            geometry.computeVertexNormals()

            const material = new THREE.MeshStandardMaterial({
                color: 0xcccccc
            })

            const mesh = new THREE.Mesh(geometry, material)

            mesh.name = file.name
            this.scene.add(mesh)
            this.objectAdded(mesh)

            URL.revokeObjectURL(url)
        }, undefined, this.handleLoadError)
    }

    //Notify the viewer that a new object was added:
    objectAdded(object) {
        if (this.onObjectAdded) {
            this.onObjectAdded(object)
        }
    }

    //Model Errors:
    //Print model loading errors:
    handleLoadError(error) {
        console.error('Failed to load model:', error)
    }
}
