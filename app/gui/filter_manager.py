# gui/filter_manager.py

from PyQt6.QtCore import QObject
from typing import Dict, Any, List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FilterManager(QObject):
    """Менеджер для управления фильтрами таблицы"""

    def __init__(self):
        super().__init__()
        self._filters = {}

    def set_filter(self, column_key: str, filter_type: str, value1: Any, value2: Any = None):
        """Установить фильтр для столбца"""
        if filter_type == 'Все значения' or not value1:
            self.remove_filter(column_key)
        else:
            self._filters[column_key] = {
                'type': filter_type,
                'value1': value1,
                'value2': value2
            }
        logger.debug(f"Установлен фильтр для {column_key}: {self._filters.get(column_key)}")

    def remove_filter(self, column_key: str):
        """Удалить фильтр для столбца"""
        if column_key in self._filters:
            del self._filters[column_key]

    def clear_filters(self):
        """Очистить все фильтры"""
        self._filters.clear()

    def get_filters(self) -> Dict[str, Any]:
        """Получить все активные фильтры"""
        return self._filters.copy()

    def apply_filters(self, analysis_data: Dict[str, Any], column_manager) -> bool:
        """Применить фильтры к данным анализа"""
        if not self._filters:
            return True  # Нет фильтров - показываем все

        for column_key, filter_info in self._filters.items():
            column_config = column_manager.get_column_config(column_key)
            if not column_config:
                continue

            value = self._get_column_value(analysis_data, column_config)
            if not self._check_filter(value, filter_info, column_config.get('type', 'string')):
                return False

        return True

    def _get_column_value(self, analysis_data: Dict[str, Any], column_config: Dict[str, Any]) -> Any:
        """Получить значение столбца для фильтрации"""
        try:
            column_key = column_config['key']
            source = column_config['source']

            if source == 'params':
                return analysis_data['params'].get(column_key, float('nan'))
            elif source == 'channel_params':
                processor = analysis_data.get('processor')
                if processor and hasattr(processor, 'channel_parameters'):
                    channel_params = processor.channel_parameters
                    if channel_params:
                        selected_channel = analysis_data['params'].get('selected_channel', 'CH2')
                        if selected_channel in channel_params:
                            return channel_params[selected_channel].get(column_key, float('nan'))
                        else:
                            first_channel = next(iter(channel_params.values()))
                            return first_channel.get(column_key, float('nan'))
                return float('nan')
            elif source == 'raw_data':
                processor = analysis_data.get('processor')
                if processor:
                    raw_data = getattr(processor, f'raw_{column_key}', {})
                    if raw_data:
                        selected_channel = analysis_data['params'].get('selected_channel', 'CH2')
                        return raw_data.get(selected_channel, float('nan'))
                return float('nan')
            elif source == 'processor':
                processor = analysis_data.get('processor')
                if processor:
                    return getattr(processor, column_key, float('nan'))
                return float('nan')
            else:
                return float('nan')

        except Exception as e:
            logger.error(f"Ошибка получения значения для фильтрации {column_config['key']}: {str(e)}")
            return float('nan')

    def _check_filter(self, value: Any, filter_info: Dict[str, Any], value_type: str) -> bool:
        """Проверить значение по фильтру"""
        try:
            filter_type = filter_info['type']
            value1 = filter_info['value1']
            value2 = filter_info.get('value2')

            # Конвертируем значения в нужный тип
            if value_type == 'float':
                try:
                    value = float(value) if not np.isnan(value) else value
                    value1 = float(value1)
                    if value2 is not None:
                        value2 = float(value2)
                except (ValueError, TypeError):
                    return False

            if filter_type == 'Равно':
                if value_type == 'float':
                    return not np.isnan(value) and abs(value - value1) < 1e-6
                else:
                    return str(value) == str(value1)

            elif filter_type == 'Больше':
                if value_type == 'float':
                    return not np.isnan(value) and value > value1
                else:
                    return str(value) > str(value1)

            elif filter_type == 'Меньше':
                if value_type == 'float':
                    return not np.isnan(value) and value < value1
                else:
                    return str(value) < str(value1)

            elif filter_type == 'Между':
                if value_type == 'float' and value2 is not None:
                    return not np.isnan(value) and value1 <= value <= value2
                else:
                    return False

            return True

        except Exception as e:
            logger.error(f"Ошибка проверки фильтра: {str(e)}")
            return True