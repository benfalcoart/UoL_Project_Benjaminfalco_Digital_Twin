import * as THREE from 'three'

//Handles selecting and editing voxel boundaries:
export class VoxelBoundaryEditor {
    //Store the editor references and setup the controls:
    constructor({ camera, renderer, transformControls, transformHistory, meshSnapper, worldVoxelGrid, getGridSettings, onSelect, onDeselect }) {
        this.camera = camera
        this.renderer = renderer
        this.transformControls = transformControls
        this.transformHistory = transformHistory
        this.meshSnapper = meshSnapper
        this.worldVoxelGrid = worldVoxelGrid
        this.getGridSettings = getGridSettings
        this.onSelect = onSelect
        this.onDeselect = onDeselect

        this.selectedObject = null

        this.raycaster = new THREE.Raycaster()
        this.pointer = new THREE.Vector2()

        this.editingBoundary = null
        this.editingFace = null
        this.faceStartPosition = 0
        this.faceStartBounds = null

        this.setupTransformControls()
        this.setupPointerControls()
        this.setupHotkeys()
        //Needed for outside of keyevents
        this.controlHeld = false
    }

    //Track the currently selected object:
    setSelectedObject(object) {
        this.selectedObject = object
    }

    //Setup the transform gizmo events:
    setupTransformControls() {
        this.transformControls.addEventListener('mouseDown', () => {
            if (!this.selectedObject) {
                return
            }

            this.transformHistory.begin(this.selectedObject)
        })

        this.transformControls.addEventListener('mouseUp', () => {
            if (!this.selectedObject) {
                return
            }

            this.transformHistory.end(this.selectedObject)

            if (this.editingBoundary) {
                this.editingBoundary.buildFaceHandles()
                this.updateBoundaryGridProjection(this.editingBoundary)

                this.editingFace = null
                this.faceStartBounds = null

                this.transformControls.detach()
            }
        })

        this.transformControls.addEventListener('objectChange', () => {
            if (this.editingBoundary && this.editingFace && this.faceStartBounds) {
                const axis = this.editingFace.userData.axis
                const side = this.editingFace.userData.side

                const currentPosition = this.editingFace.position[axis]
                const delta = currentPosition - this.faceStartPosition

                this.editingBoundary.min.copy(this.faceStartBounds.min)
                this.editingBoundary.max.copy(this.faceStartBounds.max)

                let faceValue = side === 'min' ? this.faceStartBounds.min[axis] + delta : this.faceStartBounds.max[axis] + delta

                //Snap the face to a mesh surface while Ctrl is held:
                if (this.controlHeld) {
                    const snappedValue = this.getSnappedFaceValue(axis, side, delta)

                    if (snappedValue !== null) {
                        faceValue = snappedValue
                    }
                }

                if (side === 'min') {
                    this.editingBoundary.min[axis] = faceValue
                }
                else {
                    this.editingBoundary.max[axis] = faceValue
                }

                this.editingBoundary.updateBoundaryVisuals()
                this.updateBoundaryGridProjection(this.editingBoundary)

                return
            }

            if (this.selectedObject?.isVoxelBoundary) {
                this.updateBoundaryGridProjection(this.selectedObject)
            }
        })
    }

    //Setup mouse selection for editable boundary faces:
    setupPointerControls() {
        this.renderer.domElement.addEventListener('pointerdown', (event) => {
            if (!this.editingBoundary?.editMode) {
                return
            }

            const rect = this.renderer.domElement.getBoundingClientRect()

            this.pointer.x =
                ((event.clientX - rect.left) / rect.width) * 2 - 1

            this.pointer.y =
                -((event.clientY - rect.top) / rect.height) * 2 + 1

            this.raycaster.setFromCamera(this.pointer, this.camera)

            const hits = this.raycaster.intersectObjects(
                this.editingBoundary.faceHandles,
                false
            )

            if (hits.length === 0) {
                return
            }

            const face = hits[0].object

            this.editingBoundary.selectFace(face)

            this.editingFace = face

            this.beginFaceTransform(face)
        })
    }
    
