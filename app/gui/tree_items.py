# gui/tree_items.py

from PyQt6.QtWidgets import QTreeWidgetItem, QPushButton, QCheckBox, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class AnalysisItem(QTreeWidgetItem):
    """Класс элемента анализа с собственными свойствами и методами"""
    
    def __init__(self, subject_code, analysis_index, file_data):
        super().__init__()
        self.subject_code = subject_code
        self.analysis_index = analysis_index
        self.file_data = file_data
        self.checkbox_widget = None
        self.graph_button = None
        
        # Настройка флагов для drag & drop
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        
        # Сохраняем индекс в данных элемента
        self.setData(0, Qt.ItemDataRole.UserRole, analysis_index)
        
        self.setup_display()
    
    def setup_display(self):
        """Настройка отображения анализа"""
        # Чекбокс для выбора
        self.setup_checkbox()
        
        # Информация об анализе
        self.setText(1, "")  # Код предмета наследуется от родителя
        self.setText(2, self.file_data['file_name'])
        
        # Кнопка открытия графиков
        self.setup_graph_button()
        
        # Параметры
        self.setText(4, str(self.file_data['params']['start_freq']))
        self.setText(5, str(self.file_data['params']['end_freq']))
        self.setText(6, str(self.file_data['params']['record_time']))
    
    def setup_checkbox(self):
        """Настройка чекбокса"""
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        checkbox_layout.addWidget(checkbox)
        
        self.checkbox_widget = checkbox_widget
        self.checkbox = checkbox
    
    def setup_graph_button(self):
        """Настройка кнопки графиков"""
        self.graph_button = QPushButton('Открыть графики')
    
    def get_checkbox_state(self):
        """Получение состояния чекбокса"""
        if self.checkbox:
            return self.checkbox.isChecked()
        return False
    
    def set_checkbox_state(self, state):
        """Установка состояния чекбокса"""
        if self.checkbox:
            self.checkbox.setChecked(state)
    
    def update_display(self, success, file_name, message=None):
        """Обновление отображения анализа"""
        if success:
            self.setText(2, file_name)
            if self.graph_button:
                self.graph_button.setText('Открыть графики')
        else:
            if message and 'вручную' in message:
                self.setText(2, f'Установите параметры: {file_name}')
            else:
                self.setText(2, 'Ошибка загрузки')
    
    def update_params(self, params):
        """Обновление параметров анализа"""
        self.setText(4, str(params['start_freq']))
        self.setText(5, str(params['end_freq']))
        self.setText(6, str(params['record_time']))
        self.file_data['params'] = params


class SubjectItem(QTreeWidgetItem):
    """Класс элемента предмета с собственными свойствами и методами"""
    
    def __init__(self, subject_code):
        super().__init__()
        self.subject_code = subject_code
        self.analyses = {}  # analysis_index -> AnalysisItem
        self.next_analysis_index = 0  # Счетчик индексов для этого предмета
        
        # Настройка отображения
        self.setText(1, subject_code)
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDropEnabled)
        self.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
    
    def add_analysis(self, file_data, analysis_index=None):
        """Добавление анализа к предмету"""
        if analysis_index is None:
            analysis_index = self.next_analysis_index
            self.next_analysis_index += 1
        
        logger.debug(f"SubjectItem.add_analysis: предмет {self.subject_code}, индекс {analysis_index}")
        
        analysis_item = AnalysisItem(self.subject_code, analysis_index, file_data)
        self.addChild(analysis_item)
        self.analyses[analysis_index] = analysis_item
        
        # Разворачиваем предмет, чтобы показать анализы
        self.setExpanded(True)
        
        logger.debug(f"SubjectItem.add_analysis: анализ добавлен. Всего анализов: {len(self.analyses)}")
        
        return analysis_item, analysis_index
    
    def remove_analysis(self, analysis_index):
        """Удаление анализа из предмета"""
        logger.debug(f"SubjectItem.remove_analysis: предмет {self.subject_code}, индекс {analysis_index}")
        
        if analysis_index in self.analyses:
            analysis_item = self.analyses.pop(analysis_index)
            self.removeChild(analysis_item)
            logger.debug(f"SubjectItem.remove_analysis: анализ удален. Осталось анализов: {len(self.analyses)}")
            return True
        
        logger.warning(f"SubjectItem.remove_analysis: анализ с индексом {analysis_index} не найден")
        return False
    
    def get_analysis(self, analysis_index):
        """Получение анализа по индексу"""
        return self.analyses.get(analysis_index)
    
    def get_all_analyses(self):
        """Получение всех анализов предмета"""
        return list(self.analyses.keys())
    
    def get_selected_analyses(self):
        """Получение выбранных анализов (с включенными чекбоксами)"""
        selected = []
        for analysis_index, analysis_item in self.analyses.items():
            if analysis_item.get_checkbox_state():
                selected.append(analysis_index)
        return selected
    
    def update_analysis_display(self, analysis_index, success, file_name, message=None):
        """Обновление отображения анализа"""
        analysis_item = self.get_analysis(analysis_index)
        if analysis_item:
            analysis_item.update_display(success, file_name, message)
    
    def update_analysis_params(self, analysis_index, params):
        """Обновление параметров анализа"""
        analysis_item = self.get_analysis(analysis_index)
        if analysis_item:
            analysis_item.update_params(params)
    
    def move_analysis_to(self, analysis_item, new_subject_code):
        """Перемещение анализа в другой предмет"""
        analysis_index = analysis_item.analysis_index
        
        # Обновляем subject_code в анализе
        analysis_item.subject_code = new_subject_code
        
        # Удаляем из текущего предмета
        if analysis_index in self.analyses:
            del self.analyses[analysis_index]
            # Не удаляем дочерний элемент здесь, так как это сделает Qt при drop
        
        return analysis_item