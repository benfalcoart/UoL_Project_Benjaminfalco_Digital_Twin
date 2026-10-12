import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

import MATERIAL_COLORS from '../../../shared/material_colors.json'

const MAP_FILES = {
    raw: 'material_id_superpixel_raw.png',
    tie: 'material_id_tie_preview_raw.png',
    merged: 'material_id_superpixel_merged.png',
    topology: 'material_id_topology_refined.png'
}

function releaseTree(root) {
    const usedTextures = new Set()
    root.traverse(object => {
        if (!object.isMesh) return
        // Overlay meshes share geometry with the originals, and must not dispose it.
        if (object.userData.materialOverlay) {
            object.material.dispose()
        } else {
            object.geometry?.dispose()
            const materials = Array.isArray(object.material) ? object.material : [object.material]
            materials.forEach(material => {
                if (!material) return
                for (const value of Object.values(material)) {
                    if (value?.isTexture && !usedTextures.has(value)) {
                        usedTextures.add(value)
                        value.dispose()
                    }
                }
                material.dispose()
            })
        }
    })
}

// Loads hosted reconstructions from the BEHOLDER ML API.
export class ReconstructionLibrary {
    constructor(scene, onLoaded, onUpdate, onRemove = null) {
        this.scene = scene
        this.onLoaded = onLoaded
        this.onUpdate = onUpdate
        this.onRemove = onRemove
        this.scans = new Map() // reconstruction -> (chunk name -> hosted GLB URL)
        this.outputs = new Map() // reconstruction -> configuration -> chunk -> map filename -> hosted URL
        this.group = null
        this.activeName = null
        this.activeVariant = 'original'
        this.opacity = 0.65
        this.overlays = []
        this.loader = new GLTFLoader()
        this.textureLoader = new THREE.TextureLoader()
        this.textureCache = new Map()
        this.materialStatistics = []
        this.loadGeneration = 0
    }

    // Fetch catalog from ML API; no filesystem permissions or folder pickers required.
    async loadManifest() {
        const response = await fetch('/api/ml/reconstructions', { cache: 'no-store' })
        if (!response.ok) throw new Error(`Model catalog unavailable (HTTP ${response.status})`)
        const manifest = await response.json()
        if (!Array.isArray(manifest.reconstructions)) throw new Error('Invalid reconstructions.json: missing reconstructions array')

        const scans = new Map()
        const outputs = new Map()
        for (const entry of manifest.reconstructions) {
            if (!entry.name || !Array.isArray(entry.chunks)) continue
            const chunks = new Map()
            for (const chunk of entry.chunks) {
                if (!chunk.name || !chunk.url) continue
                chunks.set(chunk.name, chunk.url)
            }
            if (!chunks.size) continue
            scans.set(entry.name, chunks)

            const configurations = new Map()
            for (const [configName, chunkMaps] of Object.entries(entry.maps || {})) {
                const mapsByChunk = new Map()
                for (const [chunkName, kinds] of Object.entries(chunkMaps)) {
                    const maps = new Map()
                    for (const [kind, url] of Object.entries(kinds)) {
                        const filename = MAP_FILES[kind]
                        if (filename && typeof url === 'string') maps.set(filename, url)
                    }
                    if (maps.size) mapsByChunk.set(chunkName, maps)
                }
                if (mapsByChunk.size) configurations.set(configName, mapsByChunk)
            }
            outputs.set(entry.name, configurations)
        }
        this.scans = scans
        this.outputs = outputs
        this.onUpdate?.()
        return scans.size
    }

    getReconstructions() {
        return [...this.scans.keys()].sort((a, b) => a.localeCompare(b))
    }

    getVariants(name = this.activeName) {
        const variants = [{ value: 'original', label: 'Original diffuse texture' }]
        const configs = this.outputs.get(name)
        if (!configs) return variants
        for (const [configuration, chunks] of configs) {
            for (const [kind, filename] of Object.entries(MAP_FILES)) {
                if ([...chunks.values()].some(maps => maps.has(filename))) {
                    const display = kind === 'topology' ? 'Topology refined' : kind === 'merged' ? 'Merged ID' : kind === 'tie' ? 'Tie preview' : 'Raw ID'
                    variants.push({ value: `${configuration}|${kind}`, label: `${configuration} — ${display}` })
                }
            }
        }
        return variants
    }

    async load(name) {
        const chunks = this.scans.get(name)
        if (!chunks?.size) throw new Error(`No GLB chunks found for ${name}`)
        const generation = ++this.loadGeneration
        const nextGroup = new THREE.Group()
        nextGroup.name = name
        nextGroup.userData.reconstruction = true
        nextGroup.userData.locked = true // Prevent accidental movement of assembled scans.
        // Every GLB contains coordinates exported from the same original world space.
        // Never recenter each chunk independently or the scan cannot be reassembled.
        try {
            for (const [chunkName, url] of [...chunks].sort(([a], [b]) => a.localeCompare(b))) {
                const gltf = await this.loader.loadAsync(url)
                if (generation !== this.loadGeneration) {
                    releaseTree(gltf.scene)
                    releaseTree(nextGroup)
                    return null
                }
                gltf.scene.name = chunkName
                gltf.scene.userData.chunkName = chunkName
                gltf.scene.traverse(child => {
                    if (!child.isMesh) return
                    const materials = Array.isArray(child.material) ? child.material : [child.material]
                    materials.forEach(material => { material.side = THREE.DoubleSide; material.needsUpdate = true })
                })
                nextGroup.add(gltf.scene)
            }
        } catch (error) {
            releaseTree(nextGroup)
            throw error
        }
        this.clearLoaded()
        this.group = nextGroup
        this.activeName = name
        this.activeVariant = 'original'
        this.scene.add(nextGroup)
        this.onLoaded?.(nextGroup)
        this.onUpdate?.()
        return nextGroup
    }

