import argparse
import csv
from dataclasses import dataclass, field
import fnmatch
import hashlib
from pathlib import Path
import queue
import re
import threading
import textwrap

try:
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
except ImportError:
    raise SystemExit('Install the dependencies first: python -m pip install pillow reportlab')


LABELS = ('(a) Original UV texture', '(b) MINC', '(c) DMS', '(d) MatSynth', '(e) Soft ensemble')
KEYS = ('original', 'minc', 'dms', 'synth', 'ensemble')
PAGE_POINTS = (841.8898, 595.2756)
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'}
DEFAULT_MAP_NAME = 'material_id_superpixel_merged.png'
MAP_NAMES = (DEFAULT_MAP_NAME, 'material_id_topology_refined.png', 'material_id_superpixel_raw.png', 'material_id_tie_preview_raw.png')


@dataclass
class ComparisonJob:
    experiment: str
    dataset: str
    chunk: str
    paths: dict = field(default_factory=dict)
    issues: dict = field(default_factory=dict)
    state: str = 'Waiting'
    source_key: str = ''
    result_dirs: dict = field(default_factory=dict)
    manual_paths: set = field(default_factory=set)
    map_pattern: str = DEFAULT_MAP_NAME
    display_name: str = ''

    @property
    def title(self):
        return self.display_name.strip() or self.dataset

    @property
    def subtitle(self):
        match = re.match(r'^chunk_(\d+)', self.chunk, re.IGNORECASE)
        return f'Chunk {match.group(1)}' if match else self.chunk

    @property
    def ready(self):
        return all(self.paths.get(key) for key in KEYS)

    @property
    def description(self):
        if self.ready:
            return 'Ready'
        return '; '.join(f'{key}: {self.issues.get(key, "missing")}' for key in KEYS if not self.paths.get(key))


def configuration_kind(name):
    tokens = set(re.split(r'[^a-z0-9]+', name.casefold()))
    families = tokens & {'minc', 'dms'}
    if tokens & {'matsynth', 'synth'}:
        families.add('synth')
    if len(families) == 1:
        return next(iter(families))
    if families == {'minc', 'dms', 'synth'} and 'soft' in tokens:
        return 'ensemble'
    if name.casefold() in ('soft_ensemble', 'ensemble_soft'):
        return 'ensemble'
    return None


def normalized_dataset(name):
    name = re.sub(r'(?:[ _-]ml[ _-]ready)$', '', name, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9]', '', name.casefold())


def original_chunk_name(stem):
    stem = re.sub(r'_(?:diffuse|albedo|texture|basecolor)$', '', stem, flags=re.IGNORECASE)
    return stem.casefold()


def image_files(root):
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS:
            yield path


def select_map(candidates, pattern):
    matched = [path for path in candidates if fnmatch.fnmatchcase(path.name.casefold(), pattern.casefold())]
    if len(matched) > 1 and any(character in pattern for character in '*?['):
        matched = [path for path in matched if not any(word in path.stem.casefold() for word in ('boundaries', 'boundary', 'legend', 'mask'))]
    return matched


def apply_result_pattern(job, pattern):
    if not pattern.strip():
        raise ValueError('Choose the material-map filename to compare.')
    job.map_pattern = pattern
    for role in KEYS[1:]:
        if role in job.manual_paths:
            continue
        directories = job.result_dirs.get(role, [])
        if not directories and job.source_key:
            source = Path(job.source_key)
            if source.is_dir():
                directories = [config / job.chunk for config in source.iterdir() if config.is_dir() and configuration_kind(config.name) == role and (config / job.chunk).is_dir()]
                job.result_dirs[role] = directories
        candidates = []
        for directory in directories:
            if Path(directory).is_dir():
                candidates.extend(image_files(Path(directory)))
        matched = select_map(sorted(set(candidates)), pattern)
        job.paths.pop(role, None)
        job.issues.pop(role, None)
        if len(matched) == 1:
            job.paths[role] = matched[0]
        elif matched:
            job.issues[role] = f'{len(matched)} colour maps match {pattern}; select one'
        else:
            job.issues[role] = f'no file matching {pattern}'
    job.state = 'Waiting'
    return job


def refresh_queue_maps(jobs, pattern, cancel=None):
    for job in jobs:
        if cancel is not None and cancel.is_set():
            break
        apply_result_pattern(job, pattern)


def merge_queue(jobs, discovered):
    known = {(job.source_key or job.experiment, job.chunk): index for index, job in enumerate(jobs)}
    added = 0
    updated = 0
    for job in discovered:
        identity = (job.source_key or job.experiment, job.chunk)
        if identity not in known:
            jobs.append(job)
            known[identity] = len(jobs) - 1
            added += 1
        else:
            previous = jobs[known[identity]]
            if not job.display_name:
                job.display_name = previous.display_name
            job.manual_paths = set(previous.manual_paths)
            for key in previous.manual_paths:
                if key in previous.paths:
                    job.paths[key] = previous.paths[key]
                    job.issues.pop(key, None)
            if not job.paths.get('original') and previous.paths.get('original'):
                job.paths['original'] = previous.paths['original']
                job.issues.pop('original', None)
            jobs[known[identity]] = job
            updated += 1
    return added, updated


