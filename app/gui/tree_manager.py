# gui/tree_manager.py

from PyQt6.QtWidgets import (
    QTreeWidgetItem, QHeaderView, QPushButton,
    QFileDialog, QMessageBox, QMenu, QCheckBox, QHBoxLayout, QWidget,
    QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QAction

from gui.tree_widget import TreeWidget
from gui.tree_items import SubjectItem, AnalysisItem
from gui.column_manager import ColumnManager
from gui.filter_manager import FilterManager
from utils.constants import BUTTON_STYLE_NORMAL, BUTTON_STYLE_SUCCESS, BUTTON_STYLE_ERROR, BUTTON_STYLE_WARNING

import numpy as np
import logging
logger = logging.getLogger(__name__)

class ColumnConfigDialog(QDialog):
    """Диалог настройки столбцов"""

    def __init__(self, available_columns, current_dynamic_columns, column_manager, parent=None):
        super().__init__(parent)
        self.column_manager = column_manager
        self.available_columns = available_columns
        self.current_dynamic_columns = current_dynamic_columns.copy()

        self.setWindowTitle('Настройка столбцов')
        self.setModal(True)
        self.resize(400, 500)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Описание
        desc_label = QLabel('Перетащите параметры для настройки отображаемых столбцов:')
        layout.addWidget(desc_label)

        # Список доступных столбцов
        available_label = QLabel('Доступные параметры:')
        layout.addWidget(available_label)

        self.available_list = QListWidget()
        self.available_list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.available_list)

        # Список выбранных столбцов
        selected_label = QLabel('Текущие столбцы:')
        layout.addWidget(selected_label)

        self.selected_list = QListWidget()
        self.selected_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.selected_list)

        # Кнопки управления
        button_layout = QHBoxLayout()

        add_button = QPushButton('Добавить →')
        add_button.clicked.connect(self.add_selected)
        button_layout.addWidget(add_button)

        remove_button = QPushButton('← Удалить')
        remove_button.clicked.connect(self.remove_selected)
        button_layout.addWidget(remove_button)

        up_button = QPushButton('Вверх')
        up_button.clicked.connect(self.move_up)
        button_layout.addWidget(up_button)

        down_button = QPushButton('Вниз')
        down_button.clicked.connect(self.move_down)
        button_layout.addWidget(down_button)

        layout.addLayout(button_layout)

        # Кнопки диалога
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        layout.addWidget(button_box)

        self.load_data()

    def load_data(self):
        """Загрузка данных в списки"""
        self.available_list.clear()
        self.selected_list.clear()

        # Добавляем текущие столбцы
        current_keys = [col['key'] for col in self.current_dynamic_columns]

        for column in self.available_columns:
            if column['key'] not in current_keys:
                self.available_list.addItem(f"{column['title']} ({column['key']})")
                self.available_list.item(self.available_list.count()-1).setData(Qt.ItemDataRole.UserRole, column)

        for column in self.current_dynamic_columns:
            self.selected_list.addItem(f"{column['title']} ({column['key']})")
            self.selected_list.item(self.selected_list.count()-1).setData(Qt.ItemDataRole.UserRole, column)

    def add_selected(self):
        """Добавление выбранных параметров"""
        for item in self.available_list.selectedItems():
            column = item.data(Qt.ItemDataRole.UserRole)
            self.current_dynamic_columns.append(column)
            self.available_list.takeItem(self.available_list.row(item))

        self.load_data()

    def remove_selected(self):
        """Удаление выбранных параметров"""
        for item in self.selected_list.selectedItems():
            column = item.data(Qt.ItemDataRole.UserRole)
            self.current_dynamic_columns = [col for col in self.current_dynamic_columns if col['key'] != column['key']]

        self.load_data()

    def move_up(self):
        """Перемещение вверх"""
        current_row = self.selected_list.currentRow()
        if current_row > 0:
            item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row - 1, item)
            self.selected_list.setCurrentRow(current_row - 1)

            # Обновляем порядок в current_columns
            column = self.current_dynamic_columns.pop(current_row)
            self.current_dynamic_columns.insert(current_row - 1, column)

    def move_down(self):
        """Перемещение вниз"""
        current_row = self.selected_list.currentRow()
        if current_row < self.selected_list.count() - 1:
            item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row + 1, item)
            self.selected_list.setCurrentRow(current_row + 1)

            # Обновляем порядок в current_columns
            column = self.current_dynamic_columns.pop(current_row)
            self.current_dynamic_columns.insert(current_row + 1, column)

    def restore_defaults(self):
        """Восстановление столбцов по умолчанию"""
        self.current_dynamic_columns = [
            col for col in self.available_columns
            if col['key'] in ['start_freq', 'end_freq', 'record_time']
        ]
        self.load_data()

    def get_selected_columns(self):
        """Получение выбранных столбцов"""
        return self.current_dynamic_columns

