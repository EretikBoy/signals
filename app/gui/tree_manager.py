#gui/tree_manager.py

from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton, 
    QFileDialog, QMessageBox, QMenu, QCheckBox, QHBoxLayout, QWidget
)
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from utils.constants import BUTTON_STYLE_NORMAL, BUTTON_STYLE_SUCCESS, BUTTON_STYLE_ERROR, BUTTON_STYLE_WARNING


class TreeManager(QObject):
    """Управление древовидной таблицей с предметами и анализами"""
    
    # Сигналы
    file_loaded = pyqtSignal(str, str)  # subject_code, file_path
    subject_added = pyqtSignal(str)  # subject_code
    analysis_added = pyqtSignal(str, int)  # subject_code, analysis_index
    item_selected = pyqtSignal(str, int)  # subject_code, analysis_index (-1 для предмета)
    analysis_moved = pyqtSignal(str, str, int)  # old_subject, new_subject, analysis_index
    
    def __init__(self, tree_widget):
        super().__init__()
        self.tree = tree_widget
        self.setup_tree()
        
        # Данные для хранения связи между элементами дерева и данными
        self.subject_items = {}  # subject_code -> QTreeWidgetItem
        self.analysis_items = {}  # (subject_code, analysis_index) -> QTreeWidgetItem
        self.next_analysis_index = 0
        
        # Настройка drag & drop
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
    
    def setup_tree(self):
        """Настройка древовидной таблицы"""
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels([
            'Выбор', 
            'Код предмета', 
            'Файл анализа', 
            'Графики и \nподстройка значений', 
            'Начальная частота (Гц)', 
            'Конечная частота (Гц)', 
            'Время записи (сек)'
        ])
        
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Подключаем контекстное меню
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
    
    def add_subject(self, subject_code=None):
        """Добавление нового предмета"""
        if subject_code is None:
            subject_code = f"AN{len(self.subject_items) + 1}"
        
        # Проверяем, нет ли уже предмета с таким кодом
        if subject_code in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет с кодом {subject_code} уже существует')
            return None
        
        # Создаем элемент предмета
        subject_item = QTreeWidgetItem(self.tree)
        subject_item.setText(1, subject_code)
        subject_item.setFlags(subject_item.flags() | Qt.ItemFlag.ItemIsEditable)
        
        # Делаем предмет расширяемым
        subject_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        
        # Сохраняем ссылку
        self.subject_items[subject_code] = subject_item
        
        self.subject_added.emit(subject_code)
        return subject_code
    
    def add_analysis_to_subject(self, subject_code, file_data):
        """Добавление анализа к предмету"""
        if subject_code not in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return None
        
        subject_item = self.subject_items[subject_code]
        analysis_index = self.next_analysis_index
        self.next_analysis_index += 1
        
        # Создаем элемент анализа
        analysis_item = QTreeWidgetItem(subject_item)
        
        # Чекбокс для выбора
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        checkbox_layout.addWidget(checkbox)
        
        self.tree.setItemWidget(analysis_item, 0, checkbox_widget)
        
        # Информация об анализе
        analysis_item.setText(1, "")  # Код предмета наследуется от родителя
        analysis_item.setText(2, file_data['file_name'])
        
        # Кнопка открытия графиков
        graph_button = QPushButton('Открыть графики')
        graph_button.clicked.connect(lambda: self.item_selected.emit(subject_code, analysis_index))
        self.set_button_style(graph_button, 'normal')
        self.tree.setItemWidget(analysis_item, 3, graph_button)
        
        # Параметры
        analysis_item.setText(4, str(file_data['params']['start_freq']))
        analysis_item.setText(5, str(file_data['params']['end_freq']))
        analysis_item.setText(6, str(file_data['params']['record_time']))
        
        # Сохраняем ссылку
        self.analysis_items[(subject_code, analysis_index)] = analysis_item
        
        # Разворачиваем предмет, чтобы показать анализы
        subject_item.setExpanded(True)
        
        self.analysis_added.emit(subject_code, analysis_index)
        return analysis_index
    
    def load_files_to_subject(self, subject_code, file_paths):
        """Загрузка файлов в указанный предмет"""
        if subject_code not in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return
        
        for file_path in file_paths:
            self.file_loaded.emit(subject_code, file_path)
    
    def get_selected_subject(self):
        """Получение выбранного предмета"""
        current_item = self.tree.currentItem()
        if current_item and not current_item.parent():  # Только предметы (корневые элементы)
            return current_item.text(1)
        elif current_item and current_item.parent():  # Анализ - возвращаем родителя
            return current_item.parent().text(1)
        return None
    
    def get_selected_analysis_index(self):
        """Получение индекса выбранного анализа"""
        current_item = self.tree.currentItem()
        if current_item and current_item.parent():  # Анализ
            subject_code = current_item.parent().text(1)
            for (subj, idx), item in self.analysis_items.items():
                if item == current_item and subj == subject_code:
                    return idx
        return -1
    
    def get_analysis_checkbox_state(self, subject_code, analysis_index):
        """Получение состояния чекбокса анализа"""
        key = (subject_code, analysis_index)
        if key in self.analysis_items:
            analysis_item = self.analysis_items[key]
            checkbox_widget = self.tree.itemWidget(analysis_item, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.layout().itemAt(0).widget()
                return checkbox.isChecked()
        return False
    
    def get_all_subjects(self):
        """Получение списка всех предметов"""
        return list(self.subject_items.keys())
    
    def get_subject_analyses(self, subject_code):
        """Получение списка анализов предмета"""
        analyses = []
        for (subj, idx) in self.analysis_items.keys():
            if subj == subject_code:
                analyses.append(idx)
        return analyses
    
    def get_selected_analyses(self):
        """Получение списка выбранных анализов (с включенными чекбоксами)"""
        selected = []
        for (subject_code, analysis_index), analysis_item in self.analysis_items.items():
            if self.get_analysis_checkbox_state(subject_code, analysis_index):
                selected.append((subject_code, analysis_index))
        return selected
    
    def update_analysis_display(self, subject_code, analysis_index, success, file_name, message=None):
        """Обновление отображения анализа после загрузки"""
        key = (subject_code, analysis_index)
        if key not in self.analysis_items:
            return
        
        analysis_item = self.analysis_items[key]
        graph_button = self.tree.itemWidget(analysis_item, 3)
        
        if success:
            analysis_item.setText(2, file_name)
            graph_button.setText('Открыть графики')
            self.set_button_style(graph_button, 'success')
        else:
            if message and 'вручную' in message:
                analysis_item.setText(2, f'Установите параметры: {file_name}')
                self.set_button_style(graph_button, 'warning')
            else:
                analysis_item.setText(2, 'Ошибка загрузки')
                self.set_button_style(graph_button, 'error')
    
    def update_analysis_params(self, subject_code, analysis_index, params):
        """Обновление параметров анализа"""
        key = (subject_code, analysis_index)
        if key in self.analysis_items:
            analysis_item = self.analysis_items[key]
            analysis_item.setText(4, str(params['start_freq']))
            analysis_item.setText(5, str(params['end_freq']))
            analysis_item.setText(6, str(params['record_time']))
    
    def move_analysis(self, analysis_key, new_subject_code):
        """Перемещение анализа в другой предмет"""
        old_subject_code, analysis_index = analysis_key
        
        if old_subject_code == new_subject_code:
            return  # Не нужно перемещать в тот же предмет
        
        if new_subject_code not in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет {new_subject_code} не найден')
            return
        
        # Получаем элемент анализа
        analysis_item = self.analysis_items.get((old_subject_code, analysis_index))
        if not analysis_item:
            return
        
        # Получаем новый родительский элемент
        new_subject_item = self.subject_items[new_subject_code]
        
        # Клонируем элемент анализа
        new_analysis_item = analysis_item.clone()
        
        # Обновляем связи
        del self.analysis_items[(old_subject_code, analysis_index)]
        self.analysis_items[(new_subject_code, analysis_index)] = new_analysis_item
        
        # Удаляем старый элемент и добавляем новый
        old_subject_item = analysis_item.parent()
        old_subject_item.removeChild(analysis_item)
        new_subject_item.addChild(new_analysis_item)
        
        # Обновляем отображение
        new_subject_item.setExpanded(True)
        
        self.analysis_moved.emit(old_subject_code, new_subject_code, analysis_index)
    
    def show_context_menu(self, position):
        """Показать контекстное меню"""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        if not item.parent():  # Предмет
            add_analysis_action = menu.addAction("Добавить анализ")
            delete_subject_action = menu.addAction("Удалить предмет")
            
            action = menu.exec(self.tree.mapToGlobal(position))
            
            if action == add_analysis_action:
                self.load_files_to_current_subject()
            elif action == delete_subject_action:
                self.delete_current_subject()
        
        else:  # Анализ
            delete_analysis_action = menu.addAction("Удалить анализ")
            
            action = menu.exec(self.tree.mapToGlobal(position))
            
            if action == delete_analysis_action:
                self.delete_current_analysis()
    
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
            # Удаляем все анализы предмета
            analyses_to_delete = []
            for key in list(self.analysis_items.keys()):
                if key[0] == subject_code:
                    analyses_to_delete.append(key)
            
            for key in analyses_to_delete:
                del self.analysis_items[key]
            
            # Удаляем предмет
            subject_item = self.subject_items.pop(subject_code)
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(subject_item))
    
    def delete_current_analysis(self):
        """Удаление текущего выбранного анализа"""
        subject_code = self.get_selected_subject()
        analysis_index = self.get_selected_analysis_index()
        
        if not subject_code or analysis_index == -1:
            return
        
        key = (subject_code, analysis_index)
        if key not in self.analysis_items:
            return
        
        reply = QMessageBox.question(
            None, 
            'Подтверждение', 
            'Удалить выбранный анализ?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            analysis_item = self.analysis_items.pop(key)
            parent_item = analysis_item.parent()
            parent_item.removeChild(analysis_item)
    
    def clear_tree(self):
        """Очистка всего дерева"""
        self.tree.clear()
        self.subject_items.clear()
        self.analysis_items.clear()
        self.next_analysis_index = 0
    
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