def name_discovered_jobs(jobs, display_name):
    if not display_name.strip():
        return
    if len({job.source_key or job.experiment for job in jobs}) > 1:
        raise ValueError('Several datasets were found. Leave Dataset name blank for a parent-folder scan, then use Edit selected to name each dataset.')
    for job in jobs:
        job.display_name = display_name.strip()


def discover_jobs(ml_root, originals_root, pattern=DEFAULT_MAP_NAME):
    ml_root = Path(ml_root).expanduser().resolve()
    originals_root = Path(originals_root).expanduser().resolve()
    if not ml_root.is_dir() or not originals_root.is_dir():
        raise ValueError('Select existing ML-results and original-texture folders.')
    if not pattern.strip():
        raise ValueError('Choose the result filename, for example material_id_superpixel_merged.png.')
    originals = {}
    for path in image_files(originals_root):
        originals.setdefault(original_chunk_name(path.stem), []).append(path)
    groups = {}
    for path in image_files(ml_root):
        relative = path.relative_to(ml_root)
        if any(part.casefold().startswith(('_topology_cache', '_uv_cache')) for part in relative.parts[:-1]):
            continue
        ancestry = [path.parent, *path.parent.parents]
        config = next((parent for parent in ancestry if configuration_kind(parent.name) and (parent == ml_root or ml_root in parent.parents)), None)
        if config is None:
            continue
        inside = path.relative_to(config)
        chunk = next((part for part in inside.parts[:-1] if re.match(r'^chunk_\d+', part, re.IGNORECASE)), None)
        if chunk is None:
            continue
        dataset_directory = config.parent
        experiment = str(dataset_directory.relative_to(ml_root)) if dataset_directory == ml_root or ml_root in dataset_directory.parents else dataset_directory.name
        if experiment == '.':
            experiment = dataset_directory.name
        group = groups.setdefault((experiment, chunk.casefold()), {'dataset': dataset_directory.name, 'directory': str(dataset_directory), 'chunk': chunk, 'directories': {}})
        role = configuration_kind(config.name)
        chunk_directory = config / Path(*inside.parts[:inside.parts.index(chunk) + 1])
        group['directories'].setdefault(role, set()).add(chunk_directory)
    jobs = []
    for (experiment, _), group in sorted(groups.items()):
        job = ComparisonJob(experiment, group['dataset'], group['chunk'], source_key=group['directory'])
        candidates = originals.get(job.chunk.casefold(), [])
        matched = []
        for candidate in candidates:
            directory_names = [candidate.parent.name, originals_root.name]
            directory_names.extend(part for part in candidate.relative_to(originals_root).parts[:-1])
            if any(normalized_dataset(name) == normalized_dataset(job.dataset) for name in directory_names):
                matched.append(candidate)
        if len(matched) == 1:
            job.paths['original'] = matched[0]
        elif matched:
            job.issues['original'] = f'{len(matched)} matching textures; select one'
        else:
            job.issues['original'] = 'no texture matched this dataset and chunk'
        job.result_dirs = {role: sorted(directories) for role, directories in group['directories'].items()}
        apply_result_pattern(job, pattern)
        jobs.append(job)
    return jobs


def safe_name(value):
    return re.sub(r'[^a-zA-Z0-9_.-]+', '_', value).strip('._') or 'comparison'


def job_output_base(output_root, job):
    identity = hashlib.sha256((job.source_key or job.experiment).encode('utf-8')).hexdigest()[:8]
    return Path(output_root) / f'{safe_name(job.experiment)[:90]}_{identity}' / safe_name(job.chunk)


def write_batch_report(output_root, jobs):
    destination = Path(output_root) / 'batch_report.csv'
    temporary = destination.with_suffix('.csv.tmp')
    with temporary.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=['experiment', 'dataset', 'dataset_display_name', 'chunk', 'map_filename', 'status', 'matching_notes', *KEYS])
        writer.writeheader()
        for job in jobs:
            writer.writerow({'experiment': job.experiment, 'dataset': job.dataset, 'dataset_display_name': job.display_name, 'chunk': job.chunk, 'map_filename': job.map_pattern, 'status': job.state, 'matching_notes': job.description, **{key: str(job.paths.get(key, '')) for key in KEYS}})
    temporary.replace(destination)
    return destination