    //HOTKEY Listners:
    setupHotkeys() {
        window.addEventListener('keydown', (event) => {
            if (event.key === 'Control') {
                this.controlHeld = true
            }
            
            const key = event.key.toLowerCase()
            
            if (event.ctrlKey && key === 'z' && !event.shiftKey) {
                event.preventDefault()
                this.undo()
                return
            }

            if ((event.ctrlKey && event.shiftKey && key === 'z') || (event.ctrlKey && key === 'y')) {
                event.preventDefault()
                this.redo()
                return
            }

            if (!this.selectedObject) {
                return
            }

            if (event.key === 'Tab') {
                event.preventDefault()

                if (!this.selectedObject?.isVoxelBoundary) {
                    return
                }

                if (this.editingBoundary) {
                    this.exitBoundaryEditMode()
                }
                else {
                    this.editingBoundary = this.selectedObject
                    this.editingBoundary.setEditMode(true)
                    this.transformControls.detach()
                }

                return
            }

            switch (key) {
                case 'w':
                    this.transformControls.setMode('translate')
                    break

                case 'e':
                    this.transformControls.setMode('rotate')
                    break

                case 'r':
                    this.transformControls.setMode('scale')
                    break

                case 'escape':
                    if (this.editingBoundary) {
                        this.exitBoundaryEditMode()
                    }
                    else {
                        this.onDeselect()
                    }
                    break
            }
        })
        window.addEventListener('keyup', (event) => {
            if (event.key === 'Control') {
                this.controlHeld = false
            }
        })
        //Prevents controlHeld from being stuck when tabbing out of the window:
        //https://stackoverflow.com/questions/61713458/ignore-blur-focusout-events-when-switching-tabs-windows
        window.addEventListener('blur', () => {
            this.controlHeld = false
        })
    }



    //Begin dragging one boundary face (like blender's edit mode):
    beginFaceTransform(face) {
        const axis = face.userData.axis

        this.transformControls.attach(face)
        this.transformControls.setMode('translate')
        this.transformControls.setSpace('local')

        this.transformControls.showX = axis === 'x'
        this.transformControls.showY = axis === 'y'
        this.transformControls.showZ = axis === 'z'

        this.faceStartPosition = face.position[axis]

        this.faceStartBounds = {
            min: this.editingBoundary.min.clone(),
            max: this.editingBoundary.max.clone()
        }
    }

    //Get the local-space centre of an editable boundary face:
    getFaceCenter(bounds, axis, side) {
        const center = bounds.min.clone().add(bounds.max).multiplyScalar(0.5)
        
        center[axis] = side === 'min' ? bounds.min[axis] : bounds.max[axis]
        return center
    }

    //Try to snap the currently dragged face to a mesh surface:
    getSnappedFaceValue(axis, side, delta) {
        const epsilon = 0.000001
        if (!this.meshSnapper || Math.abs(delta) < epsilon) {
            return null
        }

        const localStart = this.getFaceCenter(this.faceStartBounds, axis, side)
        const localEnd = localStart.clone()
        localEnd[axis] += delta

        this.editingBoundary.updateWorldMatrix(true, false)

        const worldStart = this.editingBoundary.localToWorld(localStart.clone())
        const worldEnd = this.editingBoundary.localToWorld(localEnd.clone())

        const movement = worldEnd.clone().sub(worldStart)
        const maxDistance = movement.length()

        if (maxDistance < epsilon) {
            return null
        }

        const direction = movement.normalize()
        const hit = this.meshSnapper.findSurface(worldStart, direction, maxDistance)

        if (!hit) {
            return null
        }

        const localHit = this.editingBoundary.worldToLocal(hit.point.clone())
        const snappedValue = localHit[axis]

        //Do not allow the boundary to turn inside-out:
        if (side === 'min' && snappedValue >= this.faceStartBounds.max[axis]) {
            return null
        }

        if (side === 'max' && snappedValue <= this.faceStartBounds.min[axis]) {
            return null
        }

        return snappedValue
    }

    //Exit face editing and restore object transforms:
    exitBoundaryEditMode() {
        if (!this.editingBoundary) {
            return
        }

        this.editingBoundary.setEditMode(false)
        this.editingBoundary.recenterPivot()
        this.updateBoundaryGridProjection(this.editingBoundary)

        this.editingFace = null
        this.faceStartBounds = null

        this.transformControls.detach()

        this.transformControls.showX = true
        this.transformControls.showY = true
        this.transformControls.showZ = true

        this.transformControls.setSpace('world')
        this.transformControls.attach(this.editingBoundary)

        this.editingBoundary = null
    }

    //Update the projected grid for one boundary:
    updateBoundaryGridProjection(boundary) {
        const settings = this.getGridSettings()

        boundary.updateGridProjection(
            this.worldVoxelGrid,
            settings.voxelGridOpacity,
            settings.voxelBoundaryColor,
            settings.minVoxelColor,
            settings.maxVoxelColor
        )
    }

    //Undo the last object transform:
    undo() {
        const object = this.transformHistory.undo()

        if (!object) {
            return
        }

        if (object.isVoxelBoundary) {
            this.updateBoundaryGridProjection(object)
        }

        this.onSelect(object)
    }

    //Redo the last object transform:
    redo() {
        const object = this.transformHistory.redo()

        if (!object) {
            return
        }

        if (object.isVoxelBoundary) {
            this.updateBoundaryGridProjection(object)
        }

        this.onSelect(object)
    }
}
