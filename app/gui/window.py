# gui/window.py
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QLineEdit,
    QGroupBox, QComboBox, QProgressBar, QTextEdit, QFormLayout,
    QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, QEvent, pyqtSlot
import os
import shutil
import pickle
import pandas as pd
from datetime import datetime

from core.parser import DataParser
from gui.graph_dialog import GraphDialog
from core.dataprocessor import Processor
from core.instrumenthandler import *

# Константы для стилей кнопок
BUTTON_STYLE_SUCCESS = 'background-color: rgba(76, 150, 80, 60);'
BUTTON_STYLE_ERROR = 'background-color: rgba(160, 80, 80, 60);'
BUTTON_STYLE_NORMAL = 'background-color: rgba(200, 200, 200, 60);'
BUTTON_STYLE_WARNING = 'background-color: rgba(252, 215, 3, 60);'
BUTTON_STYLE_ACTIVE = 'background-color: rgba(70, 130, 180, 60);'
BUTTON_STYLE_MEASURE = '''
    QPushButton {
        background-color: rgba(70, 130, 180, 180);
        color: white;
        font-weight: bold;
        font-size: 14px;
        padding: 8px;
        border: 2px solid rgba(50, 110, 160, 200);
        border-radius: 5px;
    }
    QPushButton:hover {
        background-color: rgba(80, 140, 190, 220);
    }
    QPushButton:pressed {
        background-color: rgba(60, 120, 170, 250);
    }
'''