def run_batch(jobs, output_root, layout='row', dpi=300, caption='', overwrite=False, combined=True, cancel=None, progress=None, refresh_pattern=None):
    if refresh_pattern is not None:
        refresh_queue_maps(jobs, refresh_pattern, cancel)
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        for source in job.paths.values():
            if output_root == Path(source).resolve().parent or output_root in Path(source).resolve().parents:
                raise ValueError('Choose a separate export folder outside the source-image folders.')
    successes = []
    combined_inputs = []
    for index, job in enumerate(jobs):
        if cancel is not None and cancel.is_set():
            for pending in jobs[index:]:
                pending.state = 'Cancelled'
            break
        if not job.ready:
            job.state = 'Needs attention'
        else:
            base = job_output_base(output_root, job)
            base = base.with_name(base.name + '_' + safe_name(Path(job.map_pattern).stem))
            destinations = [base.with_name(base.name + extension) for extension in ('.pdf', '.png')]
            if not overwrite and any(path.exists() for path in destinations):
                job.state = 'Skipped: output exists'
                if all(path.exists() for path in destinations):
                    combined_inputs.append(destinations[1])
            else:
                job.state = 'Exporting'
                if progress is not None:
                    progress(index, len(jobs), job)
                try:
                    results = export_comparison([job.paths[key] for key in KEYS], base, job.title, caption, layout, dpi, subtitle=job.subtitle)
                    successes.append(results)
                    combined_inputs.append(results[1])
                    job.state = 'Exported'
                except Exception as exc:
                    job.state = f'Failed: {exc}'
        write_batch_report(output_root, jobs)
        if progress is not None:
            progress(index + 1, len(jobs), job)
    report = write_batch_report(output_root, jobs)
    combined_path = None
    if combined and combined_inputs:
        combined_path = output_root / 'all_uv_comparisons.pdf'
        if combined_path.exists() and not overwrite:
            number = 2
            while (output_root / f'all_uv_comparisons_{number}.pdf').exists():
                number += 1
            combined_path = output_root / f'all_uv_comparisons_{number}.pdf'
        document = canvas.Canvas(str(combined_path), pagesize=PAGE_POINTS, pageCompression=1)
        document.setTitle('UV material classification comparisons')
        for path in combined_inputs:
            with Image.open(path) as page:
                document.drawImage(ImageReader(page), 0, 0, width=PAGE_POINTS[0], height=PAGE_POINTS[1])
                document.showPage()
        document.save()
    return successes, report, combined_path


def load_image(path):
    with Image.open(path) as source:
        source.load()
        if source.mode.startswith('I') or source.mode == 'F':
            raise ValueError(f'{Path(path).name}: use a colour-rendered map, rather than a numerical material-ID array.')
        return source.convert('RGBA')


