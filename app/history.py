"""Scrollable, virtualized alert table with true per-cell text colors.

ttk Treeview tags color whole rows, so a Canvas draws only the visible rows.
The timestamp, track, score and filename always retain neutral text colors.
"""
import tkinter as tk
import tkinter.font as tkfont
import ttkbootstrap as ttk

from .presentation import (PAPER, INK, MUTED, BORDER, SELECTION,
                           behavior_label, behavior_color, local_timestamp)


class AlertHistory(ttk.Frame):
    ROW_HEIGHT = 38
    COLUMNS = (('Time', 176), ('Track', 52), ('Behavior', 164), ('Score', 56), ('Video', 110))

    def __init__(self, parent, on_select):
        super().__init__(parent)
        self.records = []
        self.selected_id = None
        self.on_select = on_select
        self.font = tkfont.Font(family='Segoe UI', size=9)
        self.bold = tkfont.Font(family='Segoe UI', size=9, weight='bold')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.header = tk.Canvas(self, autostyle=False, height=36, background='#F0F2F4', highlightthickness=0)
        self.header.grid(row=0, column=0, sticky='ew')
        self.canvas = tk.Canvas(self, autostyle=False, background=PAPER, highlightthickness=0, height=130)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        self.vertical = ttk.Scrollbar(self, orient='vertical', command=self._scroll_y)
        self.vertical.grid(row=1, column=1, sticky='ns')
        self.horizontal = ttk.Scrollbar(self, orient='horizontal', command=self._scroll_x)
        self.horizontal.grid(row=2, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        self.canvas.bind('<Configure>', self._draw)
        self.canvas.bind('<Button-1>', self._click)
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<Button-4>', lambda _: self._scroll_y('scroll', -1, 'units'))
        self.canvas.bind('<Button-5>', lambda _: self._scroll_y('scroll', 1, 'units'))
        self.header.bind('<Configure>', self._draw)

    def set_records(self, records):
        self.records = list(records)
        if not any(r['id'] == self.selected_id for r in self.records):
            self.selected_id = None
        self._draw()

    def add_record(self, record):
        if not any(r['id'] == record['id'] for r in self.records):
            self.records.insert(0, record)
        self._draw()

    def select(self, record_id):
        for index, record in enumerate(self.records):
            if record['id'] == record_id:
                self.selected_id = record_id
                top = self.canvas.canvasy(0)
                if not top <= index * self.ROW_HEIGHT < top + self.canvas.winfo_height():
                    self.canvas.yview_moveto(index / max(1, len(self.records)))
                self._draw()
                self.on_select(record)
                # Opening the inline image reduces the table viewport. Keep
                # the selected observation visible after that layout change.
                self.update_idletasks()
                top = self.canvas.canvasy(0)
                if not top <= index * self.ROW_HEIGHT < top + self.canvas.winfo_height() - self.ROW_HEIGHT:
                    self.canvas.yview_moveto(index / max(1, len(self.records)))
                    self._draw()
                return

    def _click(self, event):
        index = int(self.canvas.canvasy(event.y) // self.ROW_HEIGHT)
        if 0 <= index < len(self.records):
            self.select(self.records[index]['id'])

    def _scroll_y(self, *args):
        self.canvas.yview(*args)
        self._draw()

    def _scroll_x(self, *args):
        self.canvas.xview(*args)
        self.header.xview_moveto(self.canvas.xview()[0])

    def _wheel(self, event):
        self._scroll_y('scroll', -int(event.delta / 120) or (-1 if event.delta > 0 else 1), 'units')
        return 'break'

    def _fit(self, text, width):
        text = str(text)
        if self.font.measure(text) <= width:
            return text
        while text and self.font.measure(text + '…') > width:
            text = text[:-1]
        return text + '…'

    def _draw(self, _event=None):
        width = max(sum(w for _, w in self.COLUMNS), self.canvas.winfo_width())
        widths = [w for _, w in self.COLUMNS]
        widths[-1] += width - sum(widths)
        height = max(self.canvas.winfo_height(), len(self.records) * self.ROW_HEIGHT)
        self.canvas.configure(scrollregion=(0, 0, width, height), yscrollincrement=self.ROW_HEIGHT)
        self.header.configure(scrollregion=(0, 0, width, 36))
        self.header.delete('all')
        x = 0
        for (label, _), cell_width in zip(self.COLUMNS, widths):
            self.header.create_text(x + 10, 18, anchor='w', text=label, fill=MUTED, font=self.bold)
            x += cell_width
        self.header.xview_moveto(self.canvas.xview()[0])
        self.canvas.delete('all')
        if not self.records:
            self.canvas.create_text(self.canvas.winfo_width() / 2, 65,
                                    text='No alerts yet', fill=INK, font=self.bold)
            self.canvas.create_text(self.canvas.winfo_width() / 2, 92,
                                    text='Observations will appear here as a video is reviewed.',
                                    fill=MUTED, font=self.font, width=max(200, self.canvas.winfo_width()-40))
            return
        first = max(0, int(self.canvas.canvasy(0) // self.ROW_HEIGHT))
        last = min(len(self.records), first + self.canvas.winfo_height() // self.ROW_HEIGHT + 2)
        for index in range(first, last):
            record = self.records[index]
            y = index * self.ROW_HEIGHT
            selected = record['id'] == self.selected_id
            self.canvas.create_rectangle(0, y, width, y + self.ROW_HEIGHT,
                                         fill=SELECTION if selected else PAPER, outline='')
            self.canvas.create_line(0, y + self.ROW_HEIGHT, width, y + self.ROW_HEIGHT, fill=BORDER)
            values = (local_timestamp(record['wall_time']), f"#{record['track_id']}",
                      behavior_label(record['behavior_type']), f"{record['confidence']:.2f}",
                      record['video_filename'])
            x = 0
            for column, (value, cell_width) in enumerate(zip(values, widths)):
                self.canvas.create_text(x + 10, y + self.ROW_HEIGHT / 2, anchor='w',
                                        text=self._fit(value, cell_width - 18), font=self.font,
                                        fill=behavior_color(record['behavior_type']) if column == 2 else INK)
                x += cell_width
