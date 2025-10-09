#gui/window.py
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox, 
    QHBoxLayout, QPushButton, QTreeWidget
)
from PyQt6.QtCore import QEvent, Qt
from gui.tree_manager import TreeManager
from gui.instrument_manager import InstrumentManager
from gui.worker_manager import WorkerManager
from core.data_manager import DataManager
from gui.graph_dialog import GraphDialog
from utils.constants import *

import logging
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Главное окно приложения с древовидной таблицей предметов и анализов"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Анализатор каналов осциллографа')
        self.setGeometry(100, 100, 1400, 800)
        
        # Инициализация менеджеров
        self.data_manager = DataManager()
        self.worker_manager = WorkerManager()
        
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Инициализация UI компонентов
        self.setup_tree_section(main_layout)
        self.setup_instruments_section(main_layout)
        
        # Устанавливаем обработчик клавиш
        self.installEventFilter(self)
        
        # Запускаем обнаружение приборов
        self.instrument_manager.start_instrument_detection()
    
    def setup_tree_section(self, main_layout):
        """Настройка секции древовидной таблицы"""
        title_label = QLabel('Структура предметов и анализов')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        main_layout.addWidget(title_label)
        
        # Создаем древовидную таблицу
        tree_widget = QTreeWidget()
        self.tree_manager = TreeManager(tree_widget)
        
        # Создаем кнопки управления
        self.setup_tree_buttons(main_layout)
        
        main_layout.addWidget(tree_widget)
        
        # Подключаем сигналы дерева
        self.connect_tree_signals()
        
        # Добавляем начальный предмет
        self.tree_manager.add_subject("AN1")
    
    def setup_tree_buttons(self, main_layout):
        """Создание кнопок управления древовидной таблицей"""
        tree_button_layout = QHBoxLayout()
        
        add_subject_button = QPushButton('Добавить предмет')
        add_subject_button.clicked.connect(self.add_subject)
        
        load_files_button = QPushButton('Добавить файлы в текущий предмет')
        load_files_button.clicked.connect(self.tree_manager.load_files_to_current_subject)
        
        save_all_button = QPushButton('Сохранить всю таблицу')
        save_all_button.clicked.connect(self.save_all_analysis)
        
        save_selected_button = QPushButton('Сохранить выбранные анализы')
        save_selected_button.clicked.connect(self.save_selected_analysis)
        
        load_analysis_button = QPushButton('Загрузить анализ')
        load_analysis_button.clicked.connect(self.load_analysis)
        
        tree_button_layout.addWidget(add_subject_button)
        tree_button_layout.addWidget(load_files_button)
        tree_button_layout.addWidget(save_all_button)
        tree_button_layout.addWidget(save_selected_button)
        tree_button_layout.addWidget(load_analysis_button)
        
        main_layout.addLayout(tree_button_layout)
    
    def setup_instruments_section(self, main_layout):
        """Настройка секции приборов"""
        self.instrument_manager = InstrumentManager()
        instruments_group = self.instrument_manager.create_instruments_group()
        main_layout.addWidget(instruments_group)
        
        # Подключаем сигналы приборов
        self.connect_instrument_signals()
    
    def connect_tree_signals(self):
        """Подключение сигналов древовидной таблицы"""
        self.tree_manager.file_loaded.connect(self.on_file_loaded)
        self.tree_manager.subject_added.connect(self.on_subject_added)
        self.tree_manager.analysis_added.connect(self.on_analysis_added)
        self.tree_manager.item_selected.connect(self.on_item_selected)
        self.tree_manager.analysis_moved.connect(self.on_analysis_moved)
    
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
    
    def add_subject(self):
        """Добавление нового предмета"""
        self.tree_manager.add_subject()
    
    def on_file_loaded(self, subject_code, file_path):
        """Обработка загрузки файла"""
        # Создаем новый анализ в дереве
        analysis_index = self.tree_manager.add_analysis_to_subject(subject_code, {
            'file_name': 'Загрузка...',
            'params': {
                'start_freq': 0,
                'end_freq': 0,
                'record_time': 0
            }
        })
        
        if analysis_index is not None:
            # Парсим файл
            success, result = self.data_manager.parse_file(subject_code, file_path, analysis_index)
            
            if success:
                if isinstance(result, str) and 'вручную' in result:
                    # Файл загружен, но нужна ручная настройка параметров
                    self.tree_manager.update_analysis_display(subject_code, analysis_index, True, result, result)
                else:
                    # Успешная загрузка
                    file_name = result
                    self.tree_manager.update_analysis_display(subject_code, analysis_index, True, file_name)
                    
                    # Обновляем параметры в дереве
                    analysis_data = self.data_manager.get_analysis_data(subject_code, analysis_index)
                    if analysis_data:
                        self.tree_manager.update_analysis_params(subject_code, analysis_index, analysis_data['params'])
            else:
                # Ошибка загрузки
                self.tree_manager.update_analysis_display(subject_code, analysis_index, False, None, result)
    
    def on_subject_added(self, subject_code):
        """Обработка добавления нового предмета"""
        self.data_manager.initialize_subject(subject_code)
    
    def on_analysis_added(self, subject_code, analysis_index):
        """Обработка добавления нового анализа"""
        # Автоматически инициализируется в data_manager при загрузке файла
        pass
    
    def on_item_selected(self, subject_code, analysis_index):
        """Обработка выбора элемента (открытие графика)"""
        if analysis_index == -1:
            return  # Выбран предмет, а не анализ
        
        analysis_data = self.data_manager.get_analysis_data(subject_code, analysis_index)
        if not analysis_data:
            QMessageBox.warning(self, 'Ошибка', 'Данные анализа не найдены')
            return
        
        logger.debug("=== ПРОВЕРКА ДАННЫХ ПЕРЕД ОТКРЫТИЕМ ГРАФИКА ===")
        has_valid_data = False
        for channel_name, channel in analysis_data['channels'].items():
            if hasattr(channel, 'data') and channel.data is not None and not channel.data.empty:
                logger.debug(f"Канал {channel_name}: данные валидны")
                has_valid_data = True
                break

        # Проверяем, не открыт ли уже диалог
        key = (subject_code, analysis_index)
        if key in self.data_manager.open_dialogs:
            dialog = self.data_manager.open_dialogs[key]
            dialog.raise_()
            dialog.activateWindow()
            return
        
        
        # Создаем диалог
        dialog = GraphDialog(
            analysis_data['channels'], 
            analysis_data['params'], 
            analysis_data['processor'], 
            analysis_data['file_name'], 
            self
        )
        
        # Регистрируем диалог
        self.data_manager.register_dialog(subject_code, analysis_index, dialog)
        
        # Подключаем сигнал закрытия
        dialog.finished.connect(lambda: self.on_graph_dialog_closed(subject_code, analysis_index))
        
        dialog.show()
    
    def on_graph_dialog_closed(self, subject_code, analysis_index):
        """Обработка закрытия диалога с графиками"""
        key = (subject_code, analysis_index)
        if key in self.data_manager.open_dialogs:
            dialog = self.data_manager.open_dialogs[key]
            
            # Обновляем параметры
            self.data_manager.update_analysis_params(subject_code, analysis_index, dialog.params)
            self.tree_manager.update_analysis_params(subject_code, analysis_index, dialog.params)
            
            # Удаляем диалог из регистрации
            self.data_manager.unregister_dialog(subject_code, analysis_index)
    
    def on_analysis_moved(self, old_subject, new_subject, analysis_index):
        """Обработка перемещения анализа между предметами"""
        self.data_manager.move_analysis_data(old_subject, new_subject, analysis_index)
    
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
        # Сразу разблокируем интерфейс
        self.instrument_manager.set_measurement_state(False)
        self.instrument_manager.update_progress(0)
    
    def on_measurement_finished(self, channels_data):
        """Обработка завершения измерения"""
        self.instrument_manager.set_measurement_state(False)
        self.on_log_message("Измерение успешно завершено")
        
        # Получаем параметры измерения
        measurement_params = self.instrument_manager.get_measurement_params() or {}
        
        # Получаем текущий выбранный предмет или создаем новый
        current_subject = self.tree_manager.get_selected_subject()
        if not current_subject:
            current_subject = self.tree_manager.add_subject()
            logger.debug(f"Создан новый предмет для измерения: {current_subject}")
        
        # Добавляем данные в таблицу - ИСПРАВЛЕННАЯ СТРОКА
        success, subject_code, analysis_index, result = self.data_manager.save_measurement_data(
            channels_data, measurement_params, current_subject
        )
        
        if success:
            logger.debug(f"Данные измерения сохранены: {subject_code}, {analysis_index}")
            
            # Добавляем анализ в дерево - ИСПРАВЛЕННАЯ СТРОКА
            added_index = self.tree_manager.add_analysis_to_subject(subject_code, {
                'file_name': result,
                'params': measurement_params  # используем measurement_params вместо повторного вызова
            }, analysis_index)
            
            logger.debug(f"Анализ добавлен в дерево: {subject_code}, индекс: {added_index}")
            
            # Обновляем отображение
            self.tree_manager.update_analysis_display(subject_code, analysis_index, True, result)
            self.tree_manager.update_analysis_params(subject_code, analysis_index, measurement_params)
        else:
            logger.error(f"Ошибка сохранения измерения: {result}")
            self.on_log_message(result)
        
    def on_measurement_error(self, error_message):
        """Обработка ошибки измерения"""
        self.instrument_manager.set_measurement_state(False)
        self.on_log_message(f"Ошибка измерения: {error_message}")
    
    def on_oscilloscope_read_requested(self):
        """Обработка запроса на чтение данных с осциллографа"""
        oscilloscope = self.instrument_manager.get_selected_oscilloscope()
        if not oscilloscope:
            return
        
        # Запускаем чтение данных
        self.worker_manager.start_oscilloscope_reading(
            oscilloscope['resource'],
            oscilloscope['type']
        )
        
        # Обновляем UI
        self.instrument_manager.set_reading_state(True)
    
    def on_oscilloscope_data_ready(self, channels_data):
        """Обработка данных с осциллографа"""
        self.instrument_manager.set_reading_state(False)
        self.on_log_message("Данные с осциллографа успешно получены")
        
        # Получаем параметры измерения
        measurement_params = self.instrument_manager.get_measurement_params() or {}
        
        # Получаем текущий выбранный предмет или создаем новый
        current_subject = self.tree_manager.get_selected_subject()
        if not current_subject:
            current_subject = self.tree_manager.add_subject()
            logger.debug(f"Создан новый предмет для данных осциллографа: {current_subject}")
        
        # Добавляем данные в таблицу - ИСПРАВЛЕННАЯ СТРОКА
        success, subject_code, analysis_index, result = self.data_manager.save_measurement_data(
            channels_data, 
            measurement_params,  # используем measurement_params
            current_subject
        )
        
        if success:
            logger.debug(f"Данные осциллографа сохранены: {subject_code}, {analysis_index}")
            
            # Добавляем анализ в дерево - ИСПРАВЛЕННАЯ СТРОКА
            added_index = self.tree_manager.add_analysis_to_subject(subject_code, {
                'file_name': result,
                'params': measurement_params  # используем measurement_params
            }, analysis_index)
            
            logger.debug(f"Анализ осциллографа добавлен в дерево: {subject_code}, индекс: {added_index}")
            
            # Обновляем отображение
            self.tree_manager.update_analysis_display(subject_code, analysis_index, True, result)
            self.tree_manager.update_analysis_params(subject_code, analysis_index, measurement_params)
        else:
            logger.error(f"Ошибка сохранения данных осциллографа: {result}")
            self.on_log_message(result)
    
    def on_oscilloscope_data_error(self, error_message):
        """Обработка ошибки чтения данных с осциллографа"""
        self.instrument_manager.set_reading_state(False)
        self.on_log_message(f"Ошибка чтения данных: {error_message}")
    
    def on_log_message(self, message):
        """Обработка сообщения для лога"""
        self.instrument_manager.log(message)
    
    def save_all_analysis(self):
        """Сохранение всей таблицы"""
        self.data_manager.save_analysis(self.tree_manager, save_selected_only=False, parent=self)
    
    def save_selected_analysis(self):
        """Сохранение только выбранных анализов"""
        self.data_manager.save_analysis(self.tree_manager, save_selected_only=True, parent=self)
    
    def load_analysis(self):
        """Загрузка анализа"""
        loaded_data = self.data_manager.load_analysis(self)
        if not loaded_data:
            return
        
        # Очищаем дерево перед загрузкой
        self.tree_manager.clear_tree()
        
        # Загружаем предметы и анализы
        for item in loaded_data:
            subject_code = item['subject_code']
            analysis_index = item['analysis_index']  # Индекс из DataManager
            analysis_info = item['analysis_info']
            file_exists = item['file_exists']
            
            logger.debug(f"Загрузка анализа: {subject_code}, {analysis_index}")
            
            # Добавляем предмет, если его нет
            if subject_code not in self.tree_manager.subject_items:
                self.tree_manager.add_subject(subject_code)
                logger.debug(f"Добавлен предмет: {subject_code}")
            
            # Добавляем анализ с ПРАВИЛЬНЫМ индексом из DataManager
            added_index = self.tree_manager.add_analysis_to_subject(subject_code, {
                'file_name': analysis_info['file_name'],
                'params': analysis_info['params']
            }, analysis_index)  # Явно передаем индекс
            
            logger.debug(f"Анализ добавлен: {subject_code}, запрошенный индекс: {analysis_index}, фактический: {added_index}")
            
            # Обновляем отображение
            if file_exists:
                self.tree_manager.update_analysis_display(subject_code, added_index, True, analysis_info['file_name'])
            else:
                self.tree_manager.update_analysis_display(subject_code, added_index, False, 
                                                        analysis_info['file_name'], "Файл не найден")
            
            self.tree_manager.update_analysis_params(subject_code, added_index, analysis_info['params'])
    
    def eventFilter(self, obj, event):
        """Обработка событий"""
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            # Обработка удаления через Delete key
            current_subject = self.tree_manager.get_selected_subject()
            current_analysis = self.tree_manager.get_selected_analysis_index()
            
            if current_analysis != -1:
                self.tree_manager.delete_current_analysis()
            elif current_subject:
                self.tree_manager.delete_current_subject()
            
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

    def setup_tree_section(self, main_layout):
        """Настройка секции древовидной таблицы"""
        title_label = QLabel('Структура предметов и анализов')
        title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        main_layout.addWidget(title_label)
        
        # TreeManager теперь сам создает TreeWidget
        self.tree_manager = TreeManager()
        
        # Создаем кнопки управления
        self.setup_tree_buttons(main_layout)
        
        main_layout.addWidget(self.tree_manager.tree)
        
        # Подключаем сигналы дерева
        self.connect_tree_signals()
        
        # Добавляем начальный предмет
        self.tree_manager.add_subject("AN1")

    def on_analysis_moved(self, old_subject, new_subject, analysis_index):
        """Обработка перемещения анализа между предметами"""
        logger.debug(f"MainWindow: обработка перемещения {old_subject} -> {new_subject}, {analysis_index}")
        
        success = self.data_manager.move_analysis_data(old_subject, new_subject, analysis_index)
        if success:
            self.on_log_message(f"Анализ перемещен из {old_subject} в {new_subject}")
            
            # Обновляем отображение в дереве
            analysis_data = self.data_manager.get_analysis_data(new_subject, analysis_index)
            if analysis_data:
                # Отображаем оригинальное имя файла, а не стандартизированное
                self.tree_manager.update_analysis_display(new_subject, analysis_index, True, analysis_data['original_file_name'])
                self.tree_manager.update_analysis_params(new_subject, analysis_index, analysis_data['params'])
                logger.debug(f"MainWindow: отображение обновлено для {new_subject}, {analysis_index}")
            else:
                logger.warning(f"MainWindow: не удалось получить данные анализа после перемещения")
        else:
            self.on_log_message(f"Ошибка при перемещении анализа из {old_subject} в {new_subject}")
            logger.error(f"MainWindow: ошибка перемещения данных анализа")