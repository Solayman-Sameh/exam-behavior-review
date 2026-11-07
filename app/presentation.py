"""Display-only vocabulary and theme. Persisted event values are never changed."""
from datetime import datetime, timezone
import tkinter.font as tkfont

import ttkbootstrap as ttk
from ttkbootstrap.style import ThemeDefinition

NAVY = '#203B60'
BACKGROUND = '#F6F4EF'
PAPER = '#FFFFFF'
INK = '#26364A'
MUTED = '#687688'
BORDER = '#DFE3E8'
PREVIEW = '#ECEFEF'
SELECTION = '#E6EDF5'
DANGER = '#A53636'
BEHAVIORS = {
    'phone_detected': ('Phone Detected', '#A15D09'),
    'peer_directed_looking': ('Peer-Directed Looking', NAVY),
    'head_raise': ('Head Raise', '#397B79'),
}


def behavior_label(code):
    return BEHAVIORS.get(code, (code.replace('_', ' ').title(), MUTED))[0]


def behavior_color(code):
    return BEHAVIORS.get(code, ('', MUTED))[1]


def local_timestamp(value):
    try:
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Legacy timestamps without an offset were recorded as UTC too.
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone()
        return f"{moment:%b} {moment.day}, {moment.year} • {moment:%I:%M %p}".replace('• 0', '• ')
    except (ValueError, TypeError, AttributeError):
        return str(value)


def apply_theme(root):
    style = ttk.Style('flatly')
    colors = dict(style.colors.__dict__)
    colors.update(primary=NAVY, secondary=MUTED, bg=BACKGROUND, fg=INK,
                  inputbg=PAPER, inputfg=INK, border=BORDER,
                  selectbg=NAVY, selectfg=PAPER, active=SELECTION)
    style.register_theme(ThemeDefinition('exam_academic', colors, 'light'))
    style.theme_use('exam_academic')
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont',
                 'TkCaptionFont', 'TkSmallCaptionFont', 'TkIconFont', 'TkTooltipFont'):
        tkfont.nametofont(name, root=root).configure(family='Segoe UI', size=10)
    root.option_add('*Font', ('Segoe UI', 10))
    root.configure(background=BACKGROUND)
    style.configure('TButton', font=('Segoe UI', 10), padding=(14, 10))
    style.configure('TLabel', font=('Segoe UI', 10))
    style.configure('Horizontal.TProgressbar', thickness=5)
    return style
