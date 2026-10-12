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

        this.fileInput.value = ''

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
            this.toggleDoubleSided(gltf.scene,true)
            this.scene.add(gltf.scene)
            this.objectAdded(gltf.scene)
            URL.revokeObjectURL(url)
        }, undefined, error => {
            URL.revokeObjectURL(url)
            this.handleLoadError(error)
        })
    }

    //Load an OBJ model:
    loadOBJ(file, url) {
        const loader = new OBJLoader()

        loader.load(url, (object) => {
            object.name = file.name
            this.toggleDoubleSided(object,true)
            this.scene.add(object)
            this.objectAdded(object)
            URL.revokeObjectURL(url)
        }, undefined, error => {
            URL.revokeObjectURL(url)
            this.handleLoadError(error)
        })
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

            this.toggleDoubleSided(mesh,true)

            URL.revokeObjectURL(url)
        }, undefined, error => {
            URL.revokeObjectURL(url)
            this.handleLoadError(error)
        })
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
    //Toggle all mesh materials render on both sides:
    toggleDoubleSided(object,isDoubleSided) {
        object.traverse(child => {
            if (!child.isMesh || !child.material) {
                return
            }

            const materials = Array.isArray(child.material) ? child.material : [child.material]

            materials.forEach(material => {
                material.side =isDoubleSided ? THREE.DoubleSide : THREE.FrontSide
                material.needsUpdate = true
            })
        })
    }
}
