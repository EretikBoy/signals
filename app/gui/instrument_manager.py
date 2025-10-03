#gui/instrument_manager.py
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QComboBox, QLineEdit, QTextEdit, QProgressBar,
    QFormLayout
)
from PyQt6.QtCore import pyqtSignal, QObject

from utils.constants import BUTTON_STYLE_MEASURE, BUTTON_STYLE_STOP, DEFAULT_PARAMS
from core.instrumenthandler import InstrumentDetectorThread


class InstrumentManager(QObject):
    """Управление приборами: обнаружение, настройки, логирование"""
    
    # Сигналы
    instruments_refreshed = pyqtSignal()
    measurement_started = pyqtSignal(dict)  # params
    measurement_stopped = pyqtSignal()
    oscilloscope_read_requested = pyqtSignal()
    log_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.detected_instruments = {'oscilloscopes': [], 'generators': []}
        self.detection_thread = None
        self.last_measurement_data = None
        
        # UI элементы
        self.generator_combo = None
        self.oscilloscope_combo = None
        self.start_freq_edit = None
        self.end_freq_edit = None
        self.amplitude_edit = None
        self.offset_edit = None
        self.sweep_time_edit = None
        self.refresh_instruments_button = None
        self.measure_button = None
        self.stop_button = None
        self.read_oscilloscope_button = None
        self.progress_bar = None
        self.log_text = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Создание UI компонентов управления приборами"""
        # Выпадающие списки приборов
        self.generator_combo = QComboBox()
        self.oscilloscope_combo = QComboBox()
        
        # Поля ввода параметров
        self.start_freq_edit = QLineEdit(str(DEFAULT_PARAMS['start_freq']))
        self.end_freq_edit = QLineEdit(str(DEFAULT_PARAMS['end_freq']))
        self.amplitude_edit = QLineEdit(str(DEFAULT_PARAMS['amplitude']))
        self.offset_edit = QLineEdit(str(DEFAULT_PARAMS['offset']))
        self.sweep_time_edit = QLineEdit(str(DEFAULT_PARAMS['sweep_time']))
        
        # Кнопки
        self.refresh_instruments_button = QPushButton("Обновить список приборов")
        self.measure_button = QPushButton("НАЧАТЬ ЗАПИСЬ")
        self.stop_button = QPushButton("ОСТАНОВИТЬ")
        self.read_oscilloscope_button = QPushButton("Прочитать данные с осциллографа")
        
        # Прогресс бар и лог
        self.progress_bar = QProgressBar()
        self.log_text = QTextEdit()
        
        self.setup_connections()
        self.apply_styles()
    
    def setup_connections(self):
        """Настройка соединений сигналов"""
        self.refresh_instruments_button.clicked.connect(self.start_instrument_detection)
        self.measure_button.clicked.connect(self.start_measurement)
        self.stop_button.clicked.connect(self.measurement_stopped.emit)
        self.read_oscilloscope_button.clicked.connect(self.oscilloscope_read_requested.emit)
        
        self.start_freq_edit.textChanged.connect(self.update_generator_defaults)
        self.end_freq_edit.textChanged.connect(self.update_generator_defaults)
    
    def apply_styles(self):
        """Применение стилей к UI элементам"""
        self.measure_button.setStyleSheet(BUTTON_STYLE_MEASURE)
        self.measure_button.setMinimumHeight(50)
        self.stop_button.setStyleSheet(BUTTON_STYLE_STOP)
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
    
    def create_instruments_group(self):
        """Создание группы управления приборами"""
        instruments_group = QGroupBox("Управление приборами")
        instruments_layout = QVBoxLayout()
        
        # Сетка для приборов
        instruments_grid = QGridLayout()
        instruments_grid.setColumnStretch(0, 1)
        instruments_grid.setColumnStretch(1, 1)
        instruments_grid.setColumnStretch(2, 1)
        
        # Колонка 1: Генератор сигналов
        generator_group = self.create_generator_group()
        instruments_grid.addWidget(generator_group, 0, 0)
        
        # Колонка 2: Осциллограф
        oscilloscope_group = self.create_oscilloscope_group()
        instruments_grid.addWidget(oscilloscope_group, 0, 1)
        
        # Колонка 3: Управление
        control_group = self.create_control_group()
        instruments_grid.addWidget(control_group, 0, 2)
        
        instruments_layout.addLayout(instruments_grid)
        instruments_layout.addWidget(self.progress_bar)
        instruments_layout.addWidget(self.log_text)
        
        instruments_group.setLayout(instruments_layout)
        return instruments_group
    
    def create_generator_group(self):
        """Создание группы генератора сигналов"""
        generator_group = QGroupBox("Генератор сигналов")
        generator_layout = QVBoxLayout()
        
        # Выбор генератора
        generator_select_layout = QHBoxLayout()
        generator_select_layout.addWidget(QLabel("Генератор:"))
        generator_select_layout.addWidget(self.generator_combo)
        generator_layout.addLayout(generator_select_layout)
        
        # Настройки генератора
        generator_settings_layout = QFormLayout()
        generator_settings_layout.addRow("Начальная частота (Гц):", self.start_freq_edit)
        generator_settings_layout.addRow("Конечная частота (Гц):", self.end_freq_edit)
        generator_settings_layout.addRow("Амплитуда (В):", self.amplitude_edit)
        generator_settings_layout.addRow("Смещение (В):", self.offset_edit)
        generator_settings_layout.addRow("Время развертки (сек):", self.sweep_time_edit)
        
        generator_layout.addLayout(generator_settings_layout)
        generator_group.setLayout(generator_layout)
        return generator_group
    
    def create_oscilloscope_group(self):
        """Создание группы осциллографа"""
        oscilloscope_group = QGroupBox("Осциллограф")
        oscilloscope_layout = QVBoxLayout()
        
        # Выбор осциллографа
        oscilloscope_select_layout = QHBoxLayout()
        oscilloscope_select_layout.addWidget(QLabel("Осциллограф:"))
        oscilloscope_select_layout.addWidget(self.oscilloscope_combo)
        oscilloscope_layout.addLayout(oscilloscope_select_layout)
        
        # Кнопка считывания данных
        oscilloscope_layout.addWidget(self.read_oscilloscope_button)
        
        oscilloscope_group.setLayout(oscilloscope_layout)
        return oscilloscope_group
    
    def create_control_group(self):
        """Создание группы управления"""
        control_group = QGroupBox("Управление")
        control_layout = QVBoxLayout()
        
        control_layout.addWidget(self.refresh_instruments_button)
        control_layout.addWidget(self.measure_button)
        control_layout.addWidget(self.stop_button)
        
        control_group.setLayout(control_layout)
        return control_group
    
    def start_instrument_detection(self):
        """Запуск обнаружения приборов"""
        self.log_message.emit("Обнаружение приборов...")
        self.set_ui_enabled(False)
        
        # Очищаем комбобоксы
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        self.generator_combo.addItem("Обнаружение приборов...")
        self.oscilloscope_combo.addItem("Обнаружение приборов...")
        
        # Запускаем поток обнаружения
        self.detection_thread = InstrumentDetectorThread()
        self.detection_thread.detection_finished.connect(self.on_instruments_detected)
        self.detection_thread.detection_error.connect(self.on_detection_error)
        self.detection_thread.start()
    
    def on_instruments_detected(self, instruments):
        """Обработка завершения обнаружения приборов"""
        self.detected_instruments = instruments
        self.update_instrument_comboboxes()
        self.set_ui_enabled(True)
        self.log_message.emit("Обнаружение приборов завершено")
        self.instruments_refreshed.emit()
    
    def on_detection_error(self, error_message):
        """Обработка ошибки обнаружения приборов"""
        self.log_message.emit(error_message)
        self.set_ui_enabled(True, enable_measure=False)
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        self.generator_combo.addItem("Ошибка обнаружения")
        self.oscilloscope_combo.addItem("Ошибка обнаружения")
    
    def update_instrument_comboboxes(self):
        """Обновление комбобоксов с приборами"""
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        
        # Добавляем генераторы
        for instrument in self.detected_instruments['generators']:
            self.generator_combo.addItem(
                f"{instrument['resource']} ({instrument['idn']})", 
                (instrument['resource'], instrument['provider'])
            )
        
        # Добавляем осциллографы
        for instrument in self.detected_instruments['oscilloscopes']:
            self.oscilloscope_combo.addItem(
                f"{instrument['resource']} ({instrument['idn']})", 
                (instrument['resource'], instrument['provider'])
            )
        
        # Проверяем наличие рекомендуемых приборов
        has_rigol = any(instr['provider'] == 'rigol' for instr in self.detected_instruments['generators'])
        has_tektronix_osc = any(instr['provider'] == 'tektronix' for instr in self.detected_instruments['oscilloscopes'])
        
        if not has_rigol:
            self.log_message.emit("Предупреждение: не обнаружен генератор Rigol")
        
        if not has_tektronix_osc:
            self.log_message.emit("Предупреждение: не обнаружен осциллограф Tektronix")
    
    def start_measurement(self):
        """Запуск процесса измерения"""
        # Получаем параметры измерения
        params = self.get_measurement_params()
        if not params:
            return
        
        # Проверяем выбранные приборы
        if not self.get_selected_instruments():
            return
        
        self.measurement_started.emit(params)
    
    def get_measurement_params(self):
        """Получение параметров измерения из UI"""
        try:
            start_freq = float(self.start_freq_edit.text())
            end_freq = float(self.end_freq_edit.text())
            record_time = float(self.sweep_time_edit.text())
            amplitude = float(self.amplitude_edit.text())
            offset = float(self.offset_edit.text())
            
            if start_freq <= 0 or end_freq <= start_freq or record_time <= 0:
                raise ValueError("Неверные параметры измерения")
                
            return {
                'start_freq': start_freq,
                'end_freq': end_freq,
                'record_time': record_time,
                'amplitude': amplitude,
                'offset': offset
            }
        except ValueError as e:
            self.log_message.emit(f"Ошибка в параметрах: {str(e)}")
            return None
    
    def get_selected_instruments(self):
        """Получение выбранных приборов для измерения (требует оба прибора)"""
        if self.generator_combo.currentIndex() == -1:
            self.log_message.emit("Выберите генератор сигналов")
            return None
            
        if self.oscilloscope_combo.currentIndex() == -1:
            self.log_message.emit("Выберите осциллограф")
            return None
        
        generator_data = self.generator_combo.currentData()
        oscilloscope_data = self.oscilloscope_combo.currentData()
        
        if not generator_data or not oscilloscope_data:
            self.log_message.emit("Неверные данные приборов")
            return None
        
        return {
            'generator': {
                'resource': generator_data[0],
                'type': generator_data[1]
            },
            'oscilloscope': {
                'resource': oscilloscope_data[0],
                'type': oscilloscope_data[1]
            }
        }
    
    def get_selected_oscilloscope(self):
        """Получение только выбранного осциллографа (для чтения данных)"""
        if self.oscilloscope_combo.currentIndex() == -1:
            self.log_message.emit("Выберите осциллограф")
            return None
        
        oscilloscope_data = self.oscilloscope_combo.currentData()
        
        if not oscilloscope_data:
            self.log_message.emit("Неверные данные осциллографа")
            return None
        
        return {
            'resource': oscilloscope_data[0],
            'type': oscilloscope_data[1]
        }
    
    def update_generator_defaults(self):
        """Обновление настроек генератора на основе последнего измерения"""
        if self.last_measurement_data:
            try:
                params = self.last_measurement_data['params']
                self.start_freq_edit.setText(str(params.get('start_freq', DEFAULT_PARAMS['start_freq'])))
                self.end_freq_edit.setText(str(params.get('end_freq', DEFAULT_PARAMS['end_freq'])))
            except Exception as e:
                self.log_message.emit(f"Ошибка при обновлении настроек: {str(e)}")
    
    def set_ui_enabled(self, enabled, enable_measure=True):
        """Установка состояния UI элементов"""
        self.refresh_instruments_button.setEnabled(enabled)
        self.measure_button.setEnabled(enabled and enable_measure)
        self.read_oscilloscope_button.setEnabled(enabled and enable_measure)
        self.stop_button.setEnabled(not enabled)
    
    def set_measurement_state(self, measuring):
        """Установка состояния измерения"""
        self.measure_button.setEnabled(not measuring)
        self.stop_button.setEnabled(measuring)
        self.read_oscilloscope_button.setEnabled(not measuring)
        self.refresh_instruments_button.setEnabled(not measuring)
    
    def set_reading_state(self, reading):
        """Установка состояния чтения данных"""
        self.measure_button.setEnabled(not reading)
        self.read_oscilloscope_button.setEnabled(not reading)
        self.refresh_instruments_button.setEnabled(not reading)
    
    def update_progress(self, value):
        """Обновление прогресс бара"""
        self.progress_bar.setValue(value)
    
    def log(self, message):
        """Добавление сообщения в лог"""
        self.log_text.append(message)
    
    def set_last_measurement_data(self, data):
        """Установка данных последнего измерения"""
        self.last_measurement_data = data