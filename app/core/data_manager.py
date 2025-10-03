#core/data_manager.py
import os
import shutil
import pickle
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox

from core.parser import DataParser
from core.dataprocessor import Processor
from utils.constants import *


class DataManager:
    """Управление данными файлов и анализом"""
    
    def __init__(self):
        self.data_parser = DataParser()
        self.files_data = {}
        self.open_dialogs = {}
    
    def parse_file(self, file_path, row_position):
        """Парсинг файла и добавление в данные"""
        try:
            file_format = file_path.split('.')[-1]
            success = self.data_parser.parsefile(file_path, file_format)
            
            if not success:
                return False, f'Не удалось загрузить файл: {file_path}'
            
            file_name = os.path.basename(file_path)
            file_name_without_ext = file_name.split('.')[0]
            name_parts = file_name_without_ext.split('_')
            
            # Извлекаем параметры из имени файла
            start_freq = DEFAULT_PARAMS['start_freq']
            bandwidth = 1
            record_time = DEFAULT_PARAMS['record_time']
            identifier = f'AN{row_position}'
            
            if len(name_parts) >= 4:
                try:
                    identifier = str(name_parts[0])
                    start_freq = int(name_parts[1])
                    bandwidth = int(name_parts[2])
                    record_time = int(name_parts[3])
                except ValueError:
                    return True, f'Установите параметры вручную: {file_name}'
            
            end_freq = start_freq + bandwidth
            
            # Сохраняем данные файла
            self.files_data[row_position] = {
                'path': file_path,
                'file_name': file_name,
                'channels': {},
                'params': {
                    'start_freq': start_freq,
                    'end_freq': end_freq,
                    'record_time': record_time,
                    'cut_second': DEFAULT_PARAMS['cut_second'],
                    'fixedlevel': DEFAULT_PARAMS['fixedlevel'],
                    'gain': DEFAULT_PARAMS['gain']
                }
            }
            
            # Получаем каналы
            for channel_name in self.data_parser.get_channel_names():
                channel = self.data_parser.get_channel(channel_name)
                if channel and not channel.data.empty:
                    self.files_data[row_position]['channels'][channel_name] = channel
            
            # Создаём процессор для файла
            self.files_data[row_position]['processor'] = Processor(self.files_data[row_position])
            
            return True, file_name
            
        except Exception as e:
            return False, f'Ошибка при загрузке файла: {str(e)}'
    
    def save_measurement_data(self, channels_data, params):
        """Сохранение данных измерения в файл и возврат информации для таблицы"""
        try:
            timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
            file_name = f"measurement_{timestamp}.csv"
            file_path = os.path.join(MEASUREMENTS_DIR, file_name)
            
            os.makedirs(MEASUREMENTS_DIR, exist_ok=True)
            
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
            all_data.to_csv(file_path, index=False)
            
            # Подготавливаем данные для таблицы
            table_data = {
                'path': file_path,
                'file_name': file_name,
                'channels': channels_data,
                'params': {
                    'start_freq': params.get('start_freq', DEFAULT_PARAMS['start_freq']),
                    'end_freq': params.get('end_freq', DEFAULT_PARAMS['end_freq']),
                    'record_time': params.get('record_time', DEFAULT_PARAMS['record_time']),
                    'cut_second': DEFAULT_PARAMS['cut_second'],
                    'fixedlevel': DEFAULT_PARAMS['fixedlevel'],
                    'gain': DEFAULT_PARAMS['gain']
                }
            }
            
            table_data['processor'] = Processor(table_data)
            
            return True, table_data, file_name
            
        except Exception as e:
            return False, None, f'Ошибка при сохранении данных: {str(e)}'
    
    def save_analysis(self, table_widget, parent):
        """Сохранение анализа в папку tables"""
        if not self.files_data:
            QMessageBox.warning(parent, 'Предупреждение', 'Нет данных для сохранения')
            return False
        
        os.makedirs(TABLES_DIR, exist_ok=True)
        
        file_name, _ = QFileDialog.getSaveFileName(
            parent, 
            'Сохранить анализ', 
            f'{TABLES_DIR}/analysis.analysis', 
            f'Analysis Files ({ANALYSIS_EXTENSION})'
        )
        
        if not file_name:
            return False
        
        base_name = os.path.splitext(os.path.basename(file_name))[0]
        folder_name = os.path.join(os.path.dirname(file_name), base_name)
        os.makedirs(folder_name, exist_ok=True)
        
        try:
            analysis_data = {
                'rows': [],
                'files': {}
            }
            
            for row, data in self.files_data.items():
                try:
                    src_file = data['path']
                    dst_file = os.path.join(folder_name, data['file_name'])
                    shutil.copy2(src_file, dst_file)
                except Exception:
                    QMessageBox.critical(parent, 'Ошибка', 'Строки таблицы не имеют привязки, данные сохраняться без исходных файлов')
                
                row_data = {
                    'subject_code': table_widget.item(row, 0).text(),
                    'file_name': data['file_name'],
                    'params': data['params'],
                    'processor': data['processor'],
                    'channels_data': {}
                }
                
                for channel_name, channel in data['channels'].items():
                    row_data['channels_data'][channel_name] = {
                        'data': channel.data.to_dict(),
                        'name': channel.name
                    }
                
                analysis_data['rows'].append((row, row_data))
                analysis_data['files'][row] = data['file_name']
            
            with open(file_name, 'wb') as f:
                pickle.dump(analysis_data, f)
            
            QMessageBox.information(parent, 'Успех', 'Анализ успешно сохранен')
            return True
            
        except Exception as e:
            QMessageBox.critical(parent, 'Ошибка', f'Ошибка при сохранении анализа: {str(e)}')
            return False
    
    def load_analysis(self, table_widget, parent):
        """Загрузка анализа из файла"""
        file_name, _ = QFileDialog.getOpenFileName(
            parent, 
            'Загрузить анализ', 
            TABLES_DIR, 
            f'Analysis Files ({ANALYSIS_EXTENSION})'
        )
        
        if not file_name:
            return False
        
        base_name = os.path.splitext(os.path.basename(file_name))[0]
        folder_name = os.path.join(os.path.dirname(file_name), base_name)
        
        if not os.path.exists(file_name) or not os.path.exists(folder_name):
            QMessageBox.critical(parent, 'Ошибка', 'Файл анализа или папка с данными не найдены')
            return False
        
        try:
            with open(file_name, 'rb') as f:
                analysis_data = pickle.load(f)
            
            # Очищаем текущие данные
            table_widget.setRowCount(0)
            self.files_data = {}
            for dialog in self.open_dialogs.values():
                dialog.close()
            self.open_dialogs = {}
            
            for row, row_data in analysis_data['rows']:
                table_widget.insertRow(row)
                
                file_path = os.path.join(folder_name, row_data['file_name'])
                file_exists = os.path.exists(file_path)
                
                # Восстанавливаем данные в таблицу (это должен сделать TableManager)
                # Возвращаем данные для восстановления UI
                yield row, row_data, file_path, file_exists
                
                # Восстанавливаем внутренние данные
                channels = {}
                for channel_name, channel_data in row_data['channels_data'].items():
                    channel = type('Channel', (), {})()
                    channel.name = channel_data['name']
                    channel.data = pd.DataFrame(channel_data['data'])
                    channels[channel_name] = channel
                
                self.files_data[row] = {
                    'path': file_path if file_exists else None,
                    'file_name': row_data['file_name'],
                    'params': row_data['params'],
                    'processor': row_data['processor'],
                    'channels': channels
                }
            
            QMessageBox.information(parent, 'Успех', 'Анализ успешно загружен')
            return True
            
        except Exception as e:
            QMessageBox.critical(parent, 'Ошибка', f'Ошибка при загрузке анализа: {str(e)}')
            return False
    
    def get_file_data(self, row):
        """Получение данных файла по строке"""
        return self.files_data.get(row)
    
    def set_file_data(self, row, data):
        """Установка данных файла для строки"""
        self.files_data[row] = data
    
    def delete_file_data(self, row):
        """Удаление данных файла по строке"""
        if row in self.files_data:
            del self.files_data[row]
    
    def update_file_params(self, row, params):
        """Обновление параметров файла"""
        if row in self.files_data:
            self.files_data[row]['params'] = params
    
    def register_dialog(self, row, dialog):
        """Регистрация открытого диалога"""
        self.open_dialogs[row] = dialog
    
    def unregister_dialog(self, row):
        """Удаление диалога из регистрации"""
        if row in self.open_dialogs:
            del self.open_dialogs[row]