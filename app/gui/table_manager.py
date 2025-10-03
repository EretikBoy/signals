#gui/table_manager.py
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QObject

from utils.constants import TABLE_HEADERS, BUTTON_STYLE_NORMAL, BUTTON_STYLE_SUCCESS, BUTTON_STYLE_ERROR, BUTTON_STYLE_WARNING


class TableManager(QObject):
    """Управление таблицей файлов и связанными операциями"""
    
    # Сигналы
    file_loaded = pyqtSignal(int, str)  # row, file_path
    row_added = pyqtSignal(int)  # row
    rows_deleted = pyqtSignal(list)  # list of rows
    graph_requested = pyqtSignal(int)  # row
    analysis_save_requested = pyqtSignal()
    analysis_load_requested = pyqtSignal()
    
    def __init__(self, table_widget):
        super().__init__()
        self.table = table_widget
        self.setup_table()
    
    def setup_table(self):
        """Настройка таблицы"""
        self.table.setColumnCount(len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
    
    def add_table_row(self):
        """Добавление новой строки в таблицу"""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        
        # Поле для кода предмета
        subject_item = QTableWidgetItem('')
        self.table.setItem(row_position, 0, subject_item)
        
        # Кнопка добавления файла
        file_button = QPushButton('Добавить файл')
        file_button.clicked.connect(lambda: self.load_file_for_row(row_position))
        self.set_button_style(file_button, 'normal')
        self.table.setCellWidget(row_position, 1, file_button)
        
        # Кнопка для открытия графика
        graph_button = QPushButton('Открыть графики')
        graph_button.setEnabled(False)
        graph_button.clicked.connect(lambda: self.graph_requested.emit(row_position))
        self.table.setCellWidget(row_position, 2, graph_button)
        
        # Параметры (нули)
        for col in range(3, 7):
            param_item = QTableWidgetItem('0')
            self.table.setItem(row_position, col, param_item)
        
        self.row_added.emit(row_position)
        return row_position
    
    def load_file_for_row(self, row):
        """Загрузка файла для конкретной строки"""
        file_path, _ = QFileDialog.getOpenFileName(
            None, 
            'Выберите файл данных', 
            '', 
            'Excel Files (*.xlsx *.xls *.csv);;All Files (*)'
        )
        
        if file_path:
            self.file_loaded.emit(row, file_path)
    
    def load_multiple_files(self):
        """Загрузка нескольких файлов одновременно"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            None,
            'Выберите файлы данных', 
            '', 
            'Excel Files (*.xlsx *.xls *.csv);;All Files (*)'
        )
        
        for file_path in file_paths:
            row = self.add_table_row()
            self.file_loaded.emit(row, file_path)
    
    def update_row_after_file_load(self, row, success, file_name, message=None):
        """Обновление строки после загрузки файла"""
        file_button = self.table.cellWidget(row, 1)
        graph_button = self.table.cellWidget(row, 2)
        
        if success:
            file_button.setText(file_name)
            self.set_button_style(file_button, 'success')
            graph_button.setEnabled(True)
            graph_button.setText('Открыть графики')
        else:
            if message and 'вручную' in message:
                file_button.setText(f'Установите параметры\nвручную: {file_name}')
                self.set_button_style(file_button, 'warning')
            else:
                file_button.setText('Ошибка загрузки')
                self.set_button_style(file_button, 'error')
                if message:
                    QMessageBox.warning(None, 'Ошибка', message)
    
    def update_row_params(self, row, params):
        """Обновление параметров в строке таблицы"""
        self.table.item(row, 3).setText(str(params['start_freq']))
        self.table.item(row, 4).setText(str(params['end_freq']))
        self.table.item(row, 5).setText(str(params['record_time']))
        self.table.item(row, 6).setText(str(params['cut_second']))
    
    def update_row_subject_code(self, row, subject_code):
        """Обновление кода предмета в строке"""
        self.table.item(row, 0).setText(subject_code)
    
    def delete_selected_rows(self):
        """Удаление выбранных строк"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(None, 'Информация', 'Пожалуйста, выберите строки для удаления')
            return
        
        sorted_rows = sorted(selected_rows, reverse=True)
        for row in sorted_rows:
            self.table.removeRow(row)
        
        self.rows_deleted.emit(sorted_rows)
    
    def get_selected_rows(self):
        """Получение списка выбранных строк"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        return sorted(selected_rows)
    
    def clear_table(self):
        """Очистка таблицы"""
        self.table.setRowCount(0)
    
    def set_button_style(self, button, style_type='normal'):
        """Установка стиля для кнопки"""
        from utils.constants import (
            BUTTON_STYLE_SUCCESS, BUTTON_STYLE_ERROR, 
            BUTTON_STYLE_WARNING, BUTTON_STYLE_NORMAL
        )
        
        if style_type == 'success':
            button.setStyleSheet(BUTTON_STYLE_SUCCESS)
        elif style_type == 'error':
            button.setStyleSheet(BUTTON_STYLE_ERROR)
        elif style_type == 'warning':
            button.setStyleSheet(BUTTON_STYLE_WARNING)
        else:
            button.setStyleSheet(BUTTON_STYLE_NORMAL)
    
    def connect_buttons(self, load_callback, load_multiple_callback, delete_callback,
                       save_callback, load_callback_analysis):
        """Подключение callback-функций к кнопкам управления"""
        # Эти кнопки должны быть созданы в главном окне и переданы сюда
        pass  # Реализация зависит от того, как организованы кнопки управления
    
    def save_analysis(self):
        """Запрос на сохранение анализа"""
        self.analysis_save_requested.emit()
    
    def load_analysis(self):
        """Запрос на загрузку анализа"""
        self.analysis_load_requested.emit()