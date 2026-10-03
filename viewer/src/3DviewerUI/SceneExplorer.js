//Controls the scene explorer UI:
export class SceneExplorer {
    //Store the scene explorer references:
    constructor(scene, container, transformHelper, onSelect) {
        this.scene = scene
        this.container = container
        this.transformHelper = transformHelper
        this.onSelect = onSelect
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