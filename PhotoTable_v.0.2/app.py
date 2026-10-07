from __future__ import annotations

import math
import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DRAG_AND_DROP = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    HAS_DRAG_AND_DROP = False


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATE_PATH = STATIC_DIR / "card.jpg"
FONT_PATH = STATIC_DIR / "arial.ttf"
OUTPUT_DIR = Path.home() / "Pictures" / "PhotoTable"

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SLOT_X = 330
SLOT_Y = 155
SLOT_WIDTH = 720
ROW_STEP = 1085
SLOT_HEIGHT = 930
SLOTS_PER_ROW = 4
PHOTOS_PER_SHEET = 8
NAME_POINTS = (
    (500, 1120), (1250, 1120), (1950, 1120), (2650, 1120),
    (500, 2190), (1250, 2190), (1950, 2190), (2650, 2190),
)


@dataclass
class PhotoRecord:
    path: Path
    name: str = ""


class PhotoTableApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PhotoTable v.0.2 — раскладка фотографий")
        self.root.geometry("1080x760")
        self.root.minsize(900, 600)
        self.root.configure(bg="#f4f6fa")

        self.photos: list[PhotoRecord] = []
        self.entry_vars: list[tk.StringVar] = []
        self.thumbnail_refs: list[ImageTk.PhotoImage] = []
        self.result_queue: queue.Queue[tuple] = queue.Queue()
        self.worker_running = False
        self.latest_output: Path | None = None

        self.output_var = tk.StringVar(value=str(OUTPUT_DIR))
        self.count_var = tk.StringVar(value="Фотографий: 0 · листов: 0")
        self.status_var = tk.StringVar(value=self._drop_hint())

        self._configure_style()
        self._build_layout()
        self._enable_drop_target()
        self._refresh_list()

    def _drop_hint(self) -> str:
        if HAS_DRAG_AND_DROP:
            return "Перетащите фотографии в окно или нажмите «+ Добавить фото»."
        return "Нажмите «+ Добавить фото», чтобы выбрать снимки."

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f6fa")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f4f6fa", foreground="#263247", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#152238")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#64748b")
        style.configure("Card.TLabel", background="#ffffff")
        style.configure("CardTitle.TLabel", background="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(13, 8))
        style.configure("TButton", padding=(9, 6))
        style.configure("TEntry", padding=6)
        style.configure("Status.TLabel", foreground="#526176")

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=(22, 18, 22, 14))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="PhotoTable", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Добавьте снимки, расставьте их по порядку и введите подписи рядом с миниатюрами.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 10))
        self.add_button = ttk.Button(toolbar, text="+ Добавить фото", command=self._choose_photos, style="Primary.TButton")
        self.add_button.pack(side="left")
        ttk.Button(toolbar, text="Добавить папку", command=self._choose_folder).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Очистить список", command=self._clear_list).pack(side="right")
        ttk.Label(toolbar, textvariable=self.count_var).pack(side="right", padx=(0, 14))

        list_shell = ttk.Frame(outer, style="Card.TFrame", padding=1)
        list_shell.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(list_shell, background="#f4f6fa", highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(list_shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = ttk.Frame(self.canvas, padding=(10, 10, 10, 10))
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_list_frame)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda _event: self.canvas.unbind_all("<MouseWheel>"))

        destination = ttk.Frame(outer)
        destination.pack(fill="x", pady=(13, 8))
        ttk.Label(destination, text="Папка для результатов").pack(side="left")
        self.output_entry = ttk.Entry(destination, textvariable=self.output_var)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(10, 8))
        ttk.Button(destination, text="Выбрать…", command=self._choose_output).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        self.generate_button = ttk.Button(
            bottom, text="Создать листы", command=self._start_generation, style="Primary.TButton"
        )
        self.generate_button.pack(side="left")
        self.open_button = ttk.Button(bottom, text="Открыть результат", command=self._open_result, state="disabled")
        self.open_button.pack(side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=190)
        self.progress.pack(side="right", padx=(12, 0))
        ttk.Label(bottom, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

    def _enable_drop_target(self) -> None:
        if not HAS_DRAG_AND_DROP:
            return
        for widget in (self.root, self.canvas, self.list_frame):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._handle_drop)
            except (AttributeError, tk.TclError):
                continue

    def _update_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_list_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.list_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _handle_drop(self, event: tk.Event) -> str:
        if not HAS_DRAG_AND_DROP:
            return "break"
        try:
            paths = self.root.tk.splitlist(event.data)
            self._add_paths(paths)
        except (tk.TclError, AttributeError):
            self.status_var.set("Не удалось прочитать перетаскиваемые файлы.")
        return "break"

    def _choose_photos(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Выберите фотографии",
            filetypes=[
                ("Изображения", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"),
                ("Все файлы", "*.*"),
            ],
        )
        if paths:
            self._add_paths(paths)

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Выберите папку с фотографиями")
        if folder:
            paths = sorted(
                (
                    path for path in Path(folder).iterdir()
                    if path.is_file() and path.suffix.lower() in PHOTO_EXTENSIONS
                ),
                key=lambda path: path.name.casefold(),
            )
            self._add_paths(paths)

    def _add_paths(self, paths) -> None:
        known = {str(record.path.resolve()).casefold() for record in self.photos}
        added = 0
        rejected: list[str] = []
        for raw_path in paths:
            path = Path(str(raw_path)).expanduser()
            if not path.is_file() or path.suffix.lower() not in PHOTO_EXTENSIONS:
                rejected.append(path.name or str(raw_path))
                continue
            try:
                resolved = path.resolve()
                key = str(resolved).casefold()
                if key in known:
                    continue
                with Image.open(resolved) as image:
                    image.verify()
                self.photos.append(PhotoRecord(resolved))
                known.add(key)
                added += 1
            except (OSError, ValueError, Image.DecompressionBombError):
                rejected.append(path.name)

        self._refresh_list()
        if rejected:
            self.status_var.set(f"Добавлено: {added}. Пропущено неподдерживаемых или повреждённых файлов: {len(rejected)}.")
            messagebox.showwarning(
                "Некоторые файлы пропущены",
                "Не удалось добавить эти файлы:\n\n" + "\n".join(rejected[:12])
                + ("\n…" if len(rejected) > 12 else ""),
                parent=self.root,
            )
        elif added:
            self.status_var.set(f"Добавлено фотографий: {added}.")

    def _capture_names(self) -> None:
        for record, variable in zip(self.photos, self.entry_vars):
            record.name = variable.get().strip()

    def _refresh_list(self, capture_names: bool = True) -> None:
        if capture_names:
            self._capture_names()
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.entry_vars.clear()
        self.thumbnail_refs.clear()

        if not self.photos:
            text = self._drop_hint()
            empty = ttk.Label(
                self.list_frame,
                text=text + "\n\nПоддерживаются JPG, PNG, BMP, TIFF и WebP.",
                anchor="center",
                justify="center",
                foreground="#758198",
                padding=(20, 60),
            )
            empty.pack(fill="both", expand=True)
            self._register_drop(empty)
        else:
            for index, record in enumerate(self.photos):
                self._add_photo_row(index, record)

        pages = math.ceil(len(self.photos) / PHOTOS_PER_SHEET) if self.photos else 0
        self.count_var.set(f"Фотографий: {len(self.photos)} · листов: {pages}")
        self.generate_button.configure(state="normal" if self.photos and not self.worker_running else "disabled")
        self.canvas.yview_moveto(0)
        self._update_scroll_region()

    def _register_drop(self, widget: tk.Widget) -> None:
        if not HAS_DRAG_AND_DROP:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._handle_drop)
        except (AttributeError, tk.TclError):
            pass

    def _add_photo_row(self, index: int, record: PhotoRecord) -> None:
        row = ttk.Frame(self.list_frame, style="Card.TFrame", padding=10)
        row.pack(fill="x", pady=(0, 8))

        try:
            with Image.open(record.path) as source:
                preview = ImageOps.exif_transpose(source).convert("RGB")
                resampling = getattr(Image, "Resampling", Image).LANCZOS
                preview.thumbnail((136, 96), resampling)
                thumbnail = ImageTk.PhotoImage(preview)
        except (OSError, ValueError):
            thumbnail = None
        self.thumbnail_refs.append(thumbnail)

        image_box = tk.Label(row, image=thumbnail, width=138, height=98, background="#eef1f6", relief="flat")
        image_box.pack(side="left", padx=(0, 12))
        info = ttk.Frame(row, style="Card.TFrame")
        info.pack(side="left", fill="both", expand=True)
        ttk.Label(info, text=record.path.name, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(info, text=str(record.path.parent), style="Card.TLabel", foreground="#718096").pack(anchor="w", pady=(2, 8))
        ttk.Label(info, text="Подпись на листе", style="Card.TLabel").pack(anchor="w")
        variable = tk.StringVar(value=record.name)
        self.entry_vars.append(variable)
        entry = ttk.Entry(info, textvariable=variable)
        entry.pack(fill="x", pady=(3, 0))

        controls = ttk.Frame(row, style="Card.TFrame")
        controls.pack(side="right", padx=(12, 0))
        ttk.Button(
            controls, text="↑", width=3, command=lambda i=index: self._move_photo(i, -1),
            state="normal" if index > 0 else "disabled",
        ).pack(pady=(0, 4))
        ttk.Button(
            controls, text="↓", width=3, command=lambda i=index: self._move_photo(i, 1),
            state="normal" if index < len(self.photos) - 1 else "disabled",
        ).pack(pady=(0, 4))
        ttk.Button(controls, text="Удалить", command=lambda i=index: self._remove_photo(i)).pack()
        for widget in (row, image_box, info):
            self._register_drop(widget)

    def _move_photo(self, index: int, direction: int) -> None:
        self._capture_names()
        target = index + direction
        if 0 <= target < len(self.photos):
            self.photos[index], self.photos[target] = self.photos[target], self.photos[index]
            self._refresh_list(capture_names=False)

    def _remove_photo(self, index: int) -> None:
        self._capture_names()
        del self.photos[index]
        self._refresh_list(capture_names=False)
        self.status_var.set("Фотография удалена из списка.")

    def _clear_list(self) -> None:
        if not self.photos:
            return
        if messagebox.askyesno("Очистить список", "Удалить все фотографии из текущего списка?", parent=self.root):
            self.photos.clear()
            self._refresh_list(capture_names=False)
            self.status_var.set(self._drop_hint())

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Куда сохранить листы")
        if folder:
            self.output_var.set(folder)

    def _start_generation(self) -> None:
        self._capture_names()
        if not self.photos:
            messagebox.showinfo("Нет фотографий", "Сначала добавьте хотя бы одну фотографию.", parent=self.root)
            return
        if not TEMPLATE_PATH.is_file():
            messagebox.showerror("Не найден шаблон", f"Файл шаблона не найден:\n{TEMPLATE_PATH}", parent=self.root)
            return

        output_value = self.output_var.get().strip()
        if not output_value:
            messagebox.showerror("Не выбрана папка", "Укажите папку для сохранения результата.", parent=self.root)
            return
        output_root = Path(output_value).expanduser()
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            run_folder = self._new_run_folder(output_root)
        except OSError as error:
            messagebox.showerror("Не удалось создать папку", str(error), parent=self.root)
            return

        records = [(record.path, record.name) for record in self.photos]
        total_pages = math.ceil(len(records) / PHOTOS_PER_SHEET)
        self.worker_running = True
        self.generate_button.configure(state="disabled")
        self.progress.configure(maximum=total_pages, value=0)
        self.status_var.set("Подготовка листов…")

        def worker() -> None:
            try:
                create_sheets(records, run_folder, self.result_queue)
                self.result_queue.put(("done", str(run_folder), total_pages))
            except Exception as error:  # Report file and image errors in the UI.
                self.result_queue.put(("error", str(error)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll_worker)

    @staticmethod
    def _new_run_folder(output_root: Path) -> Path:
        base = output_root / f"PhotoTable_{datetime.now():%Y%m%d_%H%M%S}"
        candidate = base
        suffix = 1
        while candidate.exists():
            candidate = output_root / f"{base.name}_{suffix}"
            suffix += 1
        candidate.mkdir()
        return candidate

    def _poll_worker(self) -> None:
        try:
            while True:
                item = self.result_queue.get_nowait()
                if item[0] == "progress":
                    _, completed, total = item
                    self.progress.configure(value=completed)
                    self.status_var.set(f"Создаю лист {completed} из {total}…")
                elif item[0] == "done":
                    _, output, total = item
                    self.worker_running = False
                    self.latest_output = Path(output)
                    self.generate_button.configure(state="normal" if self.photos else "disabled")
                    self.open_button.configure(state="normal")
                    self.status_var.set(f"Готово: создано листов {total}.")
                    messagebox.showinfo(
                        "Листы готовы",
                        f"Создано листов: {total}\n\nПапка с результатом:\n{output}",
                        parent=self.root,
                    )
                elif item[0] == "error":
                    self.worker_running = False
                    self.generate_button.configure(state="normal" if self.photos else "disabled")
                    self.status_var.set("Не удалось создать листы.")
                    messagebox.showerror("Ошибка создания", item[1], parent=self.root)
        except queue.Empty:
            pass
        if self.worker_running:
            self.root.after(100, self._poll_worker)

    def _open_result(self) -> None:
        if not self.latest_output or not self.latest_output.exists():
            messagebox.showinfo("Нет результата", "Сначала создайте листы.", parent=self.root)
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self.latest_output))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.latest_output)])
            else:
                subprocess.Popen(["xdg-open", str(self.latest_output)])
        except OSError as error:
            messagebox.showerror("Не удалось открыть папку", str(error), parent=self.root)


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> ImageFont.FreeTypeFont:
    size = 100
    while size > 24:
        font = ImageFont.truetype(str(FONT_PATH), size=size)
        bounds = draw.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] <= max_width:
            return font
        size -= 4
    return ImageFont.truetype(str(FONT_PATH), size=24)