class MainWindow(QMainWindow):
    '''Главное окно приложения с таблицей файлов и управлением приборами'''
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Анализатор каналов осциллографа')
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация компонентов
        self.data_parser = DataParser()
        self.files_data = {}  # Словарь для хранения данных о файлах
        self.open_dialogs = {}  # Словарь для отслеживания открытых диалогов
        self.measurement_thread = None  # Поток для измерений
        self.detection_thread = None  # Поток для обнаружения приборов
        self.reader_thread = None  # Поток для чтения данных с осциллографа
        self.detected_instruments = {'oscilloscopes': [], 'generators': []}
        self.last_measurement_data = None  # Данные последнего измерения
        
        self.init_ui()
        
        # Запускаем обнаружение приборов в отдельном потоке
        self.start_instrument_detection()
    
    def init_ui(self):
        '''Инициализация пользовательского интерфейса'''
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок и таблица (без изменений)
        title_label = QLabel('Таблица загруженных файлов')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        main_layout.addWidget(title_label)
        
        # Создаем таблицу
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Код предмета', 
            'Файл', 
            'Графики и \nподстройка значений', 
            'Параметр 1', 
            'Параметр 2', 
            'Параметр 3',
            'Параметр 4'
        ])
        
        # Настраиваем внешний вид таблицы
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        
        # Кнопки таблицы (без изменений)
        add_row_button = QPushButton('Добавить предмет')
        add_row_button.clicked.connect(self.add_table_row)
        
        self.load_button = QPushButton('Загрузить файл')
        self.load_button.clicked.connect(self.load_file)
        
        self.load_multiple_button = QPushButton('Загрузить несколько файлов')
        self.load_multiple_button.clicked.connect(self.load_multiple_files)
        
        self.delete_button = QPushButton('Удалить выбранные строки (Del)')
        self.delete_button.clicked.connect(self.delete_selected_rows)
        
        self.save_analysis_button = QPushButton('Сохранить анализ')
        self.save_analysis_button.clicked.connect(self.save_analysis)
        
        self.load_analysis_button = QPushButton('Загрузить анализ')
        self.load_analysis_button.clicked.connect(self.load_analysis)
        
        table_button_layout = QHBoxLayout()
        table_button_layout.addWidget(add_row_button)
        table_button_layout.addWidget(self.load_button)
        table_button_layout.addWidget(self.load_multiple_button)
        table_button_layout.addWidget(self.delete_button)
        table_button_layout.addWidget(self.save_analysis_button)
        table_button_layout.addWidget(self.load_analysis_button)
        
        main_layout.addLayout(table_button_layout)
        main_layout.addWidget(self.table)
        
        # Группа управления приборами - ПЕРЕРАБОТАННАЯ ЧАСТЬ
        instruments_group = QGroupBox("Управление приборами")
        instruments_layout = QVBoxLayout()
        
        # Создаем сетку для приборов
        instruments_grid = QGridLayout()
        instruments_grid.setColumnStretch(0, 1)  # Генератор
        instruments_grid.setColumnStretch(1, 1)  # Осциллограф
        instruments_grid.setColumnStretch(2, 1)  # Управление
        
        # === КОЛОНКА 1: ГЕНЕРАТОР СИГНАЛОВ ===
        generator_group = QGroupBox("Генератор сигналов")
        generator_layout = QVBoxLayout()
        
        # Выбор генератора
        generator_select_layout = QHBoxLayout()
        generator_select_layout.addWidget(QLabel("Генератор:"))
        self.generator_combo = QComboBox()
        generator_select_layout.addWidget(self.generator_combo)
        generator_layout.addLayout(generator_select_layout)
        
        # Настройки генератора - вертикальный стек
        generator_settings_layout = QFormLayout()
        
        # Частоты
        self.start_freq_edit = QLineEdit("100")
        self.start_freq_edit.textChanged.connect(self.update_generator_defaults)
        generator_settings_layout.addRow("Начальная частота (Гц):", self.start_freq_edit)
        
        self.end_freq_edit = QLineEdit("1000")
        self.end_freq_edit.textChanged.connect(self.update_generator_defaults)
        generator_settings_layout.addRow("Конечная частота (Гц):", self.end_freq_edit)
        
        # Амплитуда и смещение
        self.amplitude_edit = QLineEdit("1")
        generator_settings_layout.addRow("Амплитуда (В):", self.amplitude_edit)
        
        self.offset_edit = QLineEdit("0")
        generator_settings_layout.addRow("Смещение (В):", self.offset_edit)
        
        # Время развертки
        self.sweep_time_edit = QLineEdit("30")
        generator_settings_layout.addRow("Время развертки (сек):", self.sweep_time_edit)
        
        generator_layout.addLayout(generator_settings_layout)
        generator_group.setLayout(generator_layout)
        instruments_grid.addWidget(generator_group, 0, 0)
        
        # === КОЛОНКА 2: ОСЦИЛЛОГРАФ ===
        oscilloscope_group = QGroupBox("Осциллограф")
        oscilloscope_layout = QVBoxLayout()
        
        # Выбор осциллографа
        oscilloscope_select_layout = QHBoxLayout()
        oscilloscope_select_layout.addWidget(QLabel("Осциллограф:"))
        self.oscilloscope_combo = QComboBox()
        oscilloscope_select_layout.addWidget(self.oscilloscope_combo)
        oscilloscope_layout.addLayout(oscilloscope_select_layout)
        
        # Кнопка считывания данных
        self.read_oscilloscope_button = QPushButton("Прочитать данные с осциллографа")
        self.read_oscilloscope_button.clicked.connect(self.read_oscilloscope_data)
        self.read_oscilloscope_button.setEnabled(False)
        oscilloscope_layout.addWidget(self.read_oscilloscope_button)
        
        oscilloscope_group.setLayout(oscilloscope_layout)
        instruments_grid.addWidget(oscilloscope_group, 0, 1)
        
        # === КОЛОНКА 3: УПРАВЛЕНИЕ ===
        control_group = QGroupBox("Управление")
        control_layout = QVBoxLayout()
        
        # Кнопка обновить список
        self.refresh_instruments_button = QPushButton("Обновить список приборов")
        self.refresh_instruments_button.clicked.connect(self.start_instrument_detection)
        control_layout.addWidget(self.refresh_instruments_button)
        
        # Большая кнопка начала записи
        self.measure_button = QPushButton("НАЧАТЬ ЗАПИСЬ")
        self.measure_button.clicked.connect(self.start_measurement)
        self.measure_button.setStyleSheet(BUTTON_STYLE_MEASURE)
        self.measure_button.setMinimumHeight(50)
        self.measure_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.measure_button.setEnabled(False)
        control_layout.addWidget(self.measure_button)
        
        # Кнопка остановки
        self.stop_button = QPushButton("ОСТАНОВИТЬ")
        self.stop_button.clicked.connect(self.stop_measurement)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet('''
            QPushButton {
                background-color: rgba(160, 80, 80, 180);
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 2px solid rgba(140, 60, 60, 200);
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: rgba(170, 90, 90, 220);
            }
        ''')
        control_layout.addWidget(self.stop_button)
        
        control_group.setLayout(control_layout)
        instruments_grid.addWidget(control_group, 0, 2)
        
        # Добавляем сетку в основной layout приборов
        instruments_layout.addLayout(instruments_grid)
        
        # Прогресс бар и лог (без изменений)
        self.progress_bar = QProgressBar()
        instruments_layout.addWidget(self.progress_bar)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        instruments_layout.addWidget(self.log_text)
        
        instruments_group.setLayout(instruments_layout)
        main_layout.addWidget(instruments_group)
        
        # Устанавливаем обработчик клавиш
        self.installEventFilter(self)
    
    def update_generator_defaults(self):
        """Обновление настроек генератора на основе последнего измерения"""
        if self.last_measurement_data:
            try:
                # Получаем параметры из последнего измерения
                params = self.last_measurement_data['params']
                
                # Устанавливаем значения по умолчанию
                self.start_freq_edit.setText(str(params.get('start_freq', 100)))
                self.end_freq_edit.setText(str(params.get('end_freq', 1000)))
                
            except Exception as e:
                self.log_text.append(f"Ошибка при обновлении настроек: {str(e)}")

    # Остальные методы остаются без изменений...
    def start_instrument_detection(self):
        """Запуск обнаружения приборов в отдельном потоке"""
        self.log_text.append("Обнаружение приборов...")
        self.refresh_instruments_button.setEnabled(False)
        self.measure_button.setEnabled(False)
        self.read_oscilloscope_button.setEnabled(False)
        
        # Очищаем комбобоксы
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        self.generator_combo.addItem("Обнаружение приборов...")
        self.oscilloscope_combo.addItem("Обнаружение приборов...")
        
        # Создаем и запускаем поток обнаружения
        self.detection_thread = InstrumentDetectorThread()
        self.detection_thread.detection_finished.connect(self.on_instruments_detected)
        self.detection_thread.detection_error.connect(self.on_detection_error)
        self.detection_thread.start()
    
    @pyqtSlot(dict)
    def on_instruments_detected(self, instruments):
        """Обработка завершения обнаружения приборов"""
        self.detected_instruments = instruments
        self.update_instrument_comboboxes()
        self.refresh_instruments_button.setEnabled(True)
        self.measure_button.setEnabled(True)
        self.read_oscilloscope_button.setEnabled(True)
        self.log_text.append("Обнаружение приборов завершено")
    
    @pyqtSlot(str)
    def on_detection_error(self, error_message):
        """Обработка ошибки обнаружения приборов"""
        self.log_text.append(error_message)
        self.refresh_instruments_button.setEnabled(True)
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        self.generator_combo.addItem("Ошибка обнаружения")
        self.oscilloscope_combo.addItem("Ошибка обнаружения")
    
    def update_instrument_comboboxes(self):
        """Обновление комбобоксов с приборами"""
        self.generator_combo.clear()
        self.oscilloscope_combo.clear()
        
        # Добавляем генераторы в комбобокс
        for instrument in self.detected_instruments['generators']:
            self.generator_combo.addItem(f"{instrument['resource']} ({instrument['idn']})", 
                                        (instrument['resource'], instrument['provider']))
        
        # Добавляем осциллографы в комбобокс
        for instrument in self.detected_instruments['oscilloscopes']:
            self.oscilloscope_combo.addItem(f"{instrument['resource']} ({instrument['idn']})", 
                                           (instrument['resource'], instrument['provider']))
        
        # Проверяем наличие рекомендуемых приборов
        has_rigol = any(instr['provider'] == 'rigol' for instr in self.detected_instruments['generators'])
        has_tektronix_osc = any(instr['provider'] == 'tektronix' for instr in self.detected_instruments['oscilloscopes'])
        
        if not has_rigol:
            self.log_text.append("Предупреждение: не обнаружен генератор Rigol")
        
        if not has_tektronix_osc:
            self.log_text.append("Предупреждение: не обнаружен осциллограф Tektronix")
    
    def eventFilter(self, obj, event):
        '''Обработка нажатий клавиш'''
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            self.delete_selected_rows()
            return True
        return super().eventFilter(obj, event)
    
    def set_button_style(self, button, style_type='normal'):
        '''Установка стиля для кнопки'''
        if style_type == 'success':
            button.setStyleSheet(BUTTON_STYLE_SUCCESS)
        elif style_type == 'error':
            button.setStyleSheet(BUTTON_STYLE_ERROR)
        elif style_type == 'warning':
            button.setStyleSheet(BUTTON_STYLE_WARNING)
        elif style_type == 'active':
            button.setStyleSheet(BUTTON_STYLE_ACTIVE)
        else:
            button.setStyleSheet(BUTTON_STYLE_NORMAL)
    
    def add_table_row(self):
        '''Добавление новой строки в таблицу'''
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        
        # Поле для кода предмета
        subject_item = QTableWidgetItem('')
        self.table.setItem(row_position, 0, subject_item)
        
        # Кнопка добавления файла для этой строки
        file_button = QPushButton('Добавить файл')
        file_button.clicked.connect(lambda: self.load_file_for_row(row_position))
        self.set_button_style(file_button, 'normal')
        self.table.setCellWidget(row_position, 1, file_button)
        
        # Кнопка для открытия графика (изначально неактивна)
        graph_button = QPushButton('Открыть графики')
        graph_button.setEnabled(False)
        graph_button.clicked.connect(lambda: self.open_graph_dialog(row_position))
        self.table.setCellWidget(row_position, 2, graph_button)
        
        # Параметры (нули)
        for col in range(3, 7):
            param_item = QTableWidgetItem('0')
            self.table.setItem(row_position, col, param_item)
    
    def load_multiple_files(self):
        '''Загрузка нескольких файлов одновременно'''
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            'Выберите файлы данных', 
            '', 
            'Excel Files (*.xlsx *.xls *.csv);;All Files (*)'
        )
        
        if not file_paths:
            return
        
        # Добавляем строки для всех файлов
        for file_path in file_paths:
            row_position = self.table.rowCount()
            self.add_table_row()
            self.load_file_to_row(file_path, row_position)
    
    def load_file_to_row(self, file_path, row_position):
        '''Загрузка файла в конкретную строку'''
        try:
            # Парсим файл
            file_format = file_path.split('.')[-1]
            success = self.data_parser.parsefile(file_path, file_format)
            
            if not success:
                QMessageBox.warning(self, 'Ошибка', f'Не удалось загрузить файл: {file_path}')
                # Обновляем кнопку в случае ошибки
                file_button = self.table.cellWidget(row_position, 1)
                file_button.setText('Ошибка загрузки')
                self.set_button_style(file_button, 'error')
                return
            
            # Получаем имя файла без пути
            file_name = file_path.split('/')[-1]
            
            # Обновляем кнопку загрузки файла
            file_button = self.table.cellWidget(row_position, 1)
            file_button.setText(file_name)
            self.set_button_style(file_button, 'success')
            
            # Активируем кнопку открытия графиков
            graph_button = self.table.cellWidget(row_position, 2)
            graph_button.setEnabled(True)
            graph_button.setText('Открыть графики')
            
            # Парсим параметры из имени файла
            file_name_without_ext = file_name.split('.')[0]
            name_parts = file_name_without_ext.split('_')
            
            # Значения по умолчанию
            start_freq = 1
            bandwidth = 1
            record_time = 1
            identifier = f'AN{row_position}'
            
            if len(name_parts) >= 4:
                try:
                    # Извлекаем параметры из имени файла
                    identifier = str(name_parts[0])
                    start_freq = int(name_parts[1])
                    bandwidth = int(name_parts[2])
                    record_time = int(name_parts[3])
                except ValueError:
                    QMessageBox.warning(self, 'Предупреждение', 
                                       f'Не удалось извлечь параметры из имени файла {file_name}, данные записаны неверно')
                    # Обновляем кнопку в случае ошибки
                    file_button = self.table.cellWidget(row_position, 1)
                    file_button.setText(f'Установите параметры\nвручную: {file_name}')
                    self.set_button_style(file_button, 'warning')
            else:
                QMessageBox.warning(self, 'Предупреждение', 
                                       f'Не удалось извлечь параметры из имени файла {file_name}, данные записаны неверно')
                # Обновляем кнопку в случае ошибки
                file_button = self.table.cellWidget(row_position, 1)
                file_button.setText(f'Установите параметры\nвручную: {file_name}')
                self.set_button_style(file_button, 'warning')
            
            end_freq = start_freq + bandwidth
            
            # Сохраняем данные файла
            self.files_data[row_position] = {
                'path': file_path,
                'file_name': file_name,  # Сохраняем имя файла
                'channels': {},
                'params': {
                    'start_freq': start_freq,
                    'end_freq': end_freq,
                    'record_time': record_time,
                    'cut_second': 0,
                    'fixedlevel': 0.6,
                    'gain': 7
                }
            }
            
            # Получаем каналы
            for channel_name in self.data_parser.get_channel_names():
                channel = self.data_parser.get_channel(channel_name)
                if channel and not channel.data.empty:
                    self.files_data[row_position]['channels'][channel_name] = channel
            
            # Создаём процессор для файла
            self.files_data[row_position]['processor'] = Processor(self.files_data[row_position])

            # Обновляем параметры в таблице
            self.table.item(row_position, 0).setText(str(identifier))
            self.table.item(row_position, 3).setText(str(self.files_data[row_position]['processor'].start_freq))
            self.table.item(row_position, 4).setText(str(self.files_data[row_position]['processor'].end_freq))
            self.table.item(row_position, 5).setText(str(self.files_data[row_position]['processor'].record_time))
            self.table.item(row_position, 6).setText(str(self.files_data[row_position]['processor'].cut_second))
                
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Произошла ошибка при загрузке файла: {str(e)}')
            
            # Обновляем кнопку в случае ошибки
            file_button = self.table.cellWidget(row_position, 1)
            file_button.setText('Ошибка загрузки')
            self.set_button_style(file_button, 'error')
    
    def load_file_for_row(self, row):
        '''Загрузка файла для конкретной строки'''
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Выберите файл данных', 
            '', 
            'Excel Files (*.xlsx *.xls *.csv);;All Files (*)'
        )
        
        if not file_path:
            return
            
        self.load_file_to_row(file_path, row)
    
    def delete_selected_rows(self):
        '''Удаление выбранных строк и связанных с ними данных'''
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, 'Информация', 'Пожалуйста, выберите строки для удаления')
            return
        
        # Сортируем строки в обратном порядке для правильного удаления
        sorted_rows = sorted(selected_rows, reverse=True)
        
        for row in sorted_rows:
            # Удаляем данные файла из словаря
            if row in self.files_data:
                del self.files_data[row]
            
            # Закрываем связанные диалоги, если они открыты
            if row in self.open_dialogs:
                self.open_dialogs[row].close()
                del self.open_dialogs[row]
            
            # Удаляем строку из таблице
            self.table.removeRow(row)
            
            # Обновляем индексы оставшихся файлов
            new_files_data = {}
            new_open_dialogs = {}
            for existing_row, data in self.files_data.items():
                if existing_row > row:
                    new_files_data[existing_row-1] = data
                    if existing_row in self.open_dialogs:
                        new_open_dialogs[existing_row-1] = self.open_dialogs[existing_row]
                elif existing_row < row:
                    new_files_data[existing_row] = data
                    if existing_row in self.open_dialogs:
                        new_open_dialogs[existing_row] = self.open_dialogs[existing_row]
            self.files_data = new_files_data
            self.open_dialogs = new_open_dialogs
        
        # Обновляем связи кнопок с новыми номерами строк
        for row in range(self.table.rowCount()):
            # Обновляем кнопку загрузки файла
            file_button = self.table.cellWidget(row, 1)
            file_button.clicked.disconnect()
            file_button.clicked.connect(lambda checked, r=row: self.load_file_for_row(r))
            
            # Обновляем кнопку открытия графиков
            graph_button = self.table.cellWidget(row, 2)
            if graph_button.isEnabled():
                graph_button.clicked.disconnect()
                graph_button.clicked.connect(lambda checked, r=row: self.open_graph_dialog(r))
    
    def open_graph_dialog(self, row):
        '''Открытие диалога с графиками и настройками'''
        if row not in self.files_data:
            QMessageBox.warning(self, 'Ошибка', 'Данные файла не найдены')
            return
        
        # Если диалог для этой строки уже открыт, активируем его
        if row in self.open_dialogs:
            self.open_dialogs[row].raise_()
            self.open_dialogs[row].activateWindow()
            return
        
        # Получаем данные для выбранной строки
        file_data = self.files_data[row]
        file_name = file_data['file_name']
        
        # Создаем и показываем диалог
        dialog = GraphDialog(file_data['channels'], file_data['params'], file_data['processor'], file_name, self)
        
        # Сохраняем ссылку на диалог
        self.open_dialogs[row] = dialog
        
        # Подключаем сигнал закрытия диалога
        dialog.finished.connect(lambda: self.on_graph_dialog_closed(row))
        
        # Показываем диалог
        dialog.show()
    
    def on_graph_dialog_closed(self, row):
        '''Обработчик закрытия диалога с графиками'''
        if row in self.open_dialogs:
            # Получаем диалог
            dialog = self.open_dialogs[row]
            
            # Обновляем параметры после закрытия диалога
            if row in self.files_data:
                self.files_data[row]['params'] = dialog.params
                
                # Обновляем таблицу
                self.table.item(row, 3).setText(str(dialog.params['start_freq']))
                self.table.item(row, 4).setText(str(dialog.params['end_freq']))
                self.table.item(row, 5).setText(str(dialog.params['record_time']))
                self.table.item(row, 6).setText(str(dialog.params['cut_second']))
            
            # Удаляем диалог из словаря открытых диалогов
            del self.open_dialogs[row]
    
    def load_file(self):
        '''Загрузка файла (альтернативный метод)'''
        # Просто добавляем новую строки и загружаем в нее файл
        self.add_table_row()
        self.load_file_for_row(self.table.rowCount() - 1)

    def save_analysis(self):
        '''Сохранение анализа в папку tables'''
        if not self.files_data:
            QMessageBox.warning(self, 'Предупреждение', 'Нет данных для сохранения')
            return
        
        # Создаем папку tables если ее нет
        if not os.path.exists('tables'):
            os.makedirs('tables')
        
        # Запрашиваем имя файя для сохранения
        file_name, _ = QFileDialog.getSaveFileName(
            self, 
            'Сохранить анализ', 
            'tables/analysis.analysis', 
            'Analysis Files (*.analysis)'
        )
        
        if not file_name:
            return
        
        # Создаем папку с тем же именем что и файл
        base_name = os.path.splitext(os.path.basename(file_name))[0]
        folder_name = os.path.join(os.path.dirname(file_name), base_name)
        
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        
        try:
            # Подготавливаем данные для сохранения
            analysis_data = {
                'rows': [],
                'files': {}
            }
            
            # Копируем файлы и сохраняем информацию
            for row, data in self.files_data.items():
                # Копируем файл в папку
                try:
                    src_file = data['path']
                    dst_file = os.path.join(folder_name, data['file_name'])
                    shutil.copy2(src_file, dst_file)
                except Exception as e:
                    QMessageBox.critical(self, 'Ошибка', f'Строки таблицы не имеют привязки, данные сохраняться без исходных файлов')
                
                # Сохраняем информацию о строке
                row_data = {
                    'subject_code': self.table.item(row, 0).text(),
                    'file_name': data['file_name'],
                    'params': data['params'],
                    'processor': data['processor'],
                    # Сохраняем данные каналов
                    'channels_data': {}
                }
                
                # Сохраняем данные каждого канала
                for channel_name, channel in data['channels'].items():
                    row_data['channels_data'][channel_name] = {
                        'data': channel.data.to_dict(),
                        'name': channel.name
                    }
                
                analysis_data['rows'].append((row, row_data))
                analysis_data['files'][row] = data['file_name']
            
            # Сохраняем данные анализа
            with open(file_name, 'wb') as f:
                pickle.dump(analysis_data, f)
            
            QMessageBox.information(self, 'Успех', 'Анализ успешно сохранен')
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при сохранении анализа: {str(e)}')
    
    def load_analysis(self):
        '''Загрузка анализа из файла'''
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            'Загрузить анализ', 
            'tables', 
            'Analysis Files (*.analysis)'
        )
        
        if not file_name:
            return
        
        # Определяем папку с файлами
        base_name = os.path.splitext(os.path.basename(file_name))[0]
        folder_name = os.path.join(os.path.dirname(file_name), base_name)
        
        if not os.path.exists(file_name) or not os.path.exists(folder_name):
            QMessageBox.critical(self, 'Ошибка', 'Файл анализа или папка с данными не найдены')
            pass
        
        try:
            # Загружаем данные анализа
            with open(file_name, 'rb') as f:
                analysis_data = pickle.load(f)
            
            # Очищаем текущие данные
            self.table.setRowCount(0)
            self.files_data = {}
            for dialog in self.open_dialogs.values():
                dialog.close()
            self.open_dialogs = {}
            
            # Восстанавливаем строки
            for row, row_data in analysis_data['rows']:
                self.add_table_row()
                
                # Проверяем доступность файла
                file_path = os.path.join(folder_name, row_data['file_name'])
                file_exists = os.path.exists(file_path)
                
                # Восстанавливаем данные
                self.table.item(row, 0).setText(row_data['subject_code'])
                
                file_button = self.table.cellWidget(row, 1)
                if not file_exists:
                    file_button.setText(f'Файл недоступен:\n{row_data["file_name"]}')
                    self.set_button_style(file_button, 'error')
                else:
                    file_button.setText(row_data['file_name'])
                    self.set_button_style(file_button, 'success')
                
                graph_button = self.table.cellWidget(row, 2)
                graph_button.setEnabled(True)
                graph_button.setText('Открыть графики')
                
                # Восстанавливаем параметры
                self.table.item(row, 3).setText(str(row_data['params']['start_freq']))
                self.table.item(row, 4).setText(str(row_data['params']['end_freq']))
                self.table.item(row, 5).setText(str(row_data['params']['record_time']))
                self.table.item(row, 6).setText(str(row_data['params']['cut_second']))
                
                # Восстанавливаем каналы
                channels = {}
                for channel_name, channel_data in row_data['channels_data'].items():
                    # Создаем объект канала и восстанавливаем данные
                    channel = type('Channel', (), {})()
                    channel.name = channel_data['name']
                    channel.data = pd.DataFrame(channel_data['data'])
                    channels[channel_name] = channel
                
                # Восстанавливаем files_data
                self.files_data[row] = {
                    'path': file_path if file_exists else None,
                    'file_name': row_data['file_name'],
                    'params': row_data['params'],
                    'processor': row_data['processor'],
                    'channels': channels
                }
            
            QMessageBox.information(self, 'Успех', 'Анализ успешно загружен')
            
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при загрузке анализа: {str(e)}')

    def start_measurement(self):
        """Запуск процесса измерения"""
        # Получаем параметры измерения
        try:
            start_freq = float(self.start_freq_edit.text())
            end_freq = float(self.end_freq_edit.text())
            record_time = float(self.sweep_time_edit.text())
            amplitude = float(self.amplitude_edit.text())
            offset = float(self.offset_edit.text())
            
            if start_freq <= 0 or end_freq <= start_freq or record_time <= 0:
                raise ValueError("Неверные параметры измерения")
        except ValueError as e:
            self.log_text.append(f"Ошибка в параметрах: {str(e)}")
            return
        
        # Получаем выбранные приборы
        if self.generator_combo.currentIndex() == -1:
            self.log_text.append("Выберите генератор сигналов")
            return
            
        if self.oscilloscope_combo.currentIndex() == -1:
            self.log_text.append("Выберите осциллограф")
            return
        
        generator_data = self.generator_combo.currentData()
        oscilloscope_data = self.oscilloscope_combo.currentData()
        
        if not generator_data or not oscilloscope_data:
            self.log_text.append("Неверные данные приборов")
            return
            
        generator_resource, generator_type = generator_data
        oscilloscope_resource, oscilloscope_type = oscilloscope_data
        
        # Параметры измерения
        params = {
            'start_freq': start_freq,
            'end_freq': end_freq,
            'record_time': record_time,
            'amplitude': amplitude,
            'offset': offset
        }
        
        # Создаем и запускаем поток измерения
        self.measurement_thread = InstrumentWorker(
            generator_resource, 
            oscilloscope_resource,
            generator_type,
            oscilloscope_type,
            params
        )
        self.measurement_thread.update_signal.connect(self.update_log)
        self.measurement_thread.progress_signal.connect(self.update_progress)
        self.measurement_thread.finished_signal.connect(self.measurement_finished)
        self.measurement_thread.error_signal.connect(self.measurement_error)
        
        # Обновляем UI
        self.measure_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.read_oscilloscope_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.append("Начало измерения...")
        
        # Запускаем поток
        self.measurement_thread.start()
    
    def stop_measurement(self):
        """Остановка процесса измерения"""
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_thread.stop()
            self.stop_button.setEnabled(False)
            self.log_text.append("Запрос на остановку измерения...")
    
    def read_oscilloscope_data(self):
        """Чтение данных с осциллографа без измерения"""
        # Получаем выбранный осциллограф
        if self.oscilloscope_combo.currentIndex() == -1:
            self.log_text.append("Выберите осциллограф")
            return
        
        oscilloscope_data = self.oscilloscope_combo.currentData()
        
        if not oscilloscope_data:
            self.log_text.append("Неверные данные осциллографа")
            return
            
        oscilloscope_resource, oscilloscope_type = oscilloscope_data
        
        # Создаем и запускаем поток чтения данных
        self.reader_thread = OscilloscopeReaderThread(
            oscilloscope_resource,
            oscilloscope_type
        )
        self.reader_thread.update_signal.connect(self.update_log)
        self.reader_thread.finished_signal.connect(self.oscilloscope_data_read)
        self.reader_thread.error_signal.connect(self.oscilloscope_data_error)
        
        # Обновляем UI
        self.read_oscilloscope_button.setEnabled(False)
        self.measure_button.setEnabled(False)
        self.log_text.append("Чтение данных с осциллографа...")
        
        # Запускаем поток
        self.reader_thread.start()
    
    @pyqtSlot(str)
    def update_log(self, message):
        """Обновление лога сообщений"""
        self.log_text.append(message)
    
    @pyqtSlot(int)
    def update_progress(self, value):
        """Обновление прогресс бара"""
        self.progress_bar.setValue(value)
    
    @pyqtSlot(dict)
    def measurement_finished(self, channels_data):
        """Обработка завершения измерения"""
        self.measure_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.read_oscilloscope_button.setEnabled(True)
        self.log_text.append("Измерение успешно завершено")
        
        # Сохраняем данные последнего измерения для настроек по умолчанию
        self.last_measurement_data = {
            'channels': channels_data,
            'params': {
                'start_freq': float(self.start_freq_edit.text()),
                'end_freq': float(self.end_freq_edit.text()),
                'record_time': float(self.sweep_time_edit.text())
            }
        }
        
        # Добавляем данные в таблицу
        self.add_measurement_to_table(channels_data)
    
    @pyqtSlot(dict)
    def oscilloscope_data_read(self, channels_data):
        """Обработка завершения чтения данных с осциллографа"""
        self.read_oscilloscope_button.setEnabled(True)
        self.measure_button.setEnabled(True)
        self.log_text.append("Данные с осциллографа успешно получены")
        
        # Добавляем данные в таблицу
        self.add_oscilloscope_data_to_table(channels_data)
    
    @pyqtSlot(str)
    def measurement_error(self, error_message):
        """Обработка ошибки измерения"""
        self.measure_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.read_oscilloscope_button.setEnabled(True)
        self.log_text.append(f"Ошибка измерения: {error_message}")
    
    @pyqtSlot(str)
    def oscilloscope_data_error(self, error_message):
        """Обработка ошибки чтения данных с осциллографа"""
        self.read_oscilloscope_button.setEnabled(True)
        self.measure_button.setEnabled(True)
        self.log_text.append(f"Ошибка чтения данных: {error_message}")
    
    def add_measurement_to_table(self, channels_data):
        """Добавление результатов измерения в таблицу"""
        if not channels_data:
            self.log_text.append("Нет данных для добавления в таблицу")
            return
        
        # Добавляем новую строку
        row_position = self.table.rowCount()
        self.add_table_row()
        
        # Генерируем имя файла на основе текущего времени
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        file_name = f"measurement_{timestamp}.csv"
        
        # Сохраняем данные в файл
        try:
            # Создаем DataFrame из данных каналов
            all_data = pd.DataFrame()
            for channel_name, channel in channels_data.items():
                if hasattr(channel, 'data') and not channel.data.empty:
                    channel_df = channel.data.copy()
                    channel_df.columns = [f'{channel_name}_time', f'{channel_name}_amplitude']
                    if all_data.empty:
                        all_data = channel_df
                    else:
                        all_data = pd.concat([all_data, channel_df], axis=1)
            
            # Сохраняем в файл
            file_path = os.path.join('measurements', file_name)
            os.makedirs('measurements', exist_ok=True)
            all_data.to_csv(file_path, index=False)
            
            # Обновляем UI
            file_button = self.table.cellWidget(row_position, 1)
            file_button.setText(file_name)
            self.set_button_style(file_button, 'success')
            
            # Активируем кнопку открытия графиков
            graph_button = self.table.cellWidget(row_position, 2)
            graph_button.setEnabled(True)
            graph_button.setText('Открыть графики')
            
            # Сохраняем данные файла
            self.files_data[row_position] = {
                'path': file_path,
                'file_name': file_name,
                'channels': channels_data,
                'params': {
                    'start_freq': float(self.start_freq_edit.text()),
                    'end_freq': float(self.end_freq_edit.text()),
                    'record_time': float(self.sweep_time_edit.text()),
                    'cut_second': 0,
                    'fixedlevel': 0.6,
                    'gain': 7
                }
            }
            
            # Создаём процессор для файла
            self.files_data[row_position]['processor'] = Processor(self.files_data[row_position])
            
            # Обновляем параметры в таблице
            identifier = f"M{timestamp}"
            self.table.item(row_position, 0).setText(identifier)
            self.table.item(row_position, 3).setText(str(self.files_data[row_position]['processor'].start_freq))
            self.table.item(row_position, 4).setText(str(self.files_data[row_position]['processor'].end_freq))
            self.table.item(row_position, 5).setText(str(self.files_data[row_position]['processor'].record_time))
            self.table.item(row_position, 6).setText(str(self.files_data[row_position]['processor'].cut_second))
            
            self.log_text.append(f"Данные сохранены в файл: {file_name}")
            
        except Exception as e:
            self.log_text.append(f"Ошибка при сохранении данных: {str(e)}")

    def add_oscilloscope_data_to_table(self, channels_data):
        """Добавление данных с осциллографа в таблицу"""
        if not channels_data:
            self.log_text.append("Нет данных для добавления в таблицу")
            return
        
        # Добавляем новую строку
        row_position = self.table.rowCount()
        self.add_table_row()
        
        # Генерируем имя файла на основе текущего времени
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        file_name = f"oscilloscope_{timestamp}.csv"
        
        # Сохраняем данные в файл
        try:
            # Создаем DataFrame из данных каналов
            all_data = pd.DataFrame()
            for channel_name, channel in channels_data.items():
                if hasattr(channel, 'data') and not channel.data.empty:
                    channel_df = channel.data.copy()
                    channel_df.columns = [f'{channel_name}_time', f'{channel_name}_amplitude']
                    if all_data.empty:
                        all_data = channel_df
                    else:
                        all_data = pd.concat([all_data, channel_df], axis=1)
            
            # Сохраняем в файл
            file_path = os.path.join('measurements', file_name)
            os.makedirs('measurements', exist_ok=True)
            all_data.to_csv(file_path, index=False)
            
            # Обновляем UI
            file_button = self.table.cellWidget(row_position, 1)
            file_button.setText(file_name)
            self.set_button_style(file_button, 'success')
            
            # Активируем кнопку открытия графиков
            graph_button = self.table.cellWidget(row_position, 2)
            graph_button.setEnabled(True)
            graph_button.setText('Открыть графики')
            
            # Сохраняем данные файла (без параметров частоты, так как это просто данные с осциллографа)
            self.files_data[row_position] = {
                'path': file_path,
                'file_name': file_name,
                'channels': channels_data,
                'params': {
                    'start_freq': 1,  # Значения по умолчанию
                    'end_freq': 1000,
                    'record_time': 1,
                    'cut_second': 0,
                    'fixedlevel': 0.6,
                    'gain': 1
                }
            }
            
            # Создаём процессор для файла
            self.files_data[row_position]['processor'] = Processor(self.files_data[row_position])
            
            # Обновляем параметры в таблице
            identifier = f"OSC{timestamp}"
            self.table.item(row_position, 0).setText(identifier)
            self.table.item(row_position, 3).setText(str(self.files_data[row_position]['processor'].start_freq))
            self.table.item(row_position, 4).setText(str(self.files_data[row_position]['processor'].end_freq))
            self.table.item(row_position, 5).setText(str(self.files_data[row_position]['processor'].record_time))
            self.table.item(row_position, 6).setText(str(self.files_data[row_position]['processor'].cut_second))
            
            self.log_text.append(f"Данные осциллографа сохранены в файл: {file_name}")
            
        except Exception as e:
            self.log_text.append(f"Ошибка при сохранении данных осциллографа: {str(e)}")