def get_font(size, bold=False):
    names = (
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
        'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def wrapped_lines(draw, text, font, width):
    lines = []
    for paragraph in text.splitlines():
        current = ''
        for word in paragraph.split():
            candidate = f'{current} {word}'.strip()
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def fit_text(draw, text, width, max_lines, scale, start=16, minimum=8, bold=False):
    for size in range(start, minimum - 1, -1):
        font = get_font(max(1, round(size * scale)), bold)
        lines = wrapped_lines(draw, text, font, width)
        if len(lines) <= max_lines and all(draw.textlength(line, font=font) <= width for line in lines):
            return font, lines, round(size * scale * 1.4)
    raise ValueError('The title or caption is too long. Shorten it and export again.')


def render_page(images, title, caption='', layout='row', dpi=300, subtitle=''):
    if len(images) != 5:
        raise ValueError('Choose all five images: original, MINC, DMS, MatSynth and soft ensemble.')
    if not 72 <= dpi <= 600:
        raise ValueError('DPI must be between 72 and 600.')
    if layout not in ('row', 'two-rows'):
        raise ValueError('Layout must be row or two-rows.')
    scale = dpi / 72
    width, height = (round(value * scale) for value in PAGE_POINTS)
    page = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(page)
    margin = round(26 * scale)
    gap = round(12 * scale)
    title_font, title_lines, line_height = fit_text(draw, title or 'UV material classification comparison', width - 2 * margin, 2, scale, bold=True)
    title_y = margin
    for line in title_lines:
        draw.text((width / 2, title_y), line, font=title_font, fill='#202020', anchor='mt')
        title_y += line_height
    if subtitle:
        subtitle_font = get_font(round(11 * scale))
        draw.text((width / 2, title_y + round(2 * scale)), subtitle, font=subtitle_font, fill='#606060', anchor='mt')
        title_y += round(20 * scale)
    top = title_y + round(18 * scale)
    footer_lines = []
    if caption.strip():
        footer_font, footer_lines, footer_spacing = fit_text(draw, caption, width - 2 * margin, 3, scale, start=10)
    footer_height = len(footer_lines) * footer_spacing + round(14 * scale) if footer_lines else 0
    bottom = height - margin - footer_height
    groups = ((0, 1, 2, 3, 4),) if layout == 'row' else ((0, 1, 2), (3, 4))
    row_height = (bottom - top - gap * (len(groups) - 1)) / len(groups)
    label_height = round(26 * scale)
    columns = max(len(group) for group in groups)
    panel_width = (width - 2 * margin - gap * (columns - 1)) / columns
    label_font = get_font(round(11 * scale), True)
    for row, group in enumerate(groups):
        group_width = len(group) * panel_width + (len(group) - 1) * gap
        start_x = (width - group_width) / 2
        row_y = top + row * (row_height + gap)
        image_box_height = min(row_height - label_height, max(panel_width * images[index].height / images[index].width for index in group))
        content_y = row_y + (row_height - image_box_height - label_height) / 2
        for column, index in enumerate(group):
            x = start_x + column * (panel_width + gap)
            source = images[index]
            ratio = min(panel_width / source.width, image_box_height / source.height)
            resized_size = (max(1, round(source.width * ratio)), max(1, round(source.height * ratio)))
            method = Image.Resampling.LANCZOS if index == 0 else Image.Resampling.NEAREST
            resized = source.resize(resized_size, method)
            image_x = round(x + (panel_width - resized.width) / 2)
            image_y = round(content_y + (image_box_height - resized.height) / 2)
            page.paste(resized, (image_x, image_y), resized)
            draw.rectangle((image_x - 1, image_y - 1, image_x + resized.width, image_y + resized.height), outline='#bbbbbb', width=max(1, round(scale / 2)))
            label_y = content_y + image_box_height + round(8 * scale)
            draw.text((x + panel_width / 2, label_y), LABELS[index], font=label_font, fill='#202020', anchor='mt')
    if footer_lines:
        footer_y = height - margin - len(footer_lines) * footer_spacing
        for line in footer_lines:
            draw.text((margin, footer_y), line, font=footer_font, fill='#404040', anchor='lt')
            footer_y += footer_spacing
    return page


def export_comparison(paths, output, title, caption='', layout='row', dpi=300, subtitle=''):
    if len(paths) != 5 or not all(paths):
        raise ValueError('Choose an image for each of the five panels.')
    output = Path(output).expanduser()
    if output.suffix.lower() in ('.pdf', '.png'):
        output = output.with_suffix('')
    pdf_path = output.with_name(output.name + '.pdf')
    png_path = output.with_name(output.name + '.png')
    sources = [Path(path).expanduser().resolve() for path in paths]
    if any(destination.resolve() in sources for destination in (pdf_path, png_path)):
        raise ValueError('Choose a different export filename to avoid overwriting a source image.')
    images = [load_image(path) for path in sources]
    page = render_page(images, title, caption, layout, dpi, subtitle)
    output.parent.mkdir(parents=True, exist_ok=True)
    page.save(png_path, dpi=(dpi, dpi))
    document = canvas.Canvas(str(pdf_path), pagesize=PAGE_POINTS, pageCompression=1)
    document.setTitle((title or 'UV material classification comparison') + (f' - {subtitle}' if subtitle else ''))
    document.setSubject('Original UV texture, MINC, DMS, MatSynth and soft ensemble comparison')
    document.drawImage(ImageReader(page), 0, 0, width=PAGE_POINTS[0], height=PAGE_POINTS[1])
    document.showPage()
    document.save()
    return pdf_path, png_path


def build_batch_tab(root, parent):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import ImageTk
    ml_root = tk.StringVar()
    originals_root = tk.StringVar()
    output_root = tk.StringVar()
    dataset_name = tk.StringVar()
    pattern = tk.StringVar(value=DEFAULT_MAP_NAME)
    layout = tk.StringVar(value='row')
    dpi = tk.IntVar(value=300)
    caption = tk.StringVar()
    overwrite = tk.BooleanVar(value=False)
    combined = tk.BooleanVar(value=True)
    status = tk.StringVar(value='Select the parent ML-results folder and originals folder. Subfolders are scanned automatically.')
    jobs = []
    events = queue.Queue()
    cancellation = threading.Event()
    busy = [False]
    control_widgets = []
    settings = ttk.Frame(parent, padding=12)
    settings.pack(fill='x')
    settings.columnconfigure(1, weight=1)

    def choose_folder(variable):
        selected = filedialog.askdirectory()
        if selected:
            variable.set(selected)

    for row, (label, variable) in enumerate((('ML results parent folder:', ml_root), ('Original UV textures folder:', originals_root), ('Export folder:', output_root))):
        ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w', pady=3)
        entry = ttk.Entry(settings, textvariable=variable)
        entry.grid(row=row, column=1, sticky='ew', padx=8)
        button = ttk.Button(settings, text='Browse...', command=lambda v=variable: choose_folder(v))
        button.grid(row=row, column=2)
        control_widgets.extend((entry, button))
    ttk.Label(settings, text='Map filename (entire queue):').grid(row=3, column=0, sticky='w')
    pattern_entry = ttk.Combobox(settings, textvariable=pattern, values=MAP_NAMES)
    pattern_entry.grid(row=3, column=1, sticky='ew', padx=8, pady=5)

    def choose_pattern():
        selected = filedialog.askopenfilename(title='Choose one example merged colour map', filetypes=[('Images', '*.png *.jpg *.jpeg *.tif *.tiff'), ('All files', '*.*')])
        if selected:
            pattern.set(Path(selected).name)

    pattern_button = ttk.Button(settings, text='Use example filename...', command=choose_pattern)
    pattern_button.grid(row=3, column=2)
    control_widgets.extend((pattern_entry, pattern_button))
    ttk.Label(settings, text='Start entire queue scans the selected folders and applies this filename to EVERY queued dataset. Choose merged or topology-refined maps from the list.', wraplength=1100).grid(row=4, column=0, columnspan=3, sticky='w', pady=4)
    options = ttk.Frame(settings)
    options.grid(row=5, column=0, columnspan=3, sticky='ew', pady=8)
    for text, value in (('Five side by side', 'row'), ('Larger panels: 3 + 2', 'two-rows')):
        widget = ttk.Radiobutton(options, text=text, variable=layout, value=value)
        widget.pack(side='left', padx=(0, 14))
        control_widgets.append(widget)
    ttk.Label(options, text='DPI:').pack(side='left')
    dpi_widget = ttk.Combobox(options, textvariable=dpi, values=(150, 300, 600), state='readonly', width=6)
    dpi_widget.pack(side='left', padx=8)
    control_widgets.append(dpi_widget)
    for text, variable in (('Combined PDF', combined), ('Overwrite existing exports', overwrite)):
        widget = ttk.Checkbutton(options, text=text, variable=variable)
        widget.pack(side='left', padx=10)
        control_widgets.append(widget)
    ttk.Label(settings, text='Optional caption / settings:').grid(row=6, column=0, sticky='w')
    caption_widget = ttk.Entry(settings, textvariable=caption)
    caption_widget.grid(row=6, column=1, columnspan=2, sticky='ew', padx=8)
    control_widgets.append(caption_widget)
    ttk.Label(settings, text='Dataset name (optional):').grid(row=7, column=0, sticky='w', pady=7)
    name_widget = ttk.Entry(settings, textvariable=dataset_name)
    name_widget.grid(row=7, column=1, columnspan=2, sticky='ew', padx=8)
    control_widgets.append(name_widget)
    ttk.Label(settings, text='Used in the exported title. Chunk numbers are added automatically. For multiple datasets, name each through Edit selected.', wraplength=1100).grid(row=8, column=0, columnspan=3, sticky='w')
    table_frame = ttk.Frame(parent, padding=(12, 0, 12, 0))
    table_frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(table_frame, columns=('experiment', 'chunk', 'maps', 'matching', 'state'), show='headings', selectmode='extended')
    for column, title, width in (('experiment', 'Dataset / experiment', 280), ('chunk', 'Chunk', 180), ('maps', 'Maps', 55), ('matching', 'Matching status', 360), ('state', 'Export status', 160)):
        tree.heading(column, text=title)
        tree.column(column, width=width, minwidth=45, stretch=column in ('experiment', 'matching'))
    tree.tag_configure('ready', foreground='#18733a')
    tree.tag_configure('attention', foreground='#aa3020')
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    tree.configure(yscrollcommand=scrollbar.set)
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)

    def refresh():
        selected = set(tree.selection())
        tree.delete(*tree.get_children())
        for index, job in enumerate(jobs):
            tree.insert('', 'end', iid=str(index), values=(job.display_name or job.experiment, job.chunk, f'{sum(bool(job.paths.get(key)) for key in KEYS)}/5', job.description, job.state), tags=('ready' if job.ready else 'attention',))
        tree.selection_set([item for item in selected if tree.exists(item)])

    def set_busy(value):
        busy[0] = value
        for widget in control_widgets:
            widget.configure(state='disabled' if value else ('readonly' if widget is dpi_widget else 'normal'))
        stop_button.configure(state='normal' if value else 'disabled')

    def scan():
        if not ml_root.get().strip() or not originals_root.get().strip():
            messagebox.showinfo('Choose folders', 'Choose the ML-results and original-texture folders first.')
            return
        selected_ml, selected_originals, selected_pattern = ml_root.get(), originals_root.get(), pattern.get()
        selected_name = dataset_name.get()
        set_busy(True)
        status.set('Scanning folders and matching dataset/chunk names...')

        def worker():
            try:
                discovered = discover_jobs(selected_ml, selected_originals, selected_pattern)
                name_discovered_jobs(discovered, selected_name)
                counts = merge_queue(jobs, discovered)
                refresh_queue_maps(jobs, selected_pattern)
                events.put(('scan', counts))
            except Exception as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def edit_selected(event=None):
        if busy[0] or not tree.selection():
            return
        job = jobs[int(tree.selection()[0])]
        window = tk.Toplevel(root)
        window.title(f'Check matches - {job.dataset} / {job.chunk}')
        window.geometry('1000x440')
        window.transient(root)
        window.grab_set()
        window.columnconfigure(1, weight=1)
        variables = {key: tk.StringVar(value=str(job.paths.get(key, ''))) for key in KEYS}
        edit_name = tk.StringVar(value=job.display_name)
        ttk.Label(window, text='Confirm all five images belong to this dataset and chunk.', padding=10).grid(row=0, column=0, columnspan=3, sticky='w')
        ttk.Label(window, text='Dataset name:').grid(row=1, column=0, sticky='w', padx=10, pady=10)
        ttk.Entry(window, textvariable=edit_name).grid(row=1, column=1, sticky='ew')

        def browse_role(key):
            selected = filedialog.askopenfilename(parent=window, title=f'Choose {key} image', filetypes=[('Images', '*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp'), ('All files', '*.*')])
            if selected:
                variables[key].set(selected)

        for row, (key, label) in enumerate(zip(KEYS, LABELS), start=2):
            ttk.Label(window, text=label).grid(row=row, column=0, sticky='w', padx=10, pady=10)
            ttk.Entry(window, textvariable=variables[key]).grid(row=row, column=1, sticky='ew')
            ttk.Button(window, text='Browse...', command=lambda k=key: browse_role(k)).grid(row=row, column=2, padx=10)

        def save():
            for key, variable in variables.items():
                value = variable.get().strip()
                if value and not Path(value).is_file():
                    messagebox.showerror('Missing image', f'{key}: that file does not exist.', parent=window)
                    return
            for related in jobs:
                if (related.source_key or related.experiment) == (job.source_key or job.experiment):
                    related.display_name = edit_name.get().strip()
            for key, variable in variables.items():
                value = variable.get().strip()
                if value != str(job.paths.get(key, '')):
                    job.manual_paths.add(key)
                if value:
                    job.paths[key] = Path(value)
                    job.issues.pop(key, None)
                else:
                    job.paths.pop(key, None)
                    job.issues[key] = 'not selected'
            job.state = 'Waiting'
            refresh()
            window.destroy()
        ttk.Button(window, text='Save matches', command=save).grid(row=7, column=2, padx=10, pady=10)

    def remove_selected():
        for index in sorted((int(item) for item in tree.selection()), reverse=True):
            del jobs[index]
        refresh()

    def clear():
        jobs.clear()
        refresh()
        status.set('Queue cleared.')

    def preview_selected():
        if not tree.selection():
            return
        job = jobs[int(tree.selection()[0])]
        if not job.ready:
            messagebox.showinfo('Incomplete comparison', 'Edit this entry to choose the missing images first.')
            return
        try:
            page = render_page([load_image(job.paths[key]) for key in KEYS], job.title, caption.get(), layout.get(), 100, subtitle=job.subtitle)
            page.thumbnail((1150, 750), Image.Resampling.LANCZOS)
            window = tk.Toplevel(root)
            window.title('Comparison preview')
            photograph = ImageTk.PhotoImage(page)
            label = ttk.Label(window, image=photograph)
            label.image = photograph
            label.pack(padx=8, pady=8)
        except Exception as exc:
            messagebox.showerror('Preview failed', str(exc))

    def start():
        if not jobs and (not ml_root.get().strip() or not originals_root.get().strip()):
            messagebox.showinfo('Choose folders', 'Choose the ML-results and original-texture folders first. Start will scan and export them automatically.')
            return
        if not output_root.get().strip():
            choose_folder(output_root)
        if not output_root.get().strip():
            return
        selected_output = output_root.get()
        chosen_layout, chosen_dpi, chosen_caption = layout.get(), dpi.get(), caption.get()
        chosen_overwrite, chosen_combined = overwrite.get(), combined.get()
        selected_ml, selected_originals, selected_pattern = ml_root.get().strip(), originals_root.get().strip(), pattern.get().strip()
        selected_name = dataset_name.get()
        cancellation.clear()
        set_busy(True)
        progress_bar.configure(maximum=len(jobs), value=0)
        status.set('Refreshing the selected map across the entire queue, then exporting...')

        def progress(done, total, job):
            events.put(('progress', (done, total, job.experiment, job.chunk)))

        def worker():
            try:
                if selected_ml and selected_originals:
                    discovered = discover_jobs(selected_ml, selected_originals, selected_pattern)
                    name_discovered_jobs(discovered, selected_name)
                    merge_queue(jobs, discovered)
                if not jobs:
                    raise ValueError('No chunk-result folders were found. Check the ML-results parent folder.')
                results = run_batch(jobs, selected_output, chosen_layout, chosen_dpi, chosen_caption, chosen_overwrite, chosen_combined, cancellation, progress, refresh_pattern=selected_pattern)
                events.put(('complete', results))
            except Exception as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    buttons = ttk.Frame(parent, padding=12)
    buttons.pack(fill='x')
    for text, command in (('Scan / add to queue', scan), ('Edit selected', edit_selected), ('Preview selected', preview_selected), ('Remove selected', remove_selected), ('Clear queue', clear)):
        button = ttk.Button(buttons, text=text, command=command)
        button.pack(side='left', padx=(0, 6))
        control_widgets.append(button)
    start_button = ttk.Button(buttons, text='Start entire queue', command=start)
    start_button.pack(side='right')
    control_widgets.append(start_button)
    stop_button = ttk.Button(buttons, text='Stop after current image', state='disabled', command=cancellation.set)
    stop_button.pack(side='right', padx=8)
    progress_bar = ttk.Progressbar(parent)
    progress_bar.pack(fill='x', padx=12, pady=(0, 8))
    ttk.Label(parent, textvariable=status, wraplength=1200, padding=(12, 0, 12, 12)).pack(fill='x')
    tree.bind('<Double-1>', edit_selected)

    def process_events():
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == 'scan':
                    added, updated = payload
                    ready = sum(job.ready for job in jobs)
                    status.set(f'Added {added}, rescanned {updated}. Queue: {len(jobs)} total, {ready} ready, {len(jobs) - ready} need attention. Double-click an entry to check its files.')
                    refresh()
                    set_busy(False)
                elif kind == 'progress':
                    done, total, experiment, chunk = payload
                    progress_bar.configure(maximum=total, value=done)
                    status.set(f'{done}/{total}: {experiment} / {chunk}')
                    refresh()
                elif kind == 'complete':
                    successes, report, combined_file = payload
                    set_busy(False)
                    refresh()
                    attention = sum(job.state == 'Needs attention' for job in jobs)
                    failures = sum(job.state.startswith('Failed') for job in jobs)
                    skipped = sum(job.state.startswith('Skipped') for job in jobs)
                    summary = f'{len(successes)} exported, {skipped} already present, {attention} missing required maps, {failures} failed.'
                    status.set(f'Finished: {summary} Details: {report}')
                    messagebox.showinfo('Batch complete', f'{summary}\n\nBatch report:\n{report}' + (f'\n\nCombined PDF:\n{combined_file}' if combined_file else ''))
                elif kind == 'error':
                    set_busy(False)
                    refresh()
                    status.set('Operation stopped. Your queue is still available.')
                    messagebox.showerror('Operation failed', payload)
        except queue.Empty:
            pass
        root.after(150, process_events)
    root.after(150, process_events)


