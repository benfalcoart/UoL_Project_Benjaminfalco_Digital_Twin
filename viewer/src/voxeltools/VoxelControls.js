//This class controls the voxel settings in the UI:
export class VoxelControls {
    //Find the voxel UI controls and read their starting values:
    constructor(onChange, onCalculateVolume) { 
        //Grab the HTML controls:
        this.minVoxelSlider = document.querySelector('#minVoxelSize')
        this.maxVoxelSlider = document.querySelector('#maxVoxelSize')

        this.minVoxelValue = document.querySelector('#minVoxelValue')
        this.maxVoxelValue = document.querySelector('#maxVoxelValue')

        this.voxelGridOpacitySlider = document.querySelector('#voxelGridOpacity')
        this.voxelGridOpacityValue = document.querySelector('#voxelGridOpacityValue')

        this.voxelBoundaryColorPicker = document.querySelector('#voxelBoundaryColor')
        this.minVoxelColorPicker = document.querySelector('#minVoxelColor')
        this.maxVoxelColorPicker = document.querySelector('#maxVoxelColor')

        this.calculateVolumeButton = document.querySelector('#calculateVoxelVolumeButton')
        //Set/Store the values:
        this.minVoxelSize = Number(this.minVoxelSlider.value)
        this.maxVoxelSize = Number(this.maxVoxelSlider.value)
        this.voxelGridOpacity = Number(this.voxelGridOpacitySlider.value)
        this.voxelBoundaryColor = this.voxelBoundaryColorPicker.value
        this.minVoxelColor = this.minVoxelColorPicker.value
        this.maxVoxelColor = this.maxVoxelColorPicker.value

        this.onChange = onChange
        this.onCalculateVolume = onCalculateVolume

        this.setupListeners()
    }

    //Listen for changes to the voxel controls:
    setupListeners() {
        //Voxel sliders:
        this.minVoxelSlider.addEventListener('input', () => {
            this.minVoxelSize = Number(this.minVoxelSlider.value)

            if (this.minVoxelSize > this.maxVoxelSize) {
                this.minVoxelSize = this.maxVoxelSize
                this.minVoxelSlider.value = this.maxVoxelSize
            }

            this.minVoxelValue.textContent = this.minVoxelSize.toFixed(3)
            this.notifyChange()
        })

        this.maxVoxelSlider.addEventListener('input', () => {
            this.maxVoxelSize = Number(this.maxVoxelSlider.value)

            if (this.maxVoxelSize < this.minVoxelSize) {
                this.maxVoxelSize = this.minVoxelSize
                this.maxVoxelSlider.value = this.minVoxelSize
            }

            this.maxVoxelValue.textContent = this.maxVoxelSize.toFixed(3)
            this.notifyChange()
        })
        //Opacity Slider:
        this.voxelGridOpacitySlider.addEventListener('input', () => {
            this.voxelGridOpacity = Number(this.voxelGridOpacitySlider.value)
            this.voxelGridOpacityValue.textContent = this.voxelGridOpacity.toFixed(2)

            this.notifyChange()
        })
        //Colors:
        this.voxelBoundaryColorPicker.addEventListener('input', () => {
            this.voxelBoundaryColor = this.voxelBoundaryColorPicker.value
            this.notifyChange()
        })

        this.minVoxelColorPicker.addEventListener('input', () => {
            this.minVoxelColor = this.minVoxelColorPicker.value
            this.notifyChange()
        })

        this.maxVoxelColorPicker.addEventListener('input', () => {
            this.maxVoxelColor = this.maxVoxelColorPicker.value
            this.notifyChange()
        })
        //Calculate Volume:
        this.calculateVolumeButton.addEventListener('click', () => {
            if (this.onCalculateVolume) {
                this.onCalculateVolume()
            }
        })
    }

    //Sets up the callback used when a setting changes:
    setOnChange(onChange) {
        this.onChange = onChange
    }

    //Notifies the web viewer that the voxel settings changed:
    notifyChange() {
        if (this.onChange) {
            this.onChange(this.getSettings())
        }
    }

    //Return current voxel settings:
    getSettings() {
        return {
            minVoxelSize: this.minVoxelSize,
            maxVoxelSize: this.maxVoxelSize,
            voxelGridOpacity: this.voxelGridOpacity,
            voxelBoundaryColor: this.voxelBoundaryColor,
            minVoxelColor: this.minVoxelColor,
            maxVoxelColor: this.maxVoxelColor
        }
    }

}
