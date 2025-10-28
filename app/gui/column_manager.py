# gui/column_manager.py

from PyQt6.QtCore import QObject
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ColumnManager(QObject):
    """Менеджер для управления столбцами таблицы"""

    def __init__(self):
        super().__init__()
        self._columns = []
        self._column_indices = {}
        self._setup_base_columns()

    def _setup_base_columns(self):
        """Настройка базовых столбцов"""
        self._columns = [
            {'key': 'checkbox', 'title': 'Выбор', 'type': 'widget', 'index': 0},
            {'key': 'subject_code', 'title': 'Код предмета', 'type': 'text', 'index': 1},
            {'key': 'file_name', 'title': 'Файл анализа', 'type': 'text', 'index': 2},
            {'key': 'graph_button', 'title': 'Графики и \nподстройка значений', 'type': 'widget', 'index': 3},
            {'key': 'start_freq', 'title': 'Начальная частота (Гц)', 'type': 'float', 'index': 4},
            {'key': 'end_freq', 'title': 'Конечная частота (Гц)', 'type': 'float', 'index': 5},
            {'key': 'record_time', 'title': 'Время записи (сек)', 'type': 'float', 'index': 6}
        ]
        self._rebuild_indices()

    def _rebuild_indices(self):
        """Перестроить индексы столбцов"""
        self._column_indices = {col['key']: col['index'] for col in self._columns}

    def get_column_index(self, column_key: str) -> int:
        """Получить индекс столбца по ключу"""
        return self._column_indices.get(column_key, -1)

    def get_dynamic_columns_start_index(self) -> int:
        """Получить начальный индекс для динамических столбцов"""
        return len([col for col in self._columns if col['type'] != 'dynamic'])

    def add_dynamic_column(self, column_config: Dict[str, Any]) -> int:
        """Добавить динамический столбец"""
        start_index = self.get_dynamic_columns_start_index()
        column_config['index'] = start_index
        column_config['type'] = 'dynamic'
        self._columns.append(column_config)
        self._rebuild_indices()
        return start_index

    def remove_dynamic_column(self, column_key: str) -> bool:
        """Удалить динамический столбец"""
        self._columns = [col for col in self._columns if not (col.get('type') == 'dynamic' and col['key'] == column_key)]
        self._rebuild_indices()
        return True

    def set_dynamic_columns(self, dynamic_columns: List[Dict[str, Any]]):
        """Установить динамические столбцы"""
        # Удаляем старые динамические столбцы
        self._columns = [col for col in self._columns if col.get('type') != 'dynamic']

        # Добавляем новые
        start_index = self.get_dynamic_columns_start_index()
        for i, column_config in enumerate(dynamic_columns):
            column_config['index'] = start_index + i
            column_config['type'] = 'dynamic'
            self._columns.append(column_config)

        self._rebuild_indices()

    def get_column_count(self) -> int:
        """Получить общее количество столбцов"""
        return len(self._columns)

    def get_headers(self) -> List[str]:
        """Получить заголовки столбцов"""
        return [col['title'] for col in self._columns]

    def get_dynamic_columns(self) -> List[Dict[str, Any]]:
        """Получить динамические столбцы"""
        return [col for col in self._columns if col.get('type') == 'dynamic']

    def get_column_config(self, column_key: str) -> Dict[str, Any]:
        """Получить конфигурацию столбца"""
        for col in self._columns:
            if col['key'] == column_key:
                return col.copy()
        return {}

    def is_dynamic_column(self, column_index: int) -> bool:
        """Проверить, является ли столбец динамическим"""
        if 0 <= column_index < len(self._columns):
            return self._columns[column_index].get('type') == 'dynamic'
        return False

    def get_column_by_index(self, column_index: int) -> Dict[str, Any]:
        """Получить конфигурацию столбца по индексу"""
        if 0 <= column_index < len(self._columns):
            return self._columns[column_index].copy()
        return {}