import * as THREE from 'three'

//This class will store the fixed world voxel grid settings:
export class WorldVoxelGrid {
    //Create the world grid using a fixed origin and voxel sizes:
    constructor(origin = new THREE.Vector3(), minVoxelSize = 0.1, maxVoxelSize = 0.5) {
        this.origin = origin.clone()

        this.minVoxelSize = minVoxelSize
        this.maxVoxelSize = maxVoxelSize
    }

    //Update the fixed world grid origin:
    setOrigin(origin) {
        this.origin.copy(origin)
    }

    //Update the minimum and maximum voxel sizes:
    setVoxelSizes(minVoxelSize, maxVoxelSize) {
        this.minVoxelSize = minVoxelSize
        this.maxVoxelSize = maxVoxelSize
    }

    //Find the first grid line inside a range:
    getFirstGridPosition(minValue, voxelSize, axis) {
        const origin = this.origin[axis]

        return Math.ceil((minValue - origin) / voxelSize) * voxelSize + origin
    }

    //Find the last grid line inside a range:
    getLastGridPosition(maxValue, voxelSize, axis) {
        const origin = this.origin[axis]

        return Math.floor((maxValue - origin) / voxelSize) * voxelSize + origin
    }

    //Get all world grid positions inside a range:
    getGridPositions(minValue, maxValue, voxelSize, axis) {
        const positions = []

        const first = this.getFirstGridPosition(minValue, voxelSize, axis)
        const last = this.getLastGridPosition(maxValue, voxelSize, axis)

        for (let value = first; value <= last + 0.000001; value += voxelSize) {
            positions.push(value)
        }

        return positions
    }

    //Get the minimum voxel grid positions:
    getMinGridPositions(minValue, maxValue, axis) {
        return this.getGridPositions(minValue, maxValue, this.minVoxelSize, axis)
    }

    //Get the maximum voxel grid positions:
    getMaxGridPositions(minValue, maxValue, axis) {
        return this.getGridPositions(minValue, maxValue, this.maxVoxelSize, axis)
    }
}