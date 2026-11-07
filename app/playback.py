"""Thread coordination at existing pipeline callback boundaries."""
import threading


class PlaybackControl:
    def __init__(self):
        self.stop = threading.Event()
        self._condition = threading.Condition()
        self._paused = False

    @property
    def paused(self):
        with self._condition:
            return self._paused

    def pause(self):
        with self._condition:
            self._paused = True

    def resume(self):
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def cancel(self):
        with self._condition:
            self.stop.set()
            self._paused = False
            self._condition.notify_all()

    def frame_boundary(self, on_paused):
        """Finish the in-flight frame, then block inference, not the Tk thread."""
        with self._condition:
            if self._paused and not self.stop.is_set():
                on_paused()
            while self._paused and not self.stop.is_set():
                self._condition.wait()
