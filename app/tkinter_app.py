"""Exam Behavior Review desktop interface. All Tk operations stay on the UI thread."""
import queue
import math
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageTk, ImageOps

from src.config import ROOT
from src.pipeline import process_video
from .db import AlertDatabase
from .history import AlertHistory
from .playback import PlaybackControl
from .presentation import (apply_theme, behavior_label, behavior_color, local_timestamp,
                           NAVY, BACKGROUND, PAPER, INK, MUTED, BORDER, PREVIEW, DANGER)


TITLE = 'Exam Behavior Review'
DISCLAIMER = ('Alerts are automated observations for human review — not proof of misconduct. '
              'Scores are heuristic, not probabilities.')


class CheatingAlertApp:
    def __init__(self, root, output=None):
        self.root = root
        self.style = apply_theme(root)
        self.events = queue.Queue()  # Persisted events/errors are never dropped.
        self.frames = queue.Queue(maxsize=1)  # Only the display may skip stale frames.
        self.control = PlaybackControl()
        self.stop = self.control.stop
        self.worker = None
        self.running = False
        self.phase = 'idle'
        self.closing = False
        self.clear_pending = False
        self.video_path = None
        self.preview_image = None
        self.screenshot_image = None
        self.screenshot_previous_status = None
        self.photo = self.screenshot_photo = None
        self.toasts = {}
        self.toast_number = 0
        self.after_ids = set()
        self.about_window = None
        self.last_result = None
        self.replay_capture = None
        self.replay_token = None
        self.replay_index = 0
        self.output = Path(output) if output is not None else ROOT / 'alerts'
        self.db = None
        self.status = tk.StringVar(root, value='Ready')
        self.progress_text = tk.StringVar(root, value='0%  ·  0 / 0 frames')
        self.source_text = tk.StringVar(root, value='No video selected')
        self.history_count = tk.StringVar(root, value='0 observations')
        self.screenshot_caption = tk.StringVar(root, value='')
        root.title(TITLE)
        root.geometry('1280x780')
        root.minsize(1100, 650)
        root.resizable(True, True)
        self._set_icon(root)
        self._build_layout()
        try:
            self.db = AlertDatabase(self.output / 'cheating_alerts.db')
            self.refresh_history()
        except Exception as exc:
            self._set_status(f'History unavailable: {exc}', error=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._update_controls()
        self._later(30, self.poll)

    def _later(self, delay, callback):
        token = None
        def invoke():
            self.after_ids.discard(token)
            callback()
        token = self.root.after(delay, invoke)
        self.after_ids.add(token)
        return token

    def _set_icon(self, window):
        path = ROOT / 'assets' / 'exam_review.ico'
        if path.exists():
            try:
                window.iconbitmap(str(path))
            except tk.TclError:
                pass  # Window managers without ICO support still get a working app.

    @staticmethod
    def _label(parent, text='', **kwargs):
        return tk.Label(parent, autostyle=False, text=text, bg=kwargs.pop('bg', BACKGROUND),
                        fg=kwargs.pop('fg', INK), font=kwargs.pop('font', ('Segoe UI', 10)),
                        **kwargs)

    def _build_layout(self):
        heading = ttk.Frame(self.root, padding=(24, 18, 24, 8))
        heading.pack(fill='x')
        self._label(heading, TITLE, fg=NAVY, font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        self._label(heading, 'A considered view of the exam room', fg=MUTED).pack(anchor='w', pady=(2, 0))
        toolbar = ttk.Frame(self.root, padding=(24, 8, 24, 16))
        toolbar.pack(fill='x')
        self.upload = ttk.Button(toolbar, text='📂  Upload Video', command=self.open_video, bootstyle='primary')
        self.upload.pack(side='left', padx=(0, 8))
        self.play = ttk.Button(toolbar, text='▶  Play', command=self.toggle_play, bootstyle='primary-outline', width=10)
        self.play.pack(side='left', padx=(0, 8))
        self.stop_button = ttk.Button(toolbar, text='⏹  Stop', command=self.request_stop, bootstyle='secondary-outline')
        self.stop_button.pack(side='left', padx=(0, 8))
        self.clear_button = ttk.Button(toolbar, text='✕  Clear', command=self.clear, bootstyle='secondary-outline')
        self.clear_button.pack(side='left')
        self.about_button = ttk.Button(toolbar, text='ⓘ  About', command=self.show_about, bootstyle='secondary-outline')
        self.about_button.pack(side='right')

        footer = tk.Frame(self.root, autostyle=False, bg='#EAEDEB', padx=24, pady=10)
        footer.pack(side='bottom', fill='x')
        self.disclaimer = self._label(footer, DISCLAIMER, bg='#EAEDEB', fg='#586575', font=('Segoe UI', 9), anchor='w')
        self.disclaimer.pack(fill='x')
        self.status_bar = self._label(self.root, textvariable=self.status, anchor='w', padx=24, pady=10)
        self.status_bar.pack(side='bottom', fill='x')
        self.status_bar.bind('<Configure>', lambda e: self.status_bar.configure(wraplength=max(100, e.width - 48)))

        body = ttk.Frame(self.root, padding=(24, 0, 24, 0))
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1, minsize=440)
        body.columnconfigure(1, weight=1, minsize=560)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, autostyle=False, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        preview_header = tk.Frame(left, autostyle=False, bg=PAPER, padx=16, pady=12)
        preview_header.grid(row=0, column=0, sticky='ew')
        self._label(preview_header, 'Video Preview', bg=PAPER, font=('Segoe UI', 11, 'bold')).pack(side='left')
        self.fullscreen_button = ttk.Button(preview_header, text='⛶  Full screen', bootstyle='secondary-link', command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side='right')
        self.preview = tk.Canvas(left, autostyle=False, bg=PREVIEW, highlightthickness=0)
        self.preview.grid(row=1, column=0, sticky='nsew', padx=12)
        self.preview.bind('<Configure>', lambda _: self._draw_preview())
        progress_area = tk.Frame(left, autostyle=False, bg=PAPER, padx=16, pady=14)
        progress_area.grid(row=2, column=0, sticky='ew')
        self.progress = ttk.Progressbar(progress_area, mode='determinate', maximum=100, bootstyle='primary')
        self.progress.pack(fill='x', pady=(0, 9))
        line = tk.Frame(progress_area, autostyle=False, bg=PAPER)
        line.pack(fill='x')
        self.source_label = self._label(line, textvariable=self.source_text, bg=PAPER, fg=MUTED, font=('Segoe UI', 9), anchor='w')
        self.source_label.pack(side='left', fill='x', expand=True)
        self.source_label.bind('<Configure>', lambda e: self.source_label.configure(wraplength=max(60, e.width)))
        self._label(line, textvariable=self.progress_text, bg=PAPER, fg=MUTED, font=('Segoe UI', 9)).pack(side='right', padx=(12, 0))

        right = tk.Frame(body, autostyle=False, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right_header = tk.Frame(right, autostyle=False, bg=PAPER, padx=16, pady=12)
        right_header.grid(row=0, column=0, sticky='ew')
        self._label(right_header, 'Alert History', bg=PAPER, font=('Segoe UI', 11, 'bold')).pack(side='left')
        self.clear_logs_button = ttk.Button(right_header, text='🗑  Clear Logs', command=self.clear_database_logs, bootstyle='secondary-link')
        self.clear_logs_button.pack(side='right')
        self._label(right_header, textvariable=self.history_count, bg=PAPER, fg=MUTED, font=('Segoe UI', 9)).pack(side='right', padx=(0, 10))
        self.history = AlertHistory(right, self.view_screenshot)
        self.history.grid(row=1, column=0, sticky='nsew', padx=12)
        self.history_hint = self._label(right, 'Select an observation to review its saved screenshot.', bg=PAPER,
                                       fg=MUTED, font=('Segoe UI', 9), anchor='w', padx=16, pady=12)
        self.history_hint.grid(row=2, column=0, sticky='ew')
        self.screenshot_panel = tk.Frame(right, autostyle=False, bg=PAPER, padx=12, pady=8)
        self.screenshot_panel.grid(row=3, column=0, sticky='nsew')
        right.rowconfigure(3, weight=1)
        self.screenshot_panel.columnconfigure(0, weight=1)
        self.screenshot_panel.rowconfigure(1, weight=1)
        self._label(self.screenshot_panel, 'Screenshot Preview', bg=PAPER,
                    font=('Segoe UI', 11, 'bold'), anchor='w').grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.screenshot = tk.Canvas(self.screenshot_panel, autostyle=False, bg=PREVIEW, highlightthickness=0, height=200)
        self.screenshot.grid(row=1, column=0, sticky='nsew')
        self.screenshot.bind('<Configure>', lambda _: self._draw_screenshot())
        caption = self._label(self.screenshot_panel, textvariable=self.screenshot_caption, bg=PAPER,
                              fg=MUTED, font=('Segoe UI', 9), anchor='w', justify='left')
        caption.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        caption.bind('<Configure>', lambda e: caption.configure(wraplength=max(100, e.width)))
        self.screenshot_panel.grid_remove()
        right.rowconfigure(3, weight=0)
        self.right_panel = right
        self.toast_host = tk.Frame(self.preview, autostyle=False, bg=PREVIEW)
        self._draw_preview()

    def _set_status(self, text, error=False):
        self.status.set(text)
        self.status_bar.configure(bg='#F8E7E4' if error else BACKGROUND,
                                  fg=DANGER if error else MUTED)

    def _update_controls(self):
        loading = self.phase == 'loading'
        stopping = self.phase == 'stopping' or self.closing
        self.upload.configure(state='disabled' if self.running or self.closing else 'normal')
        can_replay = (self.phase == 'complete' and self.last_result and
                      not self.last_result.get('cancelled', True) and
                      bool(self.last_result.get('output_directory')))
        playing = self.phase in ('processing', 'paused', 'pausing', 'replaying', 'replay_paused')
        self.play.configure(state='normal' if (playing or can_replay) and not stopping else 'disabled',
                            text='⏸  Pause' if self.phase in ('processing', 'replaying') else '▶  Play')
        self.stop_button.configure(state='normal' if (self.running or self.phase in ('replaying', 'replay_paused')) and not stopping else 'disabled')
        self.clear_button.configure(state='disabled' if loading or self.closing else 'normal')
        self.about_button.configure(state='disabled' if loading or self.closing else 'normal')
        self.fullscreen_button.configure(state='disabled' if loading or self.closing else 'normal')
        self.clear_logs_button.configure(state='disabled' if self.running or loading or self.closing else 'normal')

    def open_video(self):
        if self.running or self.closing:
            return
        path = filedialog.askopenfilename(parent=self.root, title='Choose an exam video',
                                         filetypes=[('Videos', '*.mp4 *.avi *.mov')])
        if path:
            self.start_video(path)

    def start_video(self, path):
        if self.running or self.closing:
            return
        self._release_replay()
        self._empty_queues()
        self._dismiss_toasts()
        self.control = PlaybackControl()
        self.stop = self.control.stop
        self.video_path = Path(path)
        self.clear_pending = False
        self.last_result = None
        self.running = True
        self.phase = 'loading'
        self.preview_image = None
        self.photo = None
        self._draw_preview()
        self.source_text.set(self.video_path.name)
        self.root.title(f'{TITLE} — {self.video_path.name}')
        self.progress.configure(mode='indeterminate', value=0)
        self.progress.start(12)
        self.progress_text.set('Loading…')
        self._set_status('Loading models…')
        self._update_controls()
        control = self.control

        def callback(kind, value):
            if kind == 'frame':
                try:
                    self.frames.get_nowait()
                except queue.Empty:
                    pass
                self.frames.put_nowait(value)
                control.frame_boundary(lambda: self.events.put(('paused', None)))
            else:
                self.events.put((kind, value))

        def run():
            try:
                result = process_video(path, self.output, callback=callback, stop=control.stop)
                self.events.put(('complete', result))
            except Exception as exc:
                self.events.put(('error', str(exc)))

        self.worker = threading.Thread(target=run, name='exam-video-review', daemon=False)
        self.worker.start()

    def toggle_play(self):
        if self.phase == 'complete':
            self._begin_replay()
        elif self.phase == 'replaying':
            self._cancel_replay_timer()
            self.phase = 'replay_paused'
            self._set_status('Replay paused — select Play to continue')
        elif self.phase == 'replay_paused':
            self.phase = 'replaying'
            self.replay_started = time.monotonic() - self.replay_index / self.replay_fps
            self._set_status('Replaying saved video…')
            self._replay_tick()
        elif self.phase == 'processing':
            self.control.pause()
            self.phase = 'pausing'
            self._set_status('Pausing after the current frame…')
        elif self.phase in ('paused', 'pausing'):
            self.control.resume()
            self.phase = 'processing'
            self._set_status('Processing video…')
        self._update_controls()

    def _cancel_replay_timer(self):
        if self.replay_token is not None:
            self.root.after_cancel(self.replay_token)
            self.after_ids.discard(self.replay_token)
            self.replay_token = None

    def _release_replay(self):
        self._cancel_replay_timer()
        if self.replay_capture is not None:
            self.replay_capture.release()
            self.replay_capture = None

    def _begin_replay(self):
        result = self.last_result
        if self.closing or not result or result.get('cancelled', True) or not result.get('output_directory'):
            return
        self._release_replay()
        self._dismiss_toasts()
        try:
            import cv2
            path = Path(result['output_directory']) / 'annotated.mp4'
            self.replay_capture = cv2.VideoCapture(str(path))
            if not self.replay_capture.isOpened():
                raise OSError('The saved annotated video could not be opened.')
            self.replay_fps = self.replay_capture.get(cv2.CAP_PROP_FPS)
            self.replay_total = int(self.replay_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if not math.isfinite(self.replay_fps) or self.replay_fps <= 0 or self.replay_total <= 0:
                raise OSError('The saved video has invalid playback information.')
            self.replay_index = 0
            self.replay_started = time.monotonic()
            self.phase = 'replaying'
            self._set_status('Replaying saved video…')
            self._replay_tick()
        except Exception as exc:
            self._release_replay()
            self.phase = 'complete'
            self._set_status(f'Unable to replay video: {exc}', error=True)
        self._update_controls()

    def _replay_tick(self):
        self.replay_token = None
        if self.phase != 'replaying' or self.closing or self.replay_capture is None:
            return
        try:
            ok, frame = self.replay_capture.read()
            if not ok:
                if self.replay_index < self.replay_total:
                    raise OSError('The saved video ended before all frames could be read.')
                self._release_replay()
                self.phase = 'complete'
                self._set_status('Replay complete — select Play to replay')
                self._update_controls()
                return
            self.replay_index += 1
            self.preview_image = Image.fromarray(frame[:, :, ::-1])
            self._draw_preview()
            percent = min(100, self.replay_index / self.replay_total * 100)
            self.progress.configure(value=percent)
            self.progress_text.set(f'{percent:.0f}%  ·  {self.replay_index:,} / {self.replay_total:,} frames')
            delay = max(1, round(1000 * (self.replay_started + self.replay_index / self.replay_fps - time.monotonic())))
            self.replay_token = self._later(delay, self._replay_tick)
        except Exception as exc:
            self._release_replay()
            self.phase = 'complete'
            self._set_status(f'Unable to replay video: {exc}', error=True)
            self._update_controls()

    def request_stop(self):
        if self.phase in ('replaying', 'replay_paused'):
            self._release_replay()
            self.phase = 'complete'
            self._set_status('Replay stopped — select Play to replay from the beginning')
            self._update_controls()
            return
        if not self.running:
            return
        self.control.cancel()  # Always wakes a paused worker.
        self.phase = 'stopping'
        self.progress.stop()
        self._set_status('Stopping processing safely…')
        self._update_controls()

    def clear(self):
        if self.closing or self.phase == 'loading':
            return
        self._release_replay()
        self.last_result = None
        if self.running:
            self.clear_pending = True
            self.request_stop()
        else:
            self.phase = 'idle'
        self.preview_image = self.photo = None
        self.video_path = None
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self.progress_text.set('0%  ·  0 / 0 frames')
        self.source_text.set('No video selected')
        self.root.title(TITLE)
        self._dismiss_toasts()
        self._set_status('Ready')
        self._draw_preview()
        self._update_controls()

    def _empty_queues(self):
        for pending in (self.frames, self.events):
            while True:
                try:
                    pending.get_nowait()
                except queue.Empty:
                    break

    def _consume_frame(self):
        try:
            frame, index, total = self.frames.get_nowait()
        except queue.Empty:
            return
        if self.clear_pending or self.closing:
            return
        if self.phase == 'loading':
            self.phase = 'processing'
            self.progress.stop()
            self.progress.configure(mode='determinate', value=0)
            self._set_status('Processing video…')
            self._update_controls()
        self.preview_image = Image.fromarray(frame[:, :, ::-1])
        self._draw_preview()
        percent = min(100, index / total * 100) if total > 0 else 0
        self.progress.configure(value=percent)
        self.progress_text.set(f'{percent:.0f}%  ·  {index:,} / {total:,} frames' if total > 0 else f'{index:,} frames · total unknown')

    def poll(self):
        self._consume_frame()
        # Bound each UI turn so a burst of notifications cannot starve the mouse.
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'event':
                self.history.add_record(value)
                self._update_count()
                if not self.clear_pending and not self.closing:
                    self._show_toast(value)
            elif kind == 'paused' and self.control.paused and self.phase == 'pausing':
                self._consume_frame()
                self.phase = 'paused'
                self._set_status('Paused — select Play to continue')
                self._update_controls()
            elif kind in ('complete', 'error'):
                self._consume_frame()  # Keep the final frame even if completion won the queue race.
                self._finish(kind, value)
        if self.closing and not (self.worker and self.worker.is_alive()):
            self._destroy()
            return
        self._later(30, self.poll)

    def _finish(self, kind, value):
        self.running = False
        self.progress.stop()
        self.progress.configure(mode='determinate')
        self.root.title(TITLE)
        if kind == 'error':
            self.phase = 'error'
            self._set_status(f'Unable to process video: {value}', error=True)
            if self.preview_image is None:
                self.progress.configure(value=0)
                self.progress_text.set('0%  ·  0 / 0 frames')
        else:
            self.last_result = value
            self.phase = 'idle' if self.clear_pending else 'complete'
            if self.clear_pending:
                self._set_status('Ready')
            else:
                label = 'Stopped' if value['cancelled'] else 'Complete'
                count = len(value['events'])
                self._set_status(f'{label} — {count} observation' + ('' if count == 1 else 's') + ' saved for review')
                total = value['total_frames']
                percent = min(100, 100 * value['frames'] / total) if total > 0 else 0
                self.progress.configure(value=percent)
                self.progress_text.set(f"{percent:.0f}%  ·  {value['frames']:,} / {total:,} frames" if total > 0 else f"{value['frames']:,} frames · total unknown")
        self.clear_pending = False
        self._update_controls()

    def clear_database_logs(self):
        if self.db is None or self.running or self.closing or self.phase == 'loading':
            return
        if not self.history.records:
            self._set_status('Alert database is already empty')
            return
        count = len(self.history.records)
        if not messagebox.askyesno(TITLE, f'Clear all {count:,} alert log' + ('' if count == 1 else 's') + ' from the database?\n\nThis will permanently delete the saved alert records.', parent=self.root):
            return
        try:
            self.db.clear_alerts()
            self.refresh_history()
            self.screenshot_image = self.screenshot_photo = None
            self.screenshot_panel.grid_remove()
            self.history_hint.grid()
            self.right_panel.rowconfigure(3, weight=0)
            self._set_status('Alert database cleared successfully')
        except Exception as exc:
            self._set_status(f'Failed to clear alert database: {exc}', error=True)

    def refresh_history(self):
        if self.db is None:
            return
        # Fetch in pages; every saved event remains available in the scrollable table.
        records = []
        while True:
            batch = self.db.get_alerts(limit=1000, offset=len(records))
            records.extend(batch)
            if len(batch) < 1000:
                break
        self.history.set_records(records)
        self._update_count()

    def _update_count(self):
        count = len(self.history.records)
        self.history_count.set(f'{count:,} observation' + ('' if count == 1 else 's'))

    def _draw_preview(self):
        canvas = self.preview
        canvas.delete('display')
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        if self.preview_image is None:
            cy = height / 2
            cx = width / 2
            canvas.create_rectangle(cx - 23, cy - 53, cx + 13, cy - 22,
                                    outline='#8A99A6', width=2, tags='display')
            canvas.create_polygon(cx + 13, cy - 44, cx + 29, cy - 53,
                                  cx + 29, cy - 22, cx + 13, cy - 31,
                                  outline='#8A99A6', fill=PREVIEW, width=2, tags='display')
            canvas.create_text(width / 2, cy + 16, text='Upload a video to begin', fill=NAVY,
                               font=('Segoe UI', 14, 'bold'), tags='display')
            canvas.create_text(width / 2, cy + 45, text='MP4, AVI or MOV  ·  Saved locally', fill=MUTED,
                               font=('Segoe UI', 10), tags='display')
        else:
            image = ImageOps.contain(self.preview_image, (width, height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image, master=self.root)
            canvas.create_image(width / 2, height / 2, image=self.photo, tags='display')
        self.toast_host.lift()

    def view_screenshot(self, event):
        self.screenshot_image = self.screenshot_photo = None
        self.history_hint.grid_remove()
        self.screenshot_panel.grid()
        self.right_panel.rowconfigure(3, weight=1)
        self.screenshot_caption.set(f"{behavior_label(event['behavior_type'])}  ·  Track #{event['track_id']}  ·  Score {event['confidence']:.2f}\n"
                                    f"{event['video_filename']}  ·  Video {event['video_time_s']:.2f}s  ·  {local_timestamp(event['wall_time'])}")
        try:
            path = (self.output / event['screenshot_path']).resolve()
            if not path.is_relative_to(self.output.resolve()) or not path.is_file():
                raise FileNotFoundError('The saved image cannot be found in this history folder.')
            with Image.open(path) as source:
                self.screenshot_image = source.convert('RGB')
            if self.status.get().startswith('Screenshot unavailable:') and self.screenshot_previous_status:
                text, error = self.screenshot_previous_status
                self._set_status(text, error=error)
            self.screenshot_previous_status = None
        except (OSError, ValueError) as exc:
            if not self.status.get().startswith('Screenshot unavailable:'):
                self.screenshot_previous_status = (self.status.get(), self.status_bar['foreground'] == DANGER)
            self._set_status(f'Screenshot unavailable: {exc}', error=True)
        self._draw_screenshot()

    def _draw_screenshot(self):
        self.screenshot.delete('all')
        width, height = max(1, self.screenshot.winfo_width()), max(1, self.screenshot.winfo_height())
        if self.screenshot_image is None:
            self.screenshot.create_text(width / 2, height / 2, text='Screenshot unavailable', fill=MUTED, font=('Segoe UI', 10))
        else:
            image = ImageOps.contain(self.screenshot_image, (width, height), Image.Resampling.LANCZOS)
            self.screenshot_photo = ImageTk.PhotoImage(image, master=self.root)
            self.screenshot.create_image(width / 2, height / 2, image=self.screenshot_photo)

    def _show_toast(self, event):
        self.toast_number += 1
        number = self.toast_number
        self.toast_host.place(relx=1, x=-12, y=12, anchor='ne')
        card = tk.Frame(self.toast_host, autostyle=False, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', pady=(0, 6))
        stripe = tk.Frame(card, autostyle=False, bg=behavior_color(event['behavior_type']), width=4)
        stripe.pack(side='left', fill='y')
        content = tk.Frame(card, autostyle=False, bg=PAPER, padx=12, pady=9)
        content.pack(side='left')
        self._label(content, behavior_label(event['behavior_type']), bg=PAPER,
                    fg=behavior_color(event['behavior_type']), font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self._label(content, f"Track #{event['track_id']}  ·  Score {event['confidence']:.2f}", bg=PAPER,
                    fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w')
        self.toasts[number] = (card, self._later(5000, lambda: self._remove_toast(number)))
        self.toast_host.lift()

    def _remove_toast(self, number):
        entry = self.toasts.pop(number, None)
        if entry:
            entry[0].destroy()
        if not self.toasts:
            self.toast_host.place_forget()

    def _dismiss_toasts(self):
        for card, token in self.toasts.values():
            self.root.after_cancel(token)
            self.after_ids.discard(token)
            card.destroy()
        self.toasts.clear()
        self.toast_host.place_forget()

    def toggle_fullscreen(self):
        enabled = not bool(self.root.attributes('-fullscreen'))
        self.root.attributes('-fullscreen', enabled)
        self.fullscreen_button.configure(text='⛶  Exit full screen' if enabled else '⛶  Full screen')

    def show_about(self):
        if self.about_window is not None and self.about_window.winfo_exists():
            self.about_window.lift()
            return
        dialog = tk.Toplevel(self.root, bg=BACKGROUND)
        self.about_window = dialog
        dialog.title(f'About {TITLE}')
        dialog.transient(self.root)
        dialog.resizable(False, False)
        self._set_icon(dialog)
        self._label(dialog, TITLE, bg=NAVY, fg=PAPER, font=('Segoe UI', 18, 'bold'),
                    padx=24, pady=22, anchor='w').pack(fill='x')
        body = tk.Frame(dialog, autostyle=False, bg=BACKGROUND, padx=24, pady=20)
        body.pack(fill='both', expand=True)
        sections = (
            ('What it observes', 'Visible phones, sustained or repeated sideways head movements toward a nearby person, and forward head raises. Track numbers are temporary per-video labels, not verified identities.'),
            ('How to read a score', 'Phone scores reflect detector evidence. Head scores combine movement, persistence or repetition, and geometry quality. These are heuristic evidence scores, not probabilities of cheating.'),
            ('What it cannot establish', 'The system cannot determine intent, measure eye gaze, identify what someone is reading, or prove misconduct. Ordinary head movements may trigger alerts. Occlusion, small faces and camera angle can hide evidence or cause mistakes.'),
            ('Your review stays local', 'Screenshots, annotated videos and alert history are saved locally in this project. Select a history row to inspect its evidence. A green box means no active alert; it does not certify normal behavior.'),
        )
        for title, text in sections:
            self._label(body, title, fg=NAVY, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 4))
            self._label(body, text, wraplength=510, justify='left', anchor='w').pack(fill='x', pady=(0, 14))
        def dismiss():
            dialog.grab_release()
            dialog.destroy()
            self.about_window = None
        ttk.Button(body, text='Close', command=dismiss, bootstyle='primary').pack(anchor='e')
        dialog.protocol('WM_DELETE_WINDOW', dismiss)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f'+{max(0, x)}+{max(0, y)}')
        dialog.grab_set()

    def close(self):
        if self.closing:
            return
        if self.running or (self.worker and self.worker.is_alive()):
            if not messagebox.askyesno(TITLE, 'Processing is in progress. Stop and close?', parent=self.root):
                return
            self.closing = True
            self.request_stop()
            self.control.cancel()
            self._set_status('Stopping processing safely…')
            self._update_controls()
        else:
            self._destroy()

    def _destroy(self):
        self._release_replay()
        self._dismiss_toasts()
        for token in tuple(self.after_ids):
            self.root.after_cancel(token)
        self.after_ids.clear()
        self.root.destroy()
