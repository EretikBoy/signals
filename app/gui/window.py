#gui/window.py
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import QEvent

from gui.table_manager import TableManager
from gui.instrument_manager import InstrumentManager
from gui.worker_manager import WorkerManager
from core.data_manager import DataManager
from gui.graph_dialog import GraphDialog
from utils.constants import *


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Анализатор каналов осциллографа')
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация менеджеров
        self.data_manager = DataManager()
        self.worker_manager = WorkerManager()
        
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Инициализация UI компонентов
        self.setup_table_section(main_layout)
        self.setup_instruments_section(main_layout)
        
        # Устанавливаем обработчик клавиш
        self.installEventFilter(self)
        
        # Запускаем обнаружение приборов
        self.instrument_manager.start_instrument_detection()
    
    def setup_table_section(self, main_layout):
        """Настройка секции таблицы"""
        title_label = QLabel('Таблица загруженных файлов')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        main_layout.addWidget(title_label)
        
        # Создаем таблицу
        from PyQt6.QtWidgets import QTableWidget
        table_widget = QTableWidget()
        self.table_manager = TableManager(table_widget)
        
        # Создаем кнопки управления таблицей
        self.setup_table_buttons(main_layout)
        
        main_layout.addWidget(table_widget)
        
        # Подключаем сигналы таблицы
        self.connect_table_signals()
    
    def setup_table_buttons(self, main_layout):
        """Создание кнопок управления таблицей"""
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton
        
        table_button_layout = QHBoxLayout()
        
        add_row_button = QPushButton('Добавить предмет')
        add_row_button.clicked.connect(self.table_manager.add_table_row)
        
        load_button = QPushButton('Загрузить файл')
        load_button.clicked.connect(self.table_manager.load_file_for_row)
        
        load_multiple_button = QPushButton('Загрузить несколько файлов')
        load_multiple_button.clicked.connect(self.table_manager.load_multiple_files)
        
        delete_button = QPushButton('Удалить выбранные строки (Del)')
        delete_button.clicked.connect(self.table_manager.delete_selected_rows)
        
        save_analysis_button = QPushButton('Сохранить анализ')
        save_analysis_button.clicked.connect(self.save_analysis)
        
        load_analysis_button = QPushButton('Загрузить анализ')
        load_analysis_button.clicked.connect(self.load_analysis)
        
        table_button_layout.addWidget(add_row_button)
        table_button_layout.addWidget(load_button)
        table_button_layout.addWidget(load_multiple_button)
        table_button_layout.addWidget(delete_button)
        table_button_layout.addWidget(save_analysis_button)
        table_button_layout.addWidget(load_analysis_button)
        
        main_layout.addLayout(table_button_layout)
    
    def setup_instruments_section(self, main_layout):
        """Настройка секции приборов"""
        self.instrument_manager = InstrumentManager()
        instruments_group = self.instrument_manager.create_instruments_group()
        main_layout.addWidget(instruments_group)
        
        # Подключаем сигналы приборов
        self.connect_instrument_signals()
    
    def connect_table_signals(self):
        """Подключение сигналов таблицы"""
        self.table_manager.file_loaded.connect(self.on_file_loaded)
        self.table_manager.row_added.connect(self.on_row_added)
        self.table_manager.rows_deleted.connect(self.on_rows_deleted)
        self.table_manager.graph_requested.connect(self.on_graph_requested)
        self.table_manager.analysis_save_requested.connect(self.save_analysis)
        self.table_manager.analysis_load_requested.connect(self.load_analysis)
    
    def connect_instrument_signals(self):
        """Подключение сигналов приборов"""
        # Сигналы от instrument_manager
        self.instrument_manager.measurement_started.connect(self.on_measurement_started)
        self.instrument_manager.measurement_stopped.connect(self.on_measurement_stopped)
        self.instrument_manager.oscilloscope_read_requested.connect(self.on_oscilloscope_read_requested)
        self.instrument_manager.log_message.connect(self.on_log_message)
        
        # Сигналы от worker_manager
        self.worker_manager.progress_updated.connect(self.instrument_manager.update_progress)
        self.worker_manager.log_message.connect(self.on_log_message)
        self.worker_manager.measurement_finished.connect(self.on_measurement_finished)
        self.worker_manager.measurement_error.connect(self.on_measurement_error)
        self.worker_manager.oscilloscope_data_ready.connect(self.on_oscilloscope_data_ready)
        self.worker_manager.oscilloscope_data_error.connect(self.on_oscilloscope_data_error)
        self.worker_manager.instruments_detected.connect(self.instrument_manager.on_instruments_detected)
        self.worker_manager.instruments_detection_error.connect(self.instrument_manager.on_detection_error)
    
    def on_file_loaded(self, row, file_path):
        """Обработка загрузки файла"""
        success, result = self.data_manager.parse_file(file_path, row)
        
        if success:
            if isinstance(result, str) and 'вручную' in result:
                # Файл загружен, но нужна ручная настройка параметров
                self.table_manager.update_row_after_file_load(row, True, result, result)
            else:
                # Успешная загрузка
                file_name = result
                self.table_manager.update_row_after_file_load(row, True, file_name)
                
                # Обновляем параметры в таблице
                file_data = self.data_manager.get_file_data(row)
                self.table_manager.update_row_params(row, file_data['params'])
                self.table_manager.update_row_subject_code(row, f'AN{row}')
        else:
            # Ошибка загрузки
            self.table_manager.update_row_after_file_load(row, False, None, result)
    
    def on_row_added(self, row):
        """Обработка добавления новой строки"""
        # Можно добавить дополнительную логику при добавлении строки
        pass
    
    def on_rows_deleted(self, rows):
        """Обработка удаления строк"""
        for row in rows:
            self.data_manager.delete_file_data(row)
            self.data_manager.unregister_dialog(row)
    
    def on_graph_requested(self, row):
        """Обработка запроса на открытие графика"""
        file_data = self.data_manager.get_file_data(row)
        if not file_data:
            QMessageBox.warning(self, 'Ошибка', 'Данные файла не найдены')
            return
        
        # Проверяем, не открыт ли уже диалог для этой строки
        if row in self.data_manager.open_dialogs:
            dialog = self.data_manager.open_dialogs[row]
            dialog.raise_()
            dialog.activateWindow()
            return
        
        # Создаем диалог
        dialog = GraphDialog(
            file_data['channels'], 
            file_data['params'], 
            file_data['processor'], 
            file_data['file_name'], 
            self
        )
        
        # Регистрируем диалог
        self.data_manager.register_dialog(row, dialog)
        
        # Подключаем сигнал закрытия
        dialog.finished.connect(lambda: self.on_graph_dialog_closed(row))
        
        dialog.show()
    
    def on_graph_dialog_closed(self, row):
        """Обработка закрытия диалога с графиками"""
        if row in self.data_manager.open_dialogs:
            dialog = self.data_manager.open_dialogs[row]
            
            # Обновляем параметры
            if row in self.data_manager.files_data:
                self.data_manager.update_file_params(row, dialog.params)
                self.table_manager.update_row_params(row, dialog.params)
            
            # Удаляем диалог из регистрации
            self.data_manager.unregister_dialog(row)
    
    def on_measurement_started(self, params):
        """Обработка начала измерения"""
        instruments = self.instrument_manager.get_selected_instruments()
        if not instruments:
            return
        
        # Запускаем измерение через worker_manager
        self.worker_manager.start_measurement(
            instruments['generator']['resource'],
            instruments['oscilloscope']['resource'],
            instruments['generator']['type'],
            instruments['oscilloscope']['type'],
            params
        )
        
        # Обновляем UI
        self.instrument_manager.set_measurement_state(True)
    
    def on_measurement_stopped(self):
        """Обработка остановки измерения"""
        if self.worker_manager.stop_measurement():
            self.on_log_message("Запрос на остановку измерения...")
    
    def on_measurement_finished(self, channels_data):
        """Обработка завершения измерения"""
        self.instrument_manager.set_measurement_state(False)
        self.on_log_message("Измерение успешно завершено")
        
        # Сохраняем данные последнего измерения
        params = self.instrument_manager.get_measurement_params()
        if params:
            self.instrument_manager.last_measurement_data = {
                'channels': channels_data,
                'params': params
            }
        
        # Добавляем данные в таблицу
        success, table_data, result = self.data_manager.save_measurement_data(channels_data, params or {})
        
        if success:
            row = self.table_manager.add_table_row()
            self.data_manager.set_file_data(row, table_data)
            
            # Обновляем UI таблицы
            self.table_manager.update_row_after_file_load(row, True, table_data['file_name'])
            self.table_manager.update_row_params(row, table_data['params'])
            self.table_manager.update_row_subject_code(row, f"M{table_data['file_name'].split('_')[1]}")
        else:
            self.on_log_message(result)
    
    def on_measurement_error(self, error_message):
        """Обработка ошибки измерения"""
        self.instrument_manager.set_measurement_state(False)
        self.on_log_message(f"Ошибка измерения: {error_message}")
    
    def on_oscilloscope_read_requested(self):
        """Обработка запроса на чтение данных с осциллографа"""
        instruments = self.instrument_manager.get_selected_instruments()
        if not instruments:
            return
        
        # Запускаем чтение данных
        self.worker_manager.start_oscilloscope_reading(
            instruments['oscilloscope']['resource'],
            instruments['oscilloscope']['type']
        )
        
        # Обновляем UI
        self.instrument_manager.set_ui_enabled(False, enable_measure=False)
    
    def on_oscilloscope_data_ready(self, channels_data):
        """Обработка данных с осциллографа"""
        self.instrument_manager.set_ui_enabled(True)
        self.on_log_message("Данные с осциллографа успешно получены")
        
        # Добавляем данные в таблицу
        success, table_data, result = self.data_manager.save_measurement_data(
            channels_data, 
            self.instrument_manager.get_measurement_params() or {}
        )
        
        if success:
            row = self.table_manager.add_table_row()
            self.data_manager.set_file_data(row, table_data)
            
            # Обновляем UI таблицы
            self.table_manager.update_row_after_file_load(row, True, table_data['file_name'])
            self.table_manager.update_row_params(row, table_data['params'])
            self.table_manager.update_row_subject_code(row, f"OSC{table_data['file_name'].split('_')[1]}")
        else:
            self.on_log_message(result)
    
    def on_oscilloscope_data_error(self, error_message):
        """Обработка ошибки чтения данных с осциллографа"""
        self.instrument_manager.set_ui_enabled(True)
        self.on_log_message(f"Ошибка чтения данных: {error_message}")
    
    def on_log_message(self, message):
        """Обработка сообщения для лога"""
        self.instrument_manager.log(message)
    
    def save_analysis(self):
        """Сохранение анализа"""
        self.data_manager.save_analysis(self.table_manager.table, self)
    
    def load_analysis(self):
        """Загрузка анализа"""
        for row, row_data, file_path, file_exists in self.data_manager.load_analysis(self.table_manager.table, self) or []:
            # Добавляем строку в таблицу
            self.table_manager.add_table_row()
            
            # Обновляем UI строки
            file_button = self.table_manager.table.cellWidget(row, 1)
            if not file_exists:
                file_button.setText(f'Файл недоступен:\n{row_data["file_name"]}')
                self.table_manager.set_button_style(file_button, 'error')
            else:
                file_button.setText(row_data['file_name'])
                self.table_manager.set_button_style(file_button, 'success')
            
            graph_button = self.table_manager.table.cellWidget(row, 2)
            graph_button.setEnabled(True)
            graph_button.setText('Открыть графики')
            
            # Обновляем параметры
            self.table_manager.update_row_params(row, row_data['params'])
            self.table_manager.update_row_subject_code(row, row_data['subject_code'])
    
    def eventFilter(self, obj, event):
        """Обработка событий"""
        if event.type() == QEvent.Type.KeyPress and event.key() == event.key().Key_Delete:
            self.table_manager.delete_selected_rows()
            return True
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        # Останавливаем все потоки
        self.worker_manager.wait_for_all()
        
        # Закрываем все открытые диалоги
        for dialog in self.data_manager.open_dialogs.values():
            dialog.close()
        
        event.accept()