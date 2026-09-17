"""
Background Network Worker Utility for PySide6 GUI.
Ensures network calls over TCP sockets do not freeze the Qt event loop.
"""

from PySide6.QtCore import QThread, Signal


class NetworkWorker(QThread):
    """
    Dedicated background worker thread for executing network requests.
    Emits result_ready on success or error_occurred on network/server failure.
    Maintains an active reference to prevent Python GC while the thread runs.
    """
    result_ready = Signal(object)
    error_occurred = Signal(str)

    _active_workers: set["NetworkWorker"] = set()

    def __init__(self, func, *args, parent=None, **kwargs):
        super().__init__(parent)
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.finished.connect(self._cleanup)

    def start(self, priority=QThread.InheritPriority) -> None:
        NetworkWorker._active_workers.add(self)
        super().start(priority)

    def run(self) -> None:
        try:
            result = self.func(*self.args, **self.kwargs)
            self.result_ready.emit(result)
        except Exception as err:
            self.error_occurred.emit(str(err))

    def _cleanup(self) -> None:
        try:
            if self.isRunning():
                self.wait(100)
        except Exception:
            pass
        NetworkWorker._active_workers.discard(self)

    def __del__(self) -> None:
        try:
            if self.isRunning():
                self.wait(200)
        except Exception:
            pass

    @classmethod
    def shutdown_all(cls, timeout_ms: int = 500) -> None:
        """Gracefully waits for all running background workers during app teardown."""
        workers = list(cls._active_workers)
        for w in workers:
            try:
                if w.isRunning():
                    w.wait(timeout_ms)
            except Exception:
                pass
        cls._active_workers.clear()
