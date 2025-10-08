# gui/tree_manager.py

from PyQt6.QtWidgets import (
    QTreeWidgetItem, QHeaderView, QPushButton, 
    QFileDialog, QMessageBox, QMenu, QCheckBox, QHBoxLayout, QWidget
)
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtGui import QAction

from gui.tree_widget import TreeWidget
from gui.tree_items import SubjectItem, AnalysisItem
from utils.constants import BUTTON_STYLE_NORMAL, BUTTON_STYLE_SUCCESS, BUTTON_STYLE_ERROR, BUTTON_STYLE_WARNING

import logging

logger = logging.getLogger(__name__)


class TreeManager(QObject):
    """Управление древовидной таблицей с предметами и анализами"""
    
    # Сигналы
    file_loaded = pyqtSignal(str, str)  # subject_code, file_path
    subject_added = pyqtSignal(str)  # subject_code
    analysis_added = pyqtSignal(str, int)  # subject_code, analysis_index
    item_selected = pyqtSignal(str, int)  # subject_code, analysis_index (-1 для предмета)
    analysis_moved = pyqtSignal(str, str, int)  # old_subject, new_subject, analysis_index
    
    def __init__(self):
        super().__init__()
        self.tree = TreeWidget()
        self.setup_tree()
        
        # Данные для хранения связи между элементами дерева и данными
        self.subject_items = {}  # subject_code -> SubjectItem
        self.next_analysis_index = 0
        
        # Подключаем сигнал перемещения
        self.tree.analysis_moved.connect(self.handle_analysis_moved)
    
    def setup_tree(self):
        """Настройка древовидной таблицы"""
        logger.debug("Настройка древовидной таблицы")
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
        
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Подключаем контекстное меню
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
    
    def handle_analysis_moved(self, old_subject, new_subject, analysis_index):
        """Обработка перемещения анализа между предметами"""
        logger.debug(f"Обработка перемещения: {old_subject} -> {new_subject}, индекс: {analysis_index}")
        
        if old_subject in self.subject_items and new_subject in self.subject_items:
            old_subject_item = self.subject_items[old_subject]
            new_subject_item = self.subject_items[new_subject]
            
            analysis_item = old_subject_item.get_analysis(analysis_index)
            if analysis_item:
                # Перемещаем анализ - ИСПРАВЛЕНИЕ: используем new_subject вместо new_subject_code
                moved_item = old_subject_item.move_analysis_to(analysis_item, new_subject)
                new_subject_item.analyses[analysis_index] = moved_item
                new_subject_item.addChild(moved_item)
                
                # Обновляем кнопку графиков
                self.update_graph_button(moved_item, new_subject, analysis_index)
                
                # Обновляем чекбокс
                self.update_checkbox(moved_item, new_subject, analysis_index)
                
                # Испускаем сигнал для обновления DataManager
                self.analysis_moved.emit(old_subject, new_subject, analysis_index)
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
        self.tree.setItemWidget(analysis_item, 3, new_graph_button)
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
        
        self.tree.setItemWidget(analysis_item, 0, checkbox_widget)
        analysis_item.checkbox_widget = checkbox_widget
        analysis_item.checkbox = checkbox
    
    def add_subject(self, subject_code=None):
        """Добавление нового предмета"""
        logger.debug(f"Добавление предмета: {subject_code}")
        
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
        
        self.subject_added.emit(subject_code)
        logger.debug(f"Предмет добавлен: {subject_code}")
        return subject_code
    
    def add_analysis_to_subject(self, subject_code, file_data):
        """Добавление анализа к предмету"""
        logger.debug(f"Добавление анализа к предмету: {subject_code}")
        
        if subject_code not in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return None
        
        subject_item = self.subject_items[subject_code]
        analysis_index = self.next_analysis_index
        self.next_analysis_index += 1
        
        logger.debug(f"Создание анализа с индексом: {analysis_index}")
        
        # Добавляем анализ через SubjectItem
        analysis_item = subject_item.add_analysis(analysis_index, file_data)
        
        # Устанавливаем виджеты в дереве
        self.tree.setItemWidget(analysis_item, 0, analysis_item.checkbox_widget)
        
        # Настраиваем кнопку графиков
        analysis_item.graph_button.clicked.connect(
            lambda: self.item_selected.emit(subject_code, analysis_index)
        )
        self.set_button_style(analysis_item.graph_button, 'normal')
        self.tree.setItemWidget(analysis_item, 3, analysis_item.graph_button)
        
        self.analysis_added.emit(subject_code, analysis_index)
        logger.debug(f"Анализ добавлен: {subject_code}, {analysis_index}")
        
        return analysis_index
    
    def load_files_to_subject(self, subject_code, file_paths):
        """Загрузка файлов в указанный предмет"""
        logger.debug(f"Загрузка файлов в предмет: {subject_code}")
        
        if subject_code not in self.subject_items:
            QMessageBox.warning(None, 'Ошибка', f'Предмет {subject_code} не найден')
            return
        
        for file_path in file_paths:
            self.file_loaded.emit(subject_code, file_path)
    
    def get_selected_subject(self):
        """Получение выбранного предмета"""
        current_item = self.tree.currentItem()
        if isinstance(current_item, SubjectItem):
            return current_item.subject_code
        elif isinstance(current_item, AnalysisItem):
            return current_item.subject_code
        return None
    
    def get_selected_analysis_index(self):
        """Получение индекса выбранного анализа"""
        current_item = self.tree.currentItem()
        if isinstance(current_item, AnalysisItem):
            return current_item.analysis_index
        return -1
    
    def get_analysis_checkbox_state(self, subject_code, analysis_index):
        """Получение состояния чекбокса анализа"""
        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item:
                return analysis_item.get_checkbox_state()
        return False
    
    def get_all_subjects(self):
        """Получение списка всех предметов"""
        return list(self.subject_items.keys())
    
    def get_subject_analyses(self, subject_code):
        """Получение списка анализов предмета"""
        if subject_code in self.subject_items:
            return self.subject_items[subject_code].get_all_analyses()
        return []
    
    def get_selected_analyses(self):
        """Получение списка выбранных анализов (с включенными чекбоксами)"""
        selected = []
        for subject_code, subject_item in self.subject_items.items():
            selected_analyses = subject_item.get_selected_analyses()
            for analysis_index in selected_analyses:
                selected.append((subject_code, analysis_index))
        return selected
    
    def update_analysis_display(self, subject_code, analysis_index, success, file_name, message=None):
        """Обновление отображения анализа после загрузки"""
        logger.debug(f"Обновление отображения анализа: {subject_code}, {analysis_index}, успех: {success}")
        
        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            subject_item.update_analysis_display(analysis_index, success, file_name, message)
            
            # Обновляем стиль кнопки
            analysis_item = subject_item.get_analysis(analysis_index)
            if analysis_item and analysis_item.graph_button:
                if success:
                    self.set_button_style(analysis_item.graph_button, 'success')
                else:
                    if message and 'вручную' in message:
                        self.set_button_style(analysis_item.graph_button, 'warning')
                    else:
                        self.set_button_style(analysis_item.graph_button, 'error')
    
    def update_analysis_params(self, subject_code, analysis_index, params):
        """Обновление параметров анализа"""
        if subject_code in self.subject_items:
            subject_item = self.subject_items[subject_code]
            subject_item.update_analysis_params(analysis_index, params)
    
    def show_context_menu(self, position):
        """Показать контекстное меню"""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        if isinstance(item, SubjectItem):  # Предмет
            add_analysis_action = QAction("Добавить анализ", self.tree)
            delete_subject_action = QAction("Удалить предмет", self.tree)
            
            menu.addAction(add_analysis_action)
            menu.addAction(delete_subject_action)
            
            add_analysis_action.triggered.connect(self.load_files_to_current_subject)
            delete_subject_action.triggered.connect(self.delete_current_subject)
        
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