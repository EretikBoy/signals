#core/data_manager.py
import os
import shutil
import pickle
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from core.parser import DataParser
from core.dataprocessor import Processor
from utils.constants import DEFAULT_PARAMS, MEASUREMENTS_DIR, TABLES_DIR, ANALYSIS_EXTENSION


class DataManager:
    """Управление данными с поддержкой иерархической структуры предметов и анализов"""
    
    def __init__(self):
        self.data_parser = DataParser()
        self.subjects_data = {}  # subject_code -> {analyses: {analysis_index: data}, ...}
        self.open_dialogs = {}  # (subject_code, analysis_index) -> dialog
    
    def initialize_subject(self, subject_code):
        """Инициализация предмета"""
        if subject_code not in self.subjects_data:
            self.subjects_data[subject_code] = {
                'analyses': {},
                'metadata': {}
            }
    
    def parse_file(self, subject_code, file_path, analysis_index):
        """Парсинг файла и добавление в данные предмета"""
        try:
            self.initialize_subject(subject_code)
            
            file_format = file_path.split('.')[-1]
            success = self.data_parser.parsefile(file_path, file_format)
            
            if not success:
                return False, f'Не удалось загрузить файл: {file_path}'
            
            file_name = os.path.basename(file_path)
            file_name_without_ext = file_name.split('.')[0]
            
            # Пытаемся извлечь параметры из имени файла
            params = self.extract_params_from_filename(file_name_without_ext)
            
            # Сохраняем данные анализа
            self.subjects_data[subject_code]['analyses'][analysis_index] = {
                'path': file_path,
                'original_file_name': file_name,
                'file_name': file_name,  # Временно, будет переименован при сохранении
                'channels': {},
                'params': params
            }
            
            # Получаем каналы
            for channel_name in self.data_parser.get_channel_names():
                channel = self.data_parser.get_channel(channel_name)
                if channel and not channel.data.empty:
                    self.subjects_data[subject_code]['analyses'][analysis_index]['channels'][channel_name] = channel
            
            # Создаём процессор для файла
            self.subjects_data[subject_code]['analyses'][analysis_index]['processor'] = Processor(
                self.subjects_data[subject_code]['analyses'][analysis_index]
            )
            
            return True, file_name
            
        except Exception as e:
            return False, f'Ошибка при загрузке файла: {str(e)}'
    
    def extract_params_from_filename(self, filename):
        """Извлечение параметров из имени файла"""
        # Стандартный формат: КОДПРЕДМЕТА_СТАРТОВАЯЧАСТОТА_ШИРИНАПОЛОСЫ_ВРЕМЯЗАПИСИ
        parts = filename.split('_')
        
        if len(parts) >= 4:
            try:
                start_freq = int(parts[1])
                bandwidth = int(parts[2])
                record_time = int(parts[3])
                end_freq = start_freq + bandwidth
                
                return {
                    'start_freq': start_freq,
                    'end_freq': end_freq,
                    'record_time': record_time,
                    'cut_second': DEFAULT_PARAMS['cut_second'],
                    'fixedlevel': DEFAULT_PARAMS['fixedlevel'],
                    'gain': DEFAULT_PARAMS['gain']
                }
            except ValueError:
                pass
        
        # Если не удалось извлечь, используем значения по умолчанию
        return {
            'start_freq': DEFAULT_PARAMS['start_freq'],
            'end_freq': DEFAULT_PARAMS['end_freq'],
            'record_time': DEFAULT_PARAMS['record_time'],
            'cut_second': DEFAULT_PARAMS['cut_second'],
            'fixedlevel': DEFAULT_PARAMS['fixedlevel'],
            'gain': DEFAULT_PARAMS['gain']
        }
    
    def generate_standard_filename(self, subject_code, params):
        """Генерация стандартизированного имени файла"""
        start_freq = int(params['start_freq'])
        bandwidth = int(params['end_freq'] - params['start_freq'])
        record_time = int(params['record_time'])
        
        return f"{subject_code}_{start_freq}_{bandwidth}_{record_time}.csv"
    
    def save_measurement_data(self, channels_data, params, subject_code=None):
        """Сохранение данных измерения в файл"""
        try:
            if subject_code is None:
                subject_code = f"M{datetime.now().strftime('%d%m%Y_%H%M%S')}"
            
            self.initialize_subject(subject_code)
            
            # Генерируем стандартизированное имя файла
            file_name = self.generate_standard_filename(subject_code, params)
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
            
            # Создаем новый индекс анализа
            analysis_index = self.get_next_analysis_index(subject_code)
            
            # Подготавливаем данные для таблицы
            analysis_data = {
                'path': file_path,
                'original_file_name': file_name,
                'file_name': file_name,
                'channels': channels_data,
                'params': params
            }
            
            analysis_data['processor'] = Processor(analysis_data)
            
            # Сохраняем данные
            self.subjects_data[subject_code]['analyses'][analysis_index] = analysis_data
            
            return True, subject_code, analysis_index, file_name
            
        except Exception as e:
            return False, None, None, f'Ошибка при сохранении данных: {str(e)}'
    
    def get_next_analysis_index(self, subject_code):
        """Получение следующего индекса анализа для предмета"""
        if subject_code not in self.subjects_data:
            return 0
        
        analyses = self.subjects_data[subject_code]['analyses']
        if not analyses:
            return 0
        
        return max(analyses.keys()) + 1
    
    def save_analysis(self, tree_manager, save_selected_only=False, parent=None):
        """Сохранение анализа"""
        if not self.subjects_data:
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
                'subjects': {},
                'files': {}
            }
            
            # Определяем, какие анализы сохранять
            subjects_to_save = {}
            if save_selected_only:
                # Сохраняем только выбранные анализы
                selected_analyses = tree_manager.get_selected_analyses()
                for subject_code, analysis_index in selected_analyses:
                    if subject_code not in subjects_to_save:
                        subjects_to_save[subject_code] = []
                    subjects_to_save[subject_code].append(analysis_index)
            else:
                # Сохраняем все анализы
                for subject_code, subject_data in self.subjects_data.items():
                    subjects_to_save[subject_code] = list(subject_data['analyses'].keys())
            
            # Копируем файлы и сохраняем информацию
            for subject_code, analysis_indices in subjects_to_save.items():
                if subject_code not in self.subjects_data:
                    continue
                
                subject_data = self.subjects_data[subject_code]
                analysis_data['subjects'][subject_code] = {
                    'analyses': {},
                    'metadata': subject_data.get('metadata', {})
                }
                
                for analysis_index in analysis_indices:
                    if analysis_index not in subject_data['analyses']:
                        continue
                    
                    analysis = subject_data['analyses'][analysis_index]
                    
                    try:
                        # Переименовываем файл в стандартный формат
                        standard_filename = self.generate_standard_filename(subject_code, analysis['params'])
                        src_file = analysis['path']
                        dst_file = os.path.join(folder_name, standard_filename)
                        shutil.copy2(src_file, dst_file)
                        
                        # Обновляем имя файла в данных
                        analysis['file_name'] = standard_filename
                        
                    except Exception as e:
                        QMessageBox.warning(parent, 'Предупреждение', 
                                           f'Ошибка копирования файла {analysis["file_name"]}: {str(e)}')
                    
                    # Сохраняем информацию об анализе
                    analysis_info = {
                        'file_name': standard_filename,
                        'params': analysis['params'],
                        'processor': analysis['processor'],
                        'channels_data': {}
                    }
                    
                    # Сохраняем данные каналов
                    for channel_name, channel in analysis['channels'].items():
                        analysis_info['channels_data'][channel_name] = {
                            'data': channel.data.to_dict(),
                            'name': channel.name
                        }
                    
                    analysis_data['subjects'][subject_code]['analyses'][analysis_index] = analysis_info
                    analysis_data['files'][(subject_code, analysis_index)] = standard_filename
            
            with open(file_name, 'wb') as f:
                pickle.dump(analysis_data, f)
            
            QMessageBox.information(parent, 'Успех', 'Анализ успешно сохранен')
            return True
            
        except Exception as e:
            QMessageBox.critical(parent, 'Ошибка', f'Ошибка при сохранении анализа: {str(e)}')
            return False
    
    def load_analysis(self, parent):
        """Загрузка анализа из файла"""
        file_name, _ = QFileDialog.getOpenFileName(
            parent, 
            'Загрузить анализ', 
            TABLES_DIR, 
            f'Analysis Files ({ANALYSIS_EXTENSION})'
        )
        
        if not file_name:
            return None
        
        base_name = os.path.splitext(os.path.basename(file_name))[0]
        folder_name = os.path.join(os.path.dirname(file_name), base_name)
        
        if not os.path.exists(file_name) or not os.path.exists(folder_name):
            QMessageBox.critical(parent, 'Ошибка', 'Файл анализа или папка с данными не найдены')
            return None
        
        try:
            with open(file_name, 'rb') as f:
                analysis_data = pickle.load(f)
            
            # Очищаем текущие данные
            self.subjects_data = {}
            for dialog in self.open_dialogs.values():
                dialog.close()
            self.open_dialogs = {}
            
            loaded_data = []
            
            for subject_code, subject_info in analysis_data['subjects'].items():
                self.initialize_subject(subject_code)
                
                for analysis_index, analysis_info in subject_info['analyses'].items():
                    file_path = os.path.join(folder_name, analysis_info['file_name'])
                    file_exists = os.path.exists(file_path)
                    
                    # Восстанавливаем данные каналов
                    channels = {}
                    for channel_name, channel_data in analysis_info['channels_data'].items():
                        channel = type('Channel', (), {})()
                        channel.name = channel_data['name']
                        channel.data = pd.DataFrame(channel_data['data'])
                        channels[channel_name] = channel
                    
                    # Сохраняем данные анализа
                    self.subjects_data[subject_code]['analyses'][analysis_index] = {
                        'path': file_path if file_exists else None,
                        'original_file_name': analysis_info['file_name'],
                        'file_name': analysis_info['file_name'],
                        'params': analysis_info['params'],
                        'processor': analysis_info['processor'],
                        'channels': channels
                    }
                    
                    loaded_data.append({
                        'subject_code': subject_code,
                        'analysis_index': analysis_index,
                        'analysis_info': analysis_info,
                        'file_path': file_path,
                        'file_exists': file_exists
                    })
            
            QMessageBox.information(parent, 'Успех', 'Анализ успешно загружен')
            return loaded_data
            
        except Exception as e:
            QMessageBox.critical(parent, 'Ошибка', f'Ошибка при загрузке анализа: {str(e)}')
            return None
    
    def get_analysis_data(self, subject_code, analysis_index):
        """Получение данных анализа"""
        if (subject_code in self.subjects_data and 
            analysis_index in self.subjects_data[subject_code]['analyses']):
            return self.subjects_data[subject_code]['analyses'][analysis_index]
        return None
    
    def update_analysis_params(self, subject_code, analysis_index, params):
        """Обновление параметров анализа"""
        analysis_data = self.get_analysis_data(subject_code, analysis_index)
        if analysis_data:
            analysis_data['params'] = params
    
    def move_analysis_data(self, old_subject, new_subject, analysis_index):
        """Перемещение данных анализа между предметами"""
        analysis_data = self.get_analysis_data(old_subject, analysis_index)
        if not analysis_data:
            return False
        
        # Удаляем из старого предмета
        if old_subject in self.subjects_data and analysis_index in self.subjects_data[old_subject]['analyses']:
            del self.subjects_data[old_subject]['analyses'][analysis_index]
        
        # Добавляем в новый предмет
        self.initialize_subject(new_subject)
        self.subjects_data[new_subject]['analyses'][analysis_index] = analysis_data
        
        return True
    
    def register_dialog(self, subject_code, analysis_index, dialog):
        """Регистрация открытого диалога"""
        self.open_dialogs[(subject_code, analysis_index)] = dialog
    
    def unregister_dialog(self, subject_code, analysis_index):
        """Удаление диалога из регистрации"""
        key = (subject_code, analysis_index)
        if key in self.open_dialogs:
            del self.open_dialogs[key]