    clearLoaded() {
        ++this.loadGeneration
        this.clearOverlays()
        if (this.group) {
            this.onRemove?.(this.group)
            this.group.removeFromParent()
            releaseTree(this.group)
            this.group = null
        }
        this.activeName = null
        this.materialStatistics = []
    }

    clearOverlays() {
        for (const overlay of this.overlays) {
            overlay.removeFromParent()
            overlay.material.dispose()
        }
        this.overlays.length = 0
        // Avoid retaining dozens of full-resolution ID atlases on the GPU across variants.
        for (const promise of this.textureCache.values()) promise.then(texture => texture.dispose()).catch(() => {})
        this.textureCache.clear()
    }

    async textureFromUrl(url) {
        if (!this.textureCache.has(url)) {
            const promise = new Promise((resolve, reject) => {
                this.textureLoader.load(url, texture => {
                    texture.colorSpace = THREE.SRGBColorSpace
                    texture.flipY = false // Match glTF UV orientation
                    texture.needsUpdate = true
                    resolve(texture)
                }, undefined, reject)
            })
            this.textureCache.set(url, promise)
        }
        return this.textureCache.get(url)
    }

    async setVariant(variant) {
        if (!this.group) return
        const selectedName = this.activeName
        const selectedGroup = this.group
        this.activeVariant = variant
        this.clearOverlays()
        this.materialStatistics = []
        if (variant === 'original') { this.onUpdate?.(); return }
        const [configuration, kind] = variant.split('|')
        const output = this.outputs.get(selectedName)?.get(configuration)
        const filename = MAP_FILES[kind]
        if (!output || !filename) throw new Error(`Material map not found: ${variant}`)
        const sampleFiles = []
        let overlaidChunks = 0
        for (const chunkRoot of selectedGroup.children) {
            const chunk = output.get(chunkRoot.userData.chunkName)
            const url = chunk?.get(filename)
            if (!url) continue
            const texture = await this.textureFromUrl(url)
            if (this.group !== selectedGroup || this.activeVariant !== variant) return
            sampleFiles.push(url)
            chunkRoot.traverse(original => {
                if (!original.isMesh || original.userData.materialOverlay) return
                const material = new THREE.MeshBasicMaterial({
                    map: texture, transparent: true, opacity: this.opacity, depthWrite: false,
                    side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1
                })
                const overlay = new THREE.Mesh(original.geometry, material)
                overlay.name = `${original.name} — material overlay`
                overlay.userData.materialOverlay = true
                overlay.userData.excludeFromExport = true
                overlay.renderOrder = 10
                original.add(overlay)
                this.overlays.push(overlay)
            })
            overlaidChunks++
        }
        this.onUpdate?.()
        await this.calculateCoverage(sampleFiles, selectedName, configuration, kind, variant)
        return overlaidChunks
    }

    setOpacity(value) {
        this.opacity = value
        this.overlays.forEach(overlay => { overlay.material.opacity = value })
    }

    async calculateCoverage(files, name, config, kind, variant) {
        // UV texel percentages are not physical 3D surface-area percentages.
        // Downsample for responsiveness when a scan has very large atlases.
        const palette = MATERIAL_COLORS
        const byRgb = new Map(Object.entries(palette).map(([label, rgb]) => [rgb.join(','), label]))
        const totals = new Map()
        let totalPixels = 0
        for (const url of files) {
            const response = await fetch(url)
            if (!response.ok) throw new Error(`Unable to read material map (HTTP ${response.status}): ${url}`)
            const bitmap = await createImageBitmap(await response.blob())
            const canvas = document.createElement('canvas')
            canvas.width = Math.min(512, bitmap.width)
            canvas.height = Math.min(512, bitmap.height)
            const ctx = canvas.getContext('2d', { willReadFrequently: true })
            ctx.imageSmoothingEnabled = false
            ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
            bitmap.close()
            const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
            for (let p = 0; p < data.length; p += 4) {
                if (data[p + 3] < 128) continue
                const label = byRgb.get(`${data[p]},${data[p + 1]},${data[p + 2]}`) || 'unmapped'
                totals.set(label, (totals.get(label) || 0) + 1)
                totalPixels++
            }
        }
        if (this.activeName !== name || this.activeVariant !== variant) return
        this.materialStatistics = [...totals].map(([name, pixels]) => ({
            name, color: palette[name] || [180, 180, 180], percent: totalPixels ? 100 * pixels / totalPixels : 0
        })).sort((a, b) => b.percent - a.percent)
        this.onUpdate?.()
    }
}
