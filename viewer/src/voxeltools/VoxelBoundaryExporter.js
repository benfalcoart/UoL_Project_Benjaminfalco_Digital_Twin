//Exports all visible voxel boundaries into a JSON file:
export function exportVoxelBoundaries(scene, settings) {
    const boundaries = []

    scene.children.forEach(object => {
        if (object.isVoxelBoundary && object.visible) {
            boundaries.push(object.toJSON())
        }
    })

    const json = JSON.stringify({
        voxelSettings: {
            maxVoxelSize: settings.maxVoxelSize,
            minVoxelSize: settings.minVoxelSize,
            subdivisionDepth: settings.subdivisionDepth
        },
        boundaries
    }, null, 2)

    return new Blob([json], {
        type: 'application/json'
    })
}