//Exports all visible voxel boundaries into a JSON file:
export function exportVoxelBoundaries(scene) {
    const boundaries = []

    scene.children.forEach(object => {
        if (object.isVoxelBoundary && object.visible) {
            boundaries.push(object.toJSON())
        }
    })

    const json = JSON.stringify({
        boundaries
    }, null, 2)

    return new Blob([json], {
        type: 'application/json'
    })
}