def create_sheets(records: list[tuple[Path, str]], output_folder: Path, progress_queue: queue.Queue) -> None:
    with Image.open(TEMPLATE_PATH) as source_template:
        template = source_template.convert("RGB")
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    pages = math.ceil(len(records) / PHOTOS_PER_SHEET)

    for page_index in range(pages):
        sheet = template.copy()
        page_records = records[page_index * PHOTOS_PER_SHEET:(page_index + 1) * PHOTOS_PER_SHEET]
        draw = ImageDraw.Draw(sheet)

        for local_index, (photo_path, name) in enumerate(page_records):
            slot_index = local_index
            row, column = divmod(slot_index, SLOTS_PER_ROW)
            slot_x = SLOT_X + column * SLOT_WIDTH
            slot_y = SLOT_Y + row * ROW_STEP

            with Image.open(photo_path) as source:
                photo = ImageOps.exif_transpose(source).convert("RGB")
                original_width, original_height = photo.size
                scale = min(SLOT_WIDTH / original_width, SLOT_HEIGHT / original_height)
                resized_size = (max(1, round(original_width * scale)), max(1, round(original_height * scale)))
                photo = photo.resize(resized_size, resampling)
            paste_x = slot_x + (SLOT_WIDTH - photo.width) // 2
            paste_y = slot_y + (SLOT_HEIGHT - photo.height) // 2
            sheet.paste(photo, (paste_x, paste_y))

            if name:
                name_x, name_y = NAME_POINTS[local_index]
                font = fit_font(draw, name, max_width=650)
                draw.text((name_x, name_y), name, fill="black", font=font)

        output_path = output_folder / f"photo_table_{page_index + 1:02d}.jpg"
        sheet.save(output_path, format="JPEG", quality=95, subsampling=0)
        progress_queue.put(("progress", page_index + 1, pages))


def main() -> None:
    root = TkinterDnD.Tk() if HAS_DRAG_AND_DROP else tk.Tk()
    PhotoTableApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
