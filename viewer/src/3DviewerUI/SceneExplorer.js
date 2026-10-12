//Controls the scene explorer UI:
export class SceneExplorer {
    //Store the scene explorer references:
    constructor(scene, container, transformHelper, onSelect,  onDelete = null, onLockChange = null) {
        this.scene = scene
        this.container = container
        this.transformHelper = transformHelper
        this.onSelect = onSelect
        this.onDelete = onDelete
        this.onLockChange = onLockChange
        this.selectedObject = null
    }

    //Update the selected item in the explorer:
    setSelectedObject(object) {
        this.selectedObject = object
        this.refresh()
    }

    //Update the Scene explorer. This should be called anytime a mesh is added.
    //Rebuild the scene explorer list:
    refresh() {
        this.container.innerHTML = ''

        this.scene.children.forEach(object => {
            if (object === this.transformHelper) {
                return
            }

            this.container.appendChild(this.createItem(object))
        })
    }

    //This adds a new item to the scene list:
    //Create one scene explorer item:
    createItem(object) {
        const item = document.createElement('div')
        item.classList.add('scene-item')

        if (object === this.selectedObject) {
            item.classList.add('selected')
        }

        const visibilityCheckbox = document.createElement('input')
        visibilityCheckbox.type = 'checkbox'
        visibilityCheckbox.checked = object.visible

        visibilityCheckbox.addEventListener('click', event => {
            event.stopPropagation()
        })

        visibilityCheckbox.addEventListener('change', event => {
            event.stopPropagation()
            object.visible = visibilityCheckbox.checked
        })

        const name = document.createElement('span')
        name.classList.add('scene-item-name')
        name.textContent = object.name || object.type

        item.appendChild(visibilityCheckbox)
        item.appendChild(name)

        if (object.isVoxelBoundary) {
            this.addVoxelBoundaryControls(item, object)
        }

        //Allows meshes, groups, and voxel boundaries to be removed.
        if (!object.isLight) {
            const lockButton = document.createElement('button')
            lockButton.type = 'button'
            lockButton.classList.add('scene-lock-button')

            const updateLockButton = () => {
                const locked = object.userData.locked === true

                lockButton.textContent = locked ? '🔒' : '🔓'
                lockButton.title = `${locked ? 'Unlock' : 'Lock'} ${object.name || object.type}`
                lockButton.setAttribute('aria-label', lockButton.title)
                lockButton.setAttribute('aria-pressed', String(locked))
                item.classList.toggle('locked', locked)
            }

            updateLockButton()

            lockButton.addEventListener('click', event => {
                event.stopPropagation()
                object.userData.locked = !object.userData.locked
                updateLockButton()
                this.onLockChange?.(object)
            })

            item.appendChild(lockButton)


            const deleteButton = document.createElement('button')
            deleteButton.type = 'button'
            deleteButton.classList.add('scene-delete-button')
            deleteButton.textContent = '×'
            deleteButton.title = `Remove ${object.name || object.type} from scene`
            deleteButton.setAttribute('aria-label', deleteButton.title)

            deleteButton.addEventListener('click', event => {
                event.stopPropagation()
                this.onDelete?.(object)
            })

            item.appendChild(deleteButton)
        }

        item.addEventListener('click', () => {
            this.onSelect(object)
        })

        return item
    }

    //Add voxel boundary specific controls:
    addVoxelBoundaryControls(item, object) {
        const gridLabel = document.createElement('span')
        gridLabel.textContent = 'Grid'

        const gridCheckbox = document.createElement('input')
        gridCheckbox.type = 'checkbox'
        gridCheckbox.checked = object.gridVisible

        gridCheckbox.addEventListener('click', event => {
            event.stopPropagation()
        })

        gridCheckbox.addEventListener('change', event => {
            object.setGridVisible(event.target.checked)
        })

        item.appendChild(gridLabel)
        item.appendChild(gridCheckbox)
    }
}