class TreeManager(QObject):
    """Управление древовидной таблицей с предметами и анализами"""

    # Сигналы
    file_loaded = pyqtSignal(str, str)  # subject_code, file_path
    subject_added = pyqtSignal(str)  # subject_code
    analysis_added = pyqtSignal(str, int)  # subject_code, analysis_index
    item_selected = pyqtSignal(str, int)  # subject_code, analysis_index (-1 для предмета)
    analysis_moved = pyqtSignal(str, str, int)  # old_subject, new_subject, analysis_index
    columns_changed = pyqtSignal(list)  # Список новых столбцов

    def __init__(self, data_manager):
        super().__init__()
        self.tree = TreeWidget()
        self.column_manager = ColumnManager()
        self.filter_manager = FilterManager()
        self.data_manager = data_manager

        self.setup_tree()

        # Данные для хранения связи между элементами дерева и данными
        self.subject_items = {}  # subject_code -> SubjectItem

        # Подключаем сигнал перемещения
        self.tree.analysis_moved.connect(self.handle_analysis_moved)
        self.tree.itemChanged.connect(self.on_item_changed)

        logger.debug("TreeManager инициализирован")

    def setup_tree(self):
        """Настройка древовидной таблицы"""
        logger.debug("Настройка древовидной таблицы")

        # Устанавливаем количество столбцов
        self.tree.setColumnCount(self.column_manager.get_column_count())
        self.tree.setHeaderLabels(self.column_manager.get_headers())

        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Включаем сортировку
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(
            self.column_manager.get_column_index('subject_code'),
            Qt.SortOrder.AscendingOrder
        )

        # Подключаем контекстное меню
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # Подключаем двойной клик по заголовку для фильтрации
        self.tree.header().sectionDoubleClicked.connect(self.on_header_double_clicked)

    def on_header_double_clicked(self, logical_index):
        """Обработка двойного клика по заголовку для фильтрации"""
        logger.debug(f"Двойной клик по заголовку столбца {logical_index}")

        column_config = self.column_manager.get_column_by_index(logical_index)
        if column_config:
            logger.debug(f"Конфигурация столбца: {column_config}")

        if column_config and column_config.get('type') == 'dynamic':
            logger.debug("Открытие фильтра для динамического столбца")
            self.show_column_filter(logical_index)
        elif logical_index == self.column_manager.get_column_index('subject_code'):
            logger.debug("Открытие фильтра для предметов")
            self.show_subject_filter()
        else:
            logger.debug("Открытие фильтра для базового столбца")
            self.show_column_filter(logical_index)

    def show_column_filter(self, column_index):
        """Показать диалог фильтрации для столбца"""
        column_config = self.column_manager.get_column_by_index(column_index)
        if column_config:
            column_key = column_config['key']
            column_title = column_config['title']

            dialog = QDialog(self.tree)
            dialog.setWindowTitle(f'Фильтр: {column_title}')
            dialog.setModal(True)
            layout = QVBoxLayout(dialog)

            # Выбор типа фильтра
            filter_type = QComboBox()
            filter_type.addItems(['Все значения', 'Равно', 'Больше', 'Меньше', 'Между'])
            layout.addWidget(QLabel('Тип фильтра:'))
            layout.addWidget(filter_type)

            # Поля для значений
            value1_layout = QHBoxLayout()
            value1_layout.addWidget(QLabel('Значение:'))
            value1_edit = QLineEdit()
            value1_layout.addWidget(value1_edit)
            layout.addLayout(value1_layout)

            value2_layout = QHBoxLayout()
            value2_layout.addWidget(QLabel('До:'))
            value2_edit = QLineEdit()
            value2_layout.addWidget(value2_edit)
            value2_layout.setEnabled(False)
            layout.addLayout(value2_layout)

            # Кнопки
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            # Логика включения полей
            def update_fields(index):
                value2_layout.setEnabled(index == 4)  # "Между"

            filter_type.currentIndexChanged.connect(update_fields)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.apply_column_filter(column_index, filter_type.currentText(),
                                       value1_edit.text(), value2_edit.text())

    def show_subject_filter(self):
        """Показать фильтр для предметов"""
        dialog = QDialog(self.tree)
        dialog.setWindowTitle('Фильтр по предметам')
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel('Фильтр по коду предмета:'))
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText('Введите часть кода предмета...')
        layout.addWidget(filter_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_subject_filter(filter_edit.text())

    def apply_column_filter(self, column_index, filter_type, value1, value2):
        """Применить фильтр к столбцу"""
        logger.debug(f"Применение фильтра: col={column_index}, type={filter_type}, v1={value1}, v2={value2}")

    def apply_subject_filter(self, filter_text):
        """Применить фильтр к предметам"""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if isinstance(item, SubjectItem):
                item.setHidden(filter_text and filter_text not in item.subject_code)

    def show_column_config_dialog(self):
        """Показать диалог настройки столбцов"""
        available_columns = self.get_available_columns()
        dialog = ColumnConfigDialog(
            available_columns,
            self.column_manager.get_dynamic_columns(),
            self.column_manager,
            self.tree
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_columns = dialog.get_selected_columns()
            self.set_dynamic_columns(new_columns)

    def get_available_columns(self):
        """Получение всех доступных столбцов"""
        return [
            # Основные параметры
            {'key': 'cut_second', 'title': 'Обрезка (сек)', 'type': 'float', 'source': 'params'},
            {'key': 'gain', 'title': 'Усиление', 'type': 'float', 'source': 'params'},
            {'key': 'fixedlevel', 'title': 'Фиксированный уровень', 'type': 'float', 'source': 'params'},

            # Параметры каналов
            {'key': 'max_amplitude', 'title': 'Макс. амплитуда (В)', 'type': 'float', 'source': 'channel_params'},
            {'key': 'resonance_frequency', 'title': 'Резонансная частота (Гц)', 'type': 'float', 'source': 'channel_params'},
            {'key': 'bandwidth_707', 'title': 'Полоса -3 дБ (Гц)', 'type': 'float', 'source': 'channel_params'},
            {'key': 'bandwidth_fixed', 'title': 'Полоса фикс. уровня (Гц)', 'type': 'float', 'source': 'channel_params'},
            {'key': 'q_factor', 'title': 'Добротность', 'type': 'float', 'source': 'channel_params'},

            # Статистика
            {'key': 'raw_max_amp', 'title': 'Макс. амплитуда (сырая)', 'type': 'float', 'source': 'raw_data'},
            {'key': 'raw_min_amp', 'title': 'Мин. амплитуда (сырая)', 'type': 'float', 'source': 'raw_data'},

            # Время анализа
            {'key': 'analysis_start_time', 'title': 'Время начала анализа', 'type': 'float', 'source': 'processor'}
        ]

    def set_dynamic_columns(self, dynamic_columns_config):
        """Установка новых динамических столбцов"""
        self.column_manager.set_dynamic_columns(dynamic_columns_config)

        # Обновляем дерево
        self.tree.setColumnCount(self.column_manager.get_column_count())
        self.tree.setHeaderLabels(self.column_manager.get_headers())

        # ПРИНУДИТЕЛЬНО обновляем все существующие анализы
        self.force_update_all_analysis_display()

        # Испускаем сигнал об изменении столбцов
        self.columns_changed.emit(dynamic_columns_config)

        # logger.debug(f"Установлены новые столбцы: {len(self.dynamic_columns)}")

    def force_update_all_analysis_display(self):
        """Принудительное обновление отображения всех анализов"""
        logger.debug("Принудительное обновление всех анализов")
        for subject_code, subject_item in self.subject_items.items():
            for analysis_index in subject_item.get_all_analyses():
                analysis_item = subject_item.get_analysis(analysis_index)
                if analysis_item:
                    processor = getattr(analysis_item, 'processor', None)
                    # ОБНОВЛЯЕМ ДАННЫЕ ДАЖЕ ЕСЛИ ПРОЦЕССОР УЖЕ БЫЛ
                    self.fill_analysis_data(analysis_item, analysis_item.file_data['params'], processor)
                    logger.debug(f"Обновлен анализ: {subject_code}, {analysis_index}, процессор: {processor is not None}")

    def update_all_analysis_display(self):
        """Обновление отображения всех анализов"""
        for subject_code, subject_item in self.subject_items.items():
            for analysis_index in subject_item.get_all_analyses():
                analysis_item = subject_item.get_analysis(analysis_index)
                if analysis_item:
                    processor = getattr(analysis_item, 'processor', None)
                    self.fill_analysis_data(analysis_item, analysis_item.file_data['params'], processor)

    def handle_analysis_moved(self, old_subject, new_subject, analysis_index):
        """Обработка перемещения анализа между предметами"""
        logger.debug(f"Обработка перемещения: {old_subject} -> {new_subject}, индекс: {analysis_index}")

        if old_subject in self.subject_items and new_subject in self.subject_items:
            old_subject_item = self.subject_items[old_subject]
            new_subject_item = self.subject_items[new_subject]

            analysis_item = old_subject_item.get_analysis(analysis_index)
            if analysis_item:
                # Перемещаем анализ
                moved_item = old_subject_item.move_analysis_to(analysis_item, new_subject)
                new_subject_item.analyses[analysis_index] = moved_item
                new_subject_item.addChild(moved_item)

                # Обновляем кнопку графиков
                self.update_graph_button(moved_item, new_subject, analysis_index)

                # Обновляем чекбокс
                self.update_checkbox(moved_item, new_subject, analysis_index)

                # Испускаем сигнал для обновления DataManager
                self.analysis_moved.emit(old_subject, new_subject, analysis_index)
                logger.debug(f"Перемещение завершено успешно")
            else:
                logger.warning(f"Не найден анализ для перемещения: {old_subject}, {analysis_index}")
        else:
            logger.warning(f"Предметы не найдены: {old_subject} или {new_subject}")

    def update_graph_button(self, analysis_item, subject_code, analysis_index):
        """Обновление кнопки открытия графиков после перемещения"""
        logger.debug(f"Обновление кнопки графиков: {subject_code}, {analysis_index}")

        # Создаем новую кнопку с правильными параметрами
        new_graph_button = QPushButton('Открыть графики')
        new_graph_button.clicked.connect(lambda: self.item_selected.emit(subject_code, analysis_index))
        self.set_button_style(new_graph_button, 'normal')

        # Заменяем кнопку в дереве
        graph_button_index = self.column_manager.get_column_index('graph_button')
        self.tree.setItemWidget(analysis_item, graph_button_index, new_graph_button)
        analysis_item.graph_button = new_graph_button

    def update_checkbox(self, analysis_item, subject_code, analysis_index):
        """Обновление чекбокса после перемещения"""
        logger.debug(f"Обновление чекбокса: {subject_code}, {analysis_index}")

        # Сохраняем состояние старого чекбокса
        old_checked = analysis_item.get_checkbox_state()

        # Создаем новый чекбокс
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(old_checked)  # Сохраняем состояние
        checkbox_layout.addWidget(checkbox)

        checkbox_index = self.column_manager.get_column_index('checkbox')
        self.tree.setItemWidget(analysis_item, checkbox_index, checkbox_widget)
        analysis_item.checkbox_widget = checkbox_widget
        analysis_item.checkbox = checkbox

    def add_subject(self, subject_code=None):
        """Добавление нового предмета"""
        if subject_code is None:
            subject_code = f"AN{len(self.subject_items) + 1}"

        # Проверяем, нет ли уже предмета с таким кодом
        if subject_code in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет с кодом {subject_code} уже существует')
            return None

        # Создаем элемент предмета
        subject_item = SubjectItem(subject_code)
        self.tree.addTopLevelItem(subject_item)

        # Сохраняем ссылку
        self.subject_items[subject_code] = subject_item

        logger.debug(f"Предмет добавлен: {subject_code}. Всего предметов: {len(self.subject_items)}")

        self.subject_added.emit(subject_code)
        return subject_code

    def add_analysis_to_subject(self, subject_code, file_data, analysis_index=None, processor=None):
        """Добавление анализа к предмету"""
        logger.debug(f"Добавление анализа к предмету: {subject_code}, индекс: {analysis_index}")
        logger.debug(f"Процессор передан: {processor is not None}")

        if subject_code not in self.subject_items:
            logger.error(f"Предмет {subject_code} не найден")
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return None

        subject_item = self.subject_items[subject_code]

        # Добавляем анализ через SubjectItem
        analysis_item, actual_index = subject_item.add_analysis(file_data, analysis_index, processor)

        # Устанавливаем виджеты в дереве
        checkbox_index = self.column_manager.get_column_index('checkbox')
        self.tree.setItemWidget(analysis_item, checkbox_index, analysis_item.checkbox_widget)

        # Настраиваем кнопку графиков
        analysis_item.graph_button.clicked.connect(
            lambda: self.item_selected.emit(subject_code, actual_index)
        )
        self.set_button_style(analysis_item.graph_button, 'normal')

        graph_button_index = self.column_manager.get_column_index('graph_button')
        self.tree.setItemWidget(analysis_item, graph_button_index, analysis_item.graph_button)

        # Заполняем данные
        self.fill_analysis_data(analysis_item, file_data['params'], processor)

        logger.debug(f"Анализ добавлен: {subject_code}, индекс: {actual_index}")

        self.analysis_added.emit(subject_code, actual_index)
        return actual_index

    def fill_analysis_data(self, analysis_item, params, processor=None):
        """Заполнение данных анализа"""
        # Заполняем базовые параметры
        self.fill_basic_parameters(analysis_item, params)

        # Заполняем динамические столбцы
        if processor:
            logger.debug(f"Заполняем динамические столбцы для анализа")
            self.fill_dynamic_columns(analysis_item, processor)
        else:
            # Если процессора нет, заполняем NaN для динамических столбцов
            logger.debug(f"Процессор не передан, заполняем NaN")
            self.fill_empty_dynamic_columns(analysis_item)

    def fill_basic_parameters(self, analysis_item, params):
        """Заполнение базовых параметров"""
        # Устанавливаем код предмета (наследуется от родителя)
        subject_code_index = self.column_manager.get_column_index('subject_code')
        analysis_item.setText(subject_code_index, "")

        # Устанавливаем имя файла
        file_name_index = self.column_manager.get_column_index('file_name')
        analysis_item.setText(file_name_index, analysis_item.file_data['file_name'])

        # Устанавливаем параметры
        param_columns = ['start_freq', 'end_freq', 'record_time']
        for param_key in param_columns:
            index = self.column_manager.get_column_index(param_key)
            value = params.get(param_key, 'NaN')
            analysis_item.setText(index, str(value))

    def fill_dynamic_columns(self, analysis_item, processor):
        """Заполнение динамических столбцов"""
        try:
            for column_config in self.column_manager.get_dynamic_columns():
                value = self.get_column_value(processor, column_config)
                analysis_item.setText(column_config['index'], value)
        except Exception as e:
            logger.error(f"Ошибка заполнения динамических столбцов: {str(e)}")

    def fill_empty_dynamic_columns(self, analysis_item):
        """Заполнение динамических столбцов значениями NaN при отсутствии процессора"""
        for column_config in self.column_manager.get_dynamic_columns():
            analysis_item.setText(column_config['index'], "NaN")

    def get_column_value(self, processor, column_config):
        """Получение значения столбца из процессора для выбранного канала"""
        try:
            column_key = column_config['key']
            source = column_config['source']
            column_type = column_config.get('type', 'string')

            value = None

            if source == 'params':
                # Параметры из processor.params
                value = processor.params.get(column_key, float('nan'))
                logger.debug(f"Параметр {column_key}: {value}")

            elif source == 'channel_params':
                # Параметры каналов - берем выбранный канал
                try:
                    channel_params = processor.channel_parameters
                    logger.debug(f"Доступные channel_parameters: {list(channel_params.keys()) if channel_params else 'None'}")

                    if channel_params:
                        selected_channel = processor.params.get('selected_channel', 'CH2')
                        logger.debug(f"Выбранный канал: {selected_channel}")

                        if selected_channel in channel_params:
                            value = channel_params[selected_channel].get(column_key, float('nan'))
                            logger.debug(f"Значение {column_key} для {selected_channel}: {value}")
                        else:
                            # Если выбранного канала нет, берем первый доступный
                            first_channel_name = next(iter(channel_params.keys()))
                            first_channel = channel_params[first_channel_name]
                            value = first_channel.get(column_key, float('nan'))
                            logger.debug(f"Значение {column_key} для первого канала {first_channel_name}: {value}")
                    else:
                        value = float('nan')
                        logger.debug(f"channel_params пуст для {column_key}")
                except Exception as e:
                    logger.error(f"Ошибка получения channel_params для {column_key}: {str(e)}")
                    value = float('nan')

            elif source == 'raw_data':
                # Сырые данные - берем выбранный канал
                try:
                    raw_data = getattr(processor, f'raw_{column_key}', {})
                    logger.debug(f"Доступные raw_data для {column_key}: {list(raw_data.keys()) if raw_data else 'None'}")

                    if raw_data:
                        selected_channel = processor.params.get('selected_channel', 'CH2')
                        value = raw_data.get(selected_channel, float('nan'))
                        logger.debug(f"Raw значение {column_key} для {selected_channel}: {value}")
                    else:
                        value = float('nan')
                except Exception as e:
                    logger.error(f"Ошибка получения raw_data для {column_key}: {str(e)}")
                    value = float('nan')

            elif source == 'processor':
                # Свойства процессора
                try:
                    value = getattr(processor, column_key, float('nan'))
                    logger.debug(f"Процессор свойство {column_key}: {value}")
                except Exception as e:
                    logger.error(f"Ошибка получения свойства процессора {column_key}: {str(e)}")
                    value = float('nan')
            else:
                value = float('nan')

            # Форматирование значения
            if column_type == 'float':
                if isinstance(value, (int, float)) and not np.isnan(value):
                    return f"{value:.4f}"
                else:
                    return "NaN"
            else:
                return str(value) if value is not None and not np.isnan(value) else "NaN"

        except Exception as e:
            logger.error(f"Ошибка получения значения {column_config['key']}: {str(e)}")
            return "NaN"

    def load_files_to_subject(self, subject_code, file_paths):
        """Загрузка файлов в указанный предмет"""
        logger.debug(f"Загрузка {len(file_paths)} файлов в предмет: {subject_code}")

        if subject_code not in self.subject_items:
            logger.error(f"Предмет {subject_code} не найден")
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return

        for file_path in file_paths:
            logger.debug(f"Загрузка файла: {file_path}")
            self.file_loaded.emit(subject_code, file_path)

    def get_selected_subject(self):
        """Получение выбранного предмета"""
        current_item = self.tree.currentItem()
        if isinstance(current_item, SubjectItem):
            subject_code = current_item.subject_code
            logger.debug(f"Выбран предмет: {subject_code}")
            return subject_code
        elif isinstance(current_item, AnalysisItem):
            subject_code = current_item.subject_code
            logger.debug(f"Выбран анализ в предмете: {subject_code}")
            return subject_code
        logger.debug("Ничего не выбрано")
        return None

    def get_selected_analysis_index(self):
        """Получение индекса выбранного анализа"""
        current_item = self.tree.currentItem()
        if isinstance(current_item, AnalysisItem):
            analysis_index = current_item.analysis_index
            logger.debug(f"Выбран анализ с индексом: {analysis_index}")
            return analysis_index
        logger.debug("Анализ не выбран")
        return -1

    def get_analysis_checkbox_state(self, subject_code, analysis_index):
        """Получение состояния чекбокса анализа"""
        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item:
                state = analysis_item.get_checkbox_state()
                logger.debug(f"Состояние чекбокса {subject_code}, {analysis_index}: {state}")
                return state
        logger.warning(f"Анализ не найден: {subject_code}, {analysis_index}")
        return False

    def get_all_subjects(self):
        """Получение списка всех предметов"""
        subjects = list(self.subject_items.keys())
        logger.debug(f"Всего предметов: {len(subjects)}")
        return subjects

    def get_subject_analyses(self, subject_code):
        """Получение списка анализов предмета"""
        if subject_code in self.subject_items:
            analyses = self.subject_items[subject_code].get_all_analyses()
            logger.debug(f"Предмет {subject_code} имеет {len(analyses)} анализов")
            return analyses
        logger.warning(f"Предмет {subject_code} не найден")
        return []

    def get_selected_analyses(self):
        """Получение списка выбранных анализов (с включенными чекбоксами)"""
        selected = []
        for subject_code, subject_item in self.subject_items.items():
            selected_analyses = subject_item.get_selected_analyses()
            for analysis_index in selected_analyses:
                selected.append((subject_code, analysis_index))

        logger.debug(f"Выбрано анализов: {len(selected)}")
        return selected

    def update_analysis_display(self, subject_code, analysis_index, success, file_name, message=None, processor=None):
        """Обновление отображения анализа после загрузки"""
        logger.debug(f"Обновление отображения анализа: {subject_code}, {analysis_index}, успех: {success}")

        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]

            # ОБНОВЛЯЕМ ДАННЫЕ ФАЙЛА В АНАЛИЗЕ
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item and success:
                analysis_item.file_data['file_name'] = file_name

            subject_item.update_analysis_display(analysis_index, success, file_name, message)

            # Обновляем стиль кнопки
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item and analysis_item.graph_button:
                if success:
                    self.set_button_style(analysis_item.graph_button, 'success')
                    logger.debug(f"Отображение обновлено успешно для {subject_code}, {analysis_index}")
                else:
                    if message and 'вручную' in message:
                        self.set_button_style(analysis_item.graph_button, 'warning')
                        logger.debug(f"Отображение обновлено с предупреждением для {subject_code}, {analysis_index}")
                    else:
                        self.set_button_style(analysis_item.graph_button, 'error')
                        logger.debug(f"Отображение обновлено с ошибкой для {subject_code}, {analysis_index}")

            # Обновляем данные анализа (включая динамические столбцы)
            if analysis_item:
                # ОБНОВЛЯЕМ ПРОЦЕССОР если он передан
                if processor:
                    analysis_item.processor = processor
                    logger.debug(f"Процессор обновлен для {subject_code}, {analysis_index}")

                # ВСЕГДА обновляем данные анализа, даже если процессор уже был
                current_processor = getattr(analysis_item, 'processor', None)
                self.fill_analysis_data(analysis_item, analysis_item.file_data['params'], current_processor)
        else:
            logger.error(f"Предмет {subject_code} не найден при обновлении отображения")

    def update_analysis_params(self, subject_code, analysis_index, params):
        """Обновление параметров анализа"""
        logger.debug(f"Обновление параметров анализа: {subject_code}, {analysis_index}")

        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item:
                analysis_item.file_data['params'] = params
                self.fill_basic_parameters(analysis_item, params)
                logger.debug(f"Параметры обновлены для {subject_code}, {analysis_index}")
        else:
            logger.error(f"Предмет {subject_code} не найден при обновлении параметров")

    def show_context_menu(self, position):
        """Показать контекстное меню"""
        item = self.tree.itemAt(position)
        menu = QMenu()

        if item is None:
            # Контекстное меню для заголовков
            configure_columns_action = QAction("Настроить столбцы...", self.tree)
            configure_columns_action.triggered.connect(self.show_column_config_dialog)
            menu.addAction(configure_columns_action)
        elif isinstance(item, SubjectItem):  # Предмет
            add_analysis_action = QAction("Добавить анализ", self.tree)
            delete_subject_action = QAction("Удалить предмет", self.tree)
            filter_subject_action = QAction("Фильтровать предмет...", self.tree)

            menu.addAction(add_analysis_action)
            menu.addAction(delete_subject_action)
            menu.addAction(filter_subject_action)

            add_analysis_action.triggered.connect(self.load_files_to_current_subject)
            delete_subject_action.triggered.connect(self.delete_current_subject)
            filter_subject_action.triggered.connect(self.show_subject_filter)

        elif isinstance(item, AnalysisItem):  # Анализ
            delete_analysis_action = QAction("Удалить анализ", self.tree)
            menu.addAction(delete_analysis_action)
            delete_analysis_action.triggered.connect(self.delete_current_analysis)

        menu.exec(self.tree.mapToGlobal(position))

    def load_files_to_current_subject(self):
        """Загрузка файлов в текущий выбранный предмет"""
        subject_code = self.get_selected_subject()
        if not subject_code:
            QMessageBox.information(None, 'Информация', 'Выберите предмет для добавления анализов')
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            None,
            'Выберите файлы данных',
            '',
            'Excel Files (*.xlsx *.xls *.csv);;All Files (*)'
        )

        if file_paths:
            self.load_files_to_subject(subject_code, file_paths)

    def delete_current_subject(self):
        """Удаление текущего выбранного предмета"""
        subject_code = self.get_selected_subject()
        if not subject_code:
            return

        reply = QMessageBox.question(
            None,
            'Подтверждение',
            f'Удалить предмет {subject_code} и все его анализы?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if subject_code in self.subject_items:
                subject_item = self.subject_items.pop(subject_code)
                index = self.tree.indexOfTopLevelItem(subject_item)
                if index >= 0:
                    self.tree.takeTopLevelItem(index)
                logger.debug(f"Предмет {subject_code} удален")

    def delete_current_analysis(self):
        """Удаление текущего выбранного анализа"""
        subject_code = self.get_selected_subject()
        analysis_index = self.get_selected_analysis_index()

        if not subject_code or analysis_index == -1:
            return

        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            if subject_item.remove_analysis(analysis_index):
                logger.debug(f"Анализ удален: {subject_code}, {analysis_index}")

    def clear_tree(self):
        """Очистка всего дерева"""
        self.tree.clear()
        self.subject_items.clear()
        logger.debug("Дерево очищено")

    def on_item_changed(self, item, column):
        """Просто обновляем отображаемое имя при редактировании"""
        if column == self.column_manager.get_column_index('subject_code') and isinstance(item, SubjectItem):
            new_name = item.text(column).strip()
            if new_name:
                item.subject_name = new_name

    def get_subject_name(self, subject_code):
        """Получение отображаемого имени предмета"""
        if subject_code in self.subject_items:
            return self.subject_items[subject_code].subject_name
        return subject_code

    def get_all_subject_names(self):
        """Получение всех имен предметов"""
        return {code: item.subject_name for code, item in self.subject_items.items()}

    def set_subject_name(self, subject_code, subject_name):
        """Установка имени для предмета"""
        if subject_code in self.subject_items:
            self.subject_items[subject_code].subject_name = subject_name
            subject_code_index = self.column_manager.get_column_index('subject_code')
            self.subject_items[subject_code].setText(subject_code_index, subject_name)

    def get_analysis_item(self, subject_code, analysis_index):
        """Получение AnalysisItem по subject_code и analysis_index"""
        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            return subject_item.get_analysis(analysis_index)
        return None

    def set_button_style(self, button, style_type='normal'):
        """Установка стиля для кнопки"""
        if style_type == 'success':
            button.setStyleSheet(BUTTON_STYLE_SUCCESS)
        elif style_type == 'error':
            button.setStyleSheet(BUTTON_STYLE_ERROR)
        elif style_type == 'warning':
            button.setStyleSheet(BUTTON_STYLE_WARNING)
        else:
            button.setStyleSheet(BUTTON_STYLE_NORMAL)

    def apply_column_filter(self, column_index, filter_type, value1, value2):
        """Применить фильтр к столбцу"""
        column_config = self.column_manager.get_column_by_index(column_index)
        if column_config:
            column_key = column_config['key']
            self.filter_manager.set_filter(column_key, filter_type, value1, value2)
            self.apply_filters()
        else:
            logger.warning(f"Не найдена конфигурация столбца для индекса {column_index}")

    def apply_subject_filter(self, filter_text):
        """Применить фильтр к предметам"""
        # Для фильтрации по предметам используем специальный ключ
        self.filter_manager.set_filter('_subject_code', 'Равно', filter_text)
        self.apply_filters()

    def show_all_items(self):
        """Показать все предметы и анализы"""
        logger.debug("Показ всех элементов дерева")

        for subject_code, subject_item in self.subject_items.items():
            # ВСЕГДА показываем предмет
            subject_item.setHidden(False)

            # Показываем все анализы предмета
            for analysis_index in subject_item.get_all_analyses():
                analysis_item = subject_item.get_analysis(analysis_index)
                if analysis_item:
                    analysis_item.setHidden(False)

            # Разворачиваем предмет, чтобы были видны анализы
            subject_item.setExpanded(True)

    def apply_filters(self):
        """Применить все активные фильтры к дереву"""
        logger.debug("Применение фильтров к дереву")

        # Если нет фильтров - показываем всё
        if not self.filter_manager.get_filters():
            self.show_all_items()
            return

        # Применяем фильтры
        any_visible = False
        for subject_code, subject_item in self.subject_items.items():
            visible_analyses = 0

            # Проверяем фильтр по коду предмета
            subject_passed_filter = self._check_subject_filter(subject_code)

            for analysis_index in subject_item.get_all_analyses():
                analysis_item = subject_item.get_analysis(analysis_index)
                if analysis_item:
                    analysis_passed_filter = self._check_analysis_filters(subject_code, analysis_index)
                    analysis_item.setHidden(not analysis_passed_filter)

                    if analysis_passed_filter:
                        visible_analyses += 1

            # ПРЕДМЕТ ВИДИМ, ЕСЛИ:
            # 1. Он прошел фильтр по коду И имеет видимые анализы
            # 2. ИЛИ он пустой (нет анализов) - чтобы можно было добавлять файлы
            is_empty_subject = len(subject_item.get_all_analyses()) == 0
            subject_visible = (subject_passed_filter and visible_analyses > 0) or is_empty_subject

            subject_item.setHidden(not subject_visible)

            if subject_visible:
                any_visible = True
                subject_item.setExpanded(True)

        # Если после фильтрации ничего не видно, показываем сообщение
        if not any_visible:
            logger.debug("После применения фильтров не осталось видимых элементов")

    def _check_subject_filter(self, subject_code: str) -> bool:
        """Проверить фильтр для предмета"""
        filters = self.filter_manager.get_filters()
        subject_filter = filters.get('_subject_code')

        if not subject_filter:
            return True

        filter_type = subject_filter['type']
        filter_value = subject_filter['value1']

        if not filter_value:
            return True

        if filter_type == 'Равно':
            return filter_value.lower() in subject_code.lower()

        return True

    def _check_analysis_filters(self, subject_code: str, analysis_index: int) -> bool:
        """Проверить фильтры для анализа"""
        analysis_data = self.data_manager.get_analysis_data(subject_code, analysis_index)
        if not analysis_data:
            return False

        return self.filter_manager.apply_filters(analysis_data, self.column_manager)

    def clear_filters(self):
        """Очистить все фильтры"""
        self.filter_manager.clear_filters()
        self.apply_filters()

    # Обновим show_column_filter для лучшего UX
    def show_column_filter(self, column_index):
        """Показать диалог фильтрации для столбца"""
        column_config = self.column_manager.get_column_by_index(column_index)
        if column_config:
            column_key = column_config['key']
            column_title = column_config['title']

            # Получаем текущий фильтр для этого столбца
            current_filters = self.filter_manager.get_filters()
            current_filter = current_filters.get(column_key, {})

            dialog = QDialog(self.tree)
            dialog.setWindowTitle(f'Фильтр: {column_title}')
            dialog.setModal(True)
            layout = QVBoxLayout(dialog)

            # Выбор типа фильтра
            filter_type = QComboBox()
            filter_type.addItems(['Все значения', 'Равно', 'Больше', 'Меньше', 'Между'])
            layout.addWidget(QLabel('Тип фильтра:'))
            layout.addWidget(filter_type)

            # Поля для значений
            value1_layout = QHBoxLayout()
            value1_layout.addWidget(QLabel('Значение:'))
            value1_edit = QLineEdit()
            # Заполняем текущее значение фильтра
            if current_filter:
                value1_edit.setText(str(current_filter.get('value1', '')))
            value1_layout.addWidget(value1_edit)
            layout.addLayout(value1_layout)

            value2_layout = QHBoxLayout()
            value2_layout.addWidget(QLabel('До:'))
            value2_edit = QLineEdit()
            # Заполняем текущее значение фильтра
            if current_filter:
                value2_edit.setText(str(current_filter.get('value2', '')))
            value2_layout.addWidget(value2_edit)
            value2_layout.setEnabled(False)
            layout.addLayout(value2_layout)

            # Кнопка очистки фильтров
            clear_button = QPushButton('Очистить все фильтры')
            clear_button.clicked.connect(lambda: self.clear_filters_and_close(dialog))
            layout.addWidget(clear_button)

            # Кнопки диалога
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            # Логика включения полей
            def update_fields(index):
                is_between = index == 4  # "Между"
                value2_layout.setEnabled(is_between)
                # Устанавливаем текущий тип фильтра
                if current_filter and index == 0:
                    filter_type.setCurrentText(current_filter.get('type', 'Все значения'))

            filter_type.currentIndexChanged.connect(update_fields)

            # Устанавливаем текущий тип фильтра
            if current_filter:
                filter_type_map = {
                    'Равно': 1, 'Больше': 2, 'Меньше': 3, 'Между': 4
                }
                current_type = current_filter.get('type', 'Все значения')
                filter_type.setCurrentIndex(filter_type_map.get(current_type, 0))
            else:
                filter_type.setCurrentIndex(0)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.apply_column_filter(
                    column_index,
                    filter_type.currentText(),
                    value1_edit.text(),
                    value2_edit.text() if value2_layout.isEnabled() else None
                )

    def clear_filters_and_close(self, dialog):
        """Очистить все фильтры и закрыть диалог"""
        self.clear_filters()
        dialog.accept()

    # Обновим контекстное меню для добавления очистки фильтров
    def show_context_menu(self, position):
        """Показать контекстное меню"""
        item = self.tree.itemAt(position)
        menu = QMenu()

        if item is None:
            # Контекстное меню для заголовков
            configure_columns_action = QAction("Настроить столбцы...", self.tree)
            configure_columns_action.triggered.connect(self.show_column_config_dialog)
            menu.addAction(configure_columns_action)

            # Добавляем очистку фильтров
            clear_filters_action = QAction("Очистить все фильтры", self.tree)
            clear_filters_action.triggered.connect(self.clear_filters)
            menu.addAction(clear_filters_action)

        elif isinstance(item, SubjectItem):  # Предмет
            add_analysis_action = QAction("Добавить анализ", self.tree)
            delete_subject_action = QAction("Удалить предмет", self.tree)
            filter_subject_action = QAction("Фильтровать предмет...", self.tree)

            menu.addAction(add_analysis_action)
            menu.addAction(delete_subject_action)
            menu.addAction(filter_subject_action)

            add_analysis_action.triggered.connect(self.load_files_to_current_subject)
            delete_subject_action.triggered.connect(self.delete_current_subject)
            filter_subject_action.triggered.connect(self.show_subject_filter)

        elif isinstance(item, AnalysisItem):  # Анализ
            delete_analysis_action = QAction("Удалить анализ", self.tree)
            menu.addAction(delete_analysis_action)
            delete_analysis_action.triggered.connect(self.delete_current_analysis)

        menu.exec(self.tree.mapToGlobal(position))