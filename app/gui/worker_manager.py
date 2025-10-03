#gui/worker_manager.py
from PyQt6.QtCore import QObject, pyqtSignal

from core.instrumenthandler import (
    InstrumentDetectorThread, InstrumentWorker, OscilloscopeReaderThread
)


class WorkerManager(QObject):
    """Управление потоками выполнения: измерения, обнаружение, чтение данных"""
    
    # Сигналы для основного UI
    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str)
    measurement_finished = pyqtSignal(dict)  # channels_data
    measurement_error = pyqtSignal(str)
    oscilloscope_data_ready = pyqtSignal(dict)  # channels_data
    oscilloscope_data_error = pyqtSignal(str)
    instruments_detected = pyqtSignal(dict)
    instruments_detection_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.measurement_thread = None
        self.detection_thread = None
        self.reader_thread = None
    
    def start_instrument_detection(self):
        """Запуск обнаружения приборов в отдельном потоке"""
        self.detection_thread = InstrumentDetectorThread()
        self.detection_thread.detection_finished.connect(self.instruments_detected.emit)
        self.detection_thread.detection_error.connect(self.instruments_detection_error.emit)
        self.detection_thread.start()
    
    def start_measurement(self, generator_resource, oscilloscope_resource, 
                         generator_type, oscilloscope_type, params):
        """Запуск измерения в отдельном потоке"""
        self.measurement_thread = InstrumentWorker(
            generator_resource, 
            oscilloscope_resource,
            generator_type,
            oscilloscope_type,
            params
        )
        
        # Подключаем сигналы
        self.measurement_thread.update_signal.connect(self.log_message.emit)
        self.measurement_thread.progress_signal.connect(self.progress_updated.emit)
        self.measurement_thread.finished_signal.connect(self.measurement_finished.emit)
        self.measurement_thread.error_signal.connect(self.measurement_error.emit)
        
        # Запускаем поток
        self.measurement_thread.start()
    
    def start_oscilloscope_reading(self, oscilloscope_resource, oscilloscope_type):
        """Запуск чтения данных с осциллографа"""
        self.reader_thread = OscilloscopeReaderThread(
            oscilloscope_resource,
            oscilloscope_type
        )
        
        # Подключаем сигналы
        self.reader_thread.update_signal.connect(self.log_message.emit)
        self.reader_thread.finished_signal.connect(self.oscilloscope_data_ready.emit)
        self.reader_thread.error_signal.connect(self.oscilloscope_data_error.emit)
        
        # Запускаем поток
        self.reader_thread.start()
    
    def stop_measurement(self):
        """Остановка измерения"""
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_thread.stop()
            return True
        return False
    
    def is_measurement_running(self):
        """Проверка, выполняется ли измерение"""
        return self.measurement_thread and self.measurement_thread.isRunning()
    
    def is_detection_running(self):
        """Проверка, выполняется ли обнаружение приборов"""
        return self.detection_thread and self.detection_thread.isRunning()
    
    def is_reading_running(self):
        """Проверка, выполняется ли чтение данных"""
        return self.reader_thread and self.reader_thread.isRunning()
    
    def wait_for_all(self, timeout=5000):
        """Ожидание завершения всех потоков"""
        threads = []
        
        if self.measurement_thread and self.measurement_thread.isRunning():
            threads.append(self.measurement_thread)
        
        if self.detection_thread and self.detection_thread.isRunning():
            threads.append(self.detection_thread)
        
        if self.reader_thread and self.reader_thread.isRunning():
            threads.append(self.reader_thread)
        
        for thread in threads:
            thread.wait(timeout)