import threading
import logging


class BackgroundJob(threading.Thread):
    def __init__(self, name, interval, function):
        threading.Thread.__init__(self, name=name)
        self._name = name
        self._logger = logging.getLogger(__name__)
        self.interval = interval
        self.simulate_func = function
        self.stop_timer = threading.Event()
        self.daemon = True

    def run(self):
        self._logger.info("Start %s thread" % self._name)
        while not self.stop_timer.is_set():
            if not self.stop_timer.is_set():
                self.simulate_func()
            self.stop_timer.wait(self.interval)
        self._logger.info("Stop %s thread" % self._name)

    def cancel(self):
        self.stop_timer.set()