def launch_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        from PIL import ImageTk
    except ImportError:
        raise SystemExit('Tkinter is required for the selection window. Use a Python installation with Tk support, or use the command-line options shown by --help.')
    root = tk.Tk()
    root.title('BEHOLDER - UV map comparison v2 - whole-queue matching')
    root.geometry('1350x800')
    root.minsize(1050, 650)
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True)
    batch = ttk.Frame(notebook)
    single = ttk.Frame(notebook)
    notebook.add(batch, text='Folder batch queue')
    notebook.add(single, text='Single comparison')
    build_batch_tab(root, batch)
    title = tk.StringVar(value='Dataset name - UV material classification comparison')
    layout = tk.StringVar(value='row')
    dpi = tk.IntVar(value=300)
    status = tk.StringVar(value='Choose the five maps from the same dataset and UV atlas.')
    paths = [None] * 5
    images = [None] * 5
    photo_refs = [None] * 5
    file_labels = []
    image_labels = []
    details = []
    controls = ttk.Frame(single, padding=12)
    controls.pack(fill='x')
    ttk.Label(controls, text='Figure title:').grid(row=0, column=0, sticky='w')
    ttk.Entry(controls, textvariable=title).grid(row=0, column=1, columnspan=5, sticky='ew', padx=8)
    controls.columnconfigure(1, weight=1)
    ttk.Label(controls, text='Layout:').grid(row=1, column=0, sticky='w', pady=10)
    ttk.Radiobutton(controls, text='Five side by side', variable=layout, value='row').grid(row=1, column=1, sticky='w')
    ttk.Radiobutton(controls, text='Larger panels: 3 above, 2 below', variable=layout, value='two-rows').grid(row=1, column=2, sticky='w', padx=12)
    ttk.Label(controls, text='Export DPI:').grid(row=1, column=3)
    ttk.Combobox(controls, textvariable=dpi, values=(150, 300, 600), state='readonly', width=6).grid(row=1, column=4, padx=8)
    ttk.Label(controls, text='Caption / experiment settings (optional):').grid(row=2, column=0, columnspan=6, sticky='w')
    caption_box = tk.Text(controls, height=3, wrap='word')
    caption_box.grid(row=3, column=0, columnspan=6, sticky='ew', pady=5)
    preview_frame = ttk.Frame(single, padding=(12, 0, 12, 0))
    preview_frame.pack(fill='both', expand=True)

    def update_preview(event=None):
        panel_width = max(100, preview_frame.winfo_width() // 5 - 25)
        panel_height = max(100, preview_frame.winfo_height() - 140)
        for index, source in enumerate(images):
            if source is None:
                continue
            preview = source.copy()
            method = Image.Resampling.LANCZOS if index == 0 else Image.Resampling.NEAREST
            preview.thumbnail((panel_width, panel_height), method)
            background = Image.new('RGB', preview.size, 'white')
            background.paste(preview, mask=preview.getchannel('A'))
            photo_refs[index] = ImageTk.PhotoImage(background)
            image_labels[index].configure(image=photo_refs[index], text='')

    def browse(index):
        path = filedialog.askopenfilename(title=f'Choose {LABELS[index]}', filetypes=[('Images', '*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp'), ('All files', '*.*')])
        if not path:
            return
        try:
            source = load_image(path)
        except Exception as exc:
            messagebox.showerror('Could not load image', str(exc))
            return
        paths[index], images[index] = path, source
        file_labels[index].configure(text=textwrap.shorten(Path(path).name, width=30, placeholder='...'))
        details[index].configure(text=f'{source.width} x {source.height} pixels')
        status.set(f'{sum(path is not None for path in paths)}/5 maps loaded. Use colour-rendered maps with the same class palette and UV layout.')
        update_preview()

    def preview_page():
        if any(image is None for image in images):
            messagebox.showinfo('Choose all maps', 'Choose the original texture and all four result maps first.')
            return
        try:
            page = render_page(images, title.get(), caption_box.get('1.0', 'end').strip(), layout.get(), 100)
            page.thumbnail((1150, 750), Image.Resampling.LANCZOS)
            window = tk.Toplevel(root)
            window.title('Landscape export preview')
            photograph = ImageTk.PhotoImage(page)
            label = ttk.Label(window, image=photograph)
            label.image = photograph
            label.pack(padx=8, pady=8)
        except Exception as exc:
            messagebox.showerror('Preview failed', str(exc))

    def export():
        if any(path is None for path in paths):
            messagebox.showinfo('Choose all maps', 'Choose the original texture and all four result maps first.')
            return
        if len({image.size for image in images}) > 1:
            if not messagebox.askyesno('Different image dimensions', 'These maps have different pixel dimensions. They will retain their proportions, but the tool does not align or reproject UV layouts. Continue if they use the same atlas layout?'):
                return
        filename = filedialog.asksaveasfilename(title='Save comparison PDF and PNG', defaultextension='.pdf', initialfile='uv_comparison.pdf', filetypes=[('PDF', '*.pdf')])
        if not filename:
            return
        png_candidate = Path(filename).with_suffix('.png')
        if png_candidate.exists() and not messagebox.askyesno('Replace PNG?', f'{png_candidate.name} already exists. Replace it?'):
            return
        status.set('Exporting the comparison...')
        root.update_idletasks()
        try:
            pdf_path, png_path = export_comparison(paths, filename, title.get(), caption_box.get('1.0', 'end').strip(), layout.get(), dpi.get())
        except Exception as exc:
            status.set('Export failed; your selected images are still loaded.')
            messagebox.showerror('Export failed', str(exc))
            return
        status.set(f'Saved {pdf_path.name} and {png_path.name}')
        messagebox.showinfo('Export complete', f'Saved both files:\n{pdf_path}\n{png_path}')

    for index, label in enumerate(LABELS):
        preview_frame.columnconfigure(index, weight=1, uniform='panels')
        panel = ttk.LabelFrame(preview_frame, text=label, padding=8)
        panel.grid(row=0, column=index, sticky='nsew', padx=4)
        ttk.Button(panel, text='Choose image...', command=lambda i=index: browse(i)).pack(fill='x')
        file_label = ttk.Label(panel, text='Not loaded', anchor='center')
        file_label.pack(fill='x', pady=5)
        file_labels.append(file_label)
        detail_label = ttk.Label(panel, text='', anchor='center')
        detail_label.pack(fill='x')
        details.append(detail_label)
        image_label = ttk.Label(panel, text='UV map preview', anchor='center')
        image_label.pack(fill='both', expand=True, pady=8)
        image_labels.append(image_label)
    preview_frame.rowconfigure(0, weight=1)
    preview_frame.bind('<Configure>', update_preview)
    footer = ttk.Frame(single, padding=12)
    footer.pack(fill='x')
    ttk.Button(footer, text='Preview exported page', command=preview_page).pack(side='left')
    ttk.Button(footer, text='Export PDF + PNG', command=export).pack(side='right')
    ttk.Label(single, textvariable=status, padding=(12, 0, 12, 12), wraplength=1100).pack(fill='x')
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Select five UV maps in a window, or export them directly using the command-line options. Exports a landscape A4 PDF and PNG.')
    for key in KEYS:
        parser.add_argument(f'--{key}', type=Path, help=f'Path to the {key} image')
    parser.add_argument('--output', type=Path, help='Output filename without an extension, or a PDF filename')
    parser.add_argument('--title', default='UV material classification comparison')
    parser.add_argument('--caption', default='')
    parser.add_argument('--layout', choices=('row', 'two-rows'), default='row')
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--ml-root', type=Path, help='Parent ML-results folder for recursive batch discovery')
    parser.add_argument('--originals-root', type=Path, help='Original texture folder, scanned recursively')
    parser.add_argument('--output-dir', type=Path, help='Folder for batch PDF/PNG exports')
    parser.add_argument('--pattern', default=DEFAULT_MAP_NAME, help='Material-map filename or pattern for batch matching')
    parser.add_argument('--overwrite', action='store_true', help='Replace existing batch exports')
    parser.add_argument('--no-combined', action='store_true', help='Do not produce the combined multipage PDF')
    parser.add_argument('--dataset-name', default='', help='Friendly title for a batch containing one dataset; chunk numbers are automatic')
    args = parser.parse_args()
    paths = [getattr(args, key) for key in KEYS]
    if any(value is not None for value in (args.ml_root, args.originals_root, args.output_dir)):
        if args.ml_root is None or args.originals_root is None or args.output_dir is None:
            parser.error('Batch export requires --ml-root, --originals-root and --output-dir.')
        if any(paths) or args.output is not None:
            parser.error('Choose either batch-folder arguments or single-comparison arguments.')
        try:
            jobs = discover_jobs(args.ml_root, args.originals_root, args.pattern)
            name_discovered_jobs(jobs, args.dataset_name)
            print(f'Found {len(jobs)} comparisons; {sum(job.ready for job in jobs)} ready.')
            if not jobs:
                parser.exit(1, 'No chunk-result folders found. Expected dataset/model-configuration/chunk folders.\n')
            successes, report, combined_file = run_batch(jobs, args.output_dir, args.layout, args.dpi, args.caption, args.overwrite, not args.no_combined, progress=lambda done, total, job: print(f'{done}/{total}: {job.experiment}/{job.chunk}: {job.state}'))
        except Exception as exc:
            parser.exit(1, f'Batch failed: {exc}\n')
        print(f'Exported {len(successes)} new comparisons. Report: {report}')
        if combined_file:
            print(f'Combined PDF: {combined_file}')
    elif any(paths) or args.output is not None:
        if not all(paths) or args.output is None:
            parser.error('Command-line export requires --original, --minc, --dms, --synth, --ensemble and --output.')
        try:
            results = export_comparison(paths, args.output, args.title, args.caption, args.layout, args.dpi)
        except Exception as exc:
            parser.exit(1, f'Export failed: {exc}\n')
        for path in results:
            print(path.resolve())
    else:
        launch_gui()


if __name__ == '__main__':
    main()
