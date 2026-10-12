//viewer controller: hosted reconstructions, classification API is currently disabled 
//to prevent my GPU from randomly firing from someone over the internet pressing the button.
export class MLControls {
    constructor(library, options = {}) {
        this.library = library
        this.onModelSelected = options.onModelSelected
        this.modelSelect = document.querySelector('#reconstructionSelect')
        this.mapSelect = document.querySelector('#materialMapSelect')
        this.opacityInput = document.querySelector('#materialOpacity')
        this.opacityValue = document.querySelector('#materialOpacityValue')
        this.status = document.querySelector('#mlStatus')
        this.materialStats = document.querySelector('#materialStatistics')
        this.runButton = document.querySelector('#runMLButton')
        this.loading = false
        this.bind()
        this.refresh()
        this.loadCatalog()
    }

    message(text, error = false) {
        this.status.textContent = text
        this.status.classList.toggle('error', error)
    }

    bind() {
        this.modelSelect.addEventListener('change', async () => {
            const name = this.modelSelect.value
            if (!name) return
            this.loading = true
            this.message(`Loading ${name}...`)
            try {
                const group = await this.library.load(name)
                if (group) { this.onModelSelected?.(group); this.message(`Loaded ${group.children.length} GLB chunks.`) }
            } catch (error) { this.message(`Load failed: ${error.message}`, true) }
            finally { this.loading = false; this.refresh() }
        })
        this.mapSelect.addEventListener('change', async () => {
            this.message('Loading material maps...')
            try {
                const count = await this.library.setVariant(this.mapSelect.value)
                this.message(this.mapSelect.value === 'original' ? 'Original textures displayed.' : `Overlay applied to ${count ?? 0} chunks.`)
            } catch (error) { this.message(`Material map failed: ${error.message}`, true) }
        })
        this.opacityInput.addEventListener('input', () => {
            const opacity = Number(this.opacityInput.value)
            this.opacityValue.textContent = `${Math.round(opacity * 100)}%`
            this.library.setOpacity(opacity)
        })
        this.runButton.addEventListener('click', () => this.runClassification())
    }

    async loadCatalog() {
        this.message('Loading available reconstructions...')
        try {
            const count = await this.library.loadManifest()
            this.message(count ? `${count} reconstructions available. Choose one to inspect.` : 'No reconstructions have been published yet.')
        } catch (error) {
            this.message(`Cannot load reconstruction catalog: ${error.message}`, true)
        }
    }

    async runClassification() {
        const name = this.library.activeName
        if (!name) { this.message('Load a reconstruction first.', true); return }

        this.runButton.disabled = true
        this.message(`Requesting classification for ${name}...`)

        try {
            const response = await fetch('/api/ml/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reconstruction: name, topology: true })
            })
            const result = await response.json().catch(() => ({}))
            if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`)
            await this.monitorJob(result.job_id)
        } catch (error) {
            this.message(`Classification unavailable: ${error.message}`, true)
        } finally {
            this.runButton.disabled = false
        }
    }

    async monitorJob(jobId) {
        while (true) {
            await new Promise(resolve => setTimeout(resolve, 3500))
            const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: 'no-store' })
            const job = await response.json().catch(() => ({}))
            if (!response.ok) throw new Error(job.detail || `Job status: HTTP ${response.status}`)

            const lastLine = (job.log_tail || '').trim().split(/\r?\n/).at(-1) || ''
            if (job.status === 'starting' || job.status === 'running') {
                this.message(`${job.status === 'starting' ? 'Starting' : 'Running'}: ${job.reconstruction} — ${lastLine || 'please wait...'}`)
                continue
            }

            if (job.status === 'completed') {
                if (job.catalog_updated) {
                    await this.library.loadManifest()
                    this.refresh()
                }
                this.message(job.warning || `Classification complete: ${job.reconstruction}. ${job.catalog_updated ? 'Material maps refreshed.' : 'Regenerate the catalog to view new maps.'}`)
                return
            }
            throw new Error(job.warning || `Classification failed (exit code ${job.exit_code}); check D:\\BEHOLDER\\job_logs\\${jobId}.log`)
        }
    }

    refresh() {
        const selected = this.modelSelect.value || this.library.activeName || ''
        this.modelSelect.replaceChildren(new Option('Select a reconstruction...', ''))
        for (const name of this.library.getReconstructions()) this.modelSelect.add(new Option(name.replace(/_ml_ready$/, ''), name))
        if ([...this.modelSelect.options].some(option => option.value === selected)) this.modelSelect.value = selected
        const map = this.library.activeVariant
        this.mapSelect.replaceChildren(...this.library.getVariants().map(v => new Option(v.label, v.value)))
        this.mapSelect.value = map
        this.mapSelect.disabled = !this.library.group
        this.renderStatistics()
    }

    renderStatistics() {
        this.materialStats.replaceChildren()
        const stats = this.library.materialStatistics
        if (!stats.length) {
            const empty = document.createElement('p')
            empty.className = 'stat-hint'
            empty.textContent = 'Select a material-ID map to see approximate UV texture coverage.'
            this.materialStats.append(empty)
            return
        }
        for (const item of stats) {
            const row = document.createElement('div')
            row.className = 'material-stat'
            const color = document.createElement('span')
            color.className = 'material-swatch'
            color.style.backgroundColor = `rgb(${item.color.join(',')})`
            const name = document.createElement('span')
            name.textContent = item.name
            const percent = document.createElement('strong')
            percent.textContent = `${item.percent.toFixed(1)}%`
            row.append(color, name, percent)
            this.materialStats.append(row)
        }
    }
}
