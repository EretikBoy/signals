# core/data_manager.py

import os
import shutil
import pickle
import psutil
from datetime import datetime

import pandas as pd
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from core.parser import DataParser, Channel
from core.dataprocessor import Processor
from utils.constants import DEFAULT_PARAMS, MEASUREMENTS_DIR, TABLES_DIR, ANALYSIS_EXTENSION

import logging
logger = logging.getLogger(__name__)


def get_locked_files(process_name=None):
    """Получить список заблокированных файлов процессом"""
    locked_files = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Если указано имя процесса или это текущий процесс
            if process_name and proc.info['name'] != process_name:
                continue
            if not process_name and proc.info['pid'] != current_pid:
                continue
                
            files = proc.open_files()
            for file in files:
                locked_files.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'file': file.path
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return locked_files

def log_open_files(context=""):
    """Логировать открытые файлы текущим процессом"""
    logger.debug(f"=== ОТКРЫТЫЕ ФАЙЛЫ [{context}] ===")
    try:
        current_pid = os.getpid()
        process = psutil.Process(current_pid)
        files = process.open_files()
        
        for file in files:
            logger.debug(f"Файл открыт: {file.path} (fd: {file.fd})")
            
        if not files:
            logger.debug("Нет открытых файлов")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке открытых файлов: {e}")


class DataManager:
    """Управление данными с поддержкой иерархической структуры предметов и анализов"""
    
    def __init__(self):
        self.subjects_data = {}  # subject_code -> {analyses: {analysis_index: data}, ...}
        self.open_dialogs = {}  # (subject_code, analysis_index) -> dialog
        self._locked_files_logged = set()

    def _diagnose_file_locking(self, file_path, operation=""):
        """Диагностика блокировки файла"""
        logger.debug(f"=== ДИАГНОСТИКА БЛОКИРОВКИ ФАЙЛА [{operation}] ===")
        logger.debug(f"Целевой файл: {file_path}")
        
        # Проверяем открытые файлы текущим процессом
        log_open_files(f"before {operation}")
        
        # Проверяем, заблокирован ли конкретный файл
        try:
            with open(file_path, 'a') as test_file:
                logger.debug(f"Файл {file_path} доступен для записи")
        except PermissionError as e:
            logger.error(f"Файл {file_path} заблокирован: {e}")
            
            # Находим, кто блокирует файл
            all_locked = get_locked_files()
            for locked in all_locked:
                if file_path in locked['file']:
                    logger.error(f"Файл заблокирован процессом: PID={locked['pid']}, Name={locked['name']}, File={locked['file']}")

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
            
            file_format = file_path.split('.')[-1].lower()
            
            # СОЗДАЕМ НОВЫЙ ПАРСЕР ДЛЯ КАЖДОГО ФАЙЛА - это исправляет баг с общими каналами
            data_parser = DataParser()
            success = data_parser.parsefile(file_path, file_format)
            
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
                'file_name': file_name,
                'channels': {},
                'params': params
            }
            
            for channel_name in data_parser.get_channel_names():
                channel = data_parser.get_channel(channel_name)
                if channel and not channel.data.empty:
                    self.subjects_data[subject_code]['analyses'][analysis_index]['channels'][channel_name] = channel
            
            # Создаём процессор для файла
            self.subjects_data[subject_code]['analyses'][analysis_index]['processor'] = Processor(
                self.subjects_data[subject_code]['analyses'][analysis_index]
            )
            
            logger.debug(f"Файл {file_name} загружен. Каналы: {list(data_parser.get_channel_names())}")
            
            return True, file_name
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла {file_path}: {str(e)}")
            return False, f'Ошибка при загрузке файла: {str(e)}'
    
    def extract_params_from_filename(self, filename):
        """Извлечение параметров из имени файла"""
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
        
        return {
            'start_freq': DEFAULT_PARAMS['start_freq'],
            'end_freq': DEFAULT_PARAMS['end_freq'],
            'record_time': DEFAULT_PARAMS['record_time'],
            'cut_second': DEFAULT_PARAMS['cut_second'],
            'fixedlevel': DEFAULT_PARAMS['fixedlevel'],
            'gain': DEFAULT_PARAMS['gain']
        }
    
    def generate_standard_filename(self, subject_code, params, tree_manager=None):
        """Генерация стандартизированного имени файла"""
        try:
            start_freq = int(params.get('start_freq', DEFAULT_PARAMS['start_freq']))
            end_freq = int(params.get('end_freq', DEFAULT_PARAMS['end_freq']))
            bandwidth = end_freq - start_freq
            record_time = int(params.get('record_time', DEFAULT_PARAMS['record_time']))
            if tree_manager:
                return f"{tree_manager.get_subject_name(subject_code)}_{start_freq}_{bandwidth}_{record_time}.csv"
            else:
                return f"{subject_code}_{start_freq}_{bandwidth}_{record_time}.csv"
        except (ValueError, TypeError):
            return f"{tree_manager.get_subject_name(subject_code)}_{DEFAULT_PARAMS['start_freq']}_{DEFAULT_PARAMS['end_freq'] - DEFAULT_PARAMS['start_freq']}_{DEFAULT_PARAMS['record_time']}.csv"
    
    def save_measurement_data(self, channels_data, params, subject_code=None):
        try:
            if subject_code is None:
                subject_code = f"M{datetime.now().strftime('%d%m%Y_%H%M%S')}"
            
            self.initialize_subject(subject_code)
            
            # Генерируем имя файла
            file_name = self.generate_standard_filename(subject_code, params)
            file_path = os.path.join(MEASUREMENTS_DIR, file_name)
            os.makedirs(MEASUREMENTS_DIR, exist_ok=True)
            
            # Получаем следующий индекс анализа
            analysis_index = self.get_next_analysis_index(subject_code)
            
            analysis_data = {
                'path': file_path,
                'original_file_name': file_name,
                'file_name': file_name,
                'channels': {},
                'params': params
            }
            
            all_data = pd.DataFrame()
            valid_channels = {}
            
            for channel_name, channel_obj in channels_data.items():
                try:
                    # Извлекаем данные из объекта канала прибора
                    if hasattr(channel_obj, 'data') and channel_obj.data is not None:
                        df = channel_obj.data
                        
                        # Проверяем, что данные не пустые
                        if not df.empty and len(df.columns) >= 2:
                            # СОЗДАЕМ КАНАЛ В ФОРМАТЕ parser.Channel
                            channel = Channel(channel_name)
                            
                            # Извлекаем время и амплитуду (первые две колонки)
                            time_data = df.iloc[:, 0]
                            amplitude_data = df.iloc[:, 1]
                            
                            # Устанавливаем данные в канал
                            channel.set_data(time_data, amplitude_data)
                            
                            # Сохраняем канал
                            analysis_data['channels'][channel_name] = channel
                            valid_channels[channel_name] = channel
                            
                            # Добавляем в общий DataFrame для CSV
                            channel_df = pd.DataFrame({
                                f'{channel_name}_time': time_data,
                                f'{channel_name}_amplitude': amplitude_data
                            })
                            
                            if all_data.empty:
                                all_data = channel_df
                            else:
                                all_data = pd.concat([all_data, channel_df], axis=1)
                            
                            logger.debug(f"Канал {channel_name} обработан: {len(time_data)} точек")
                        else:
                            logger.warning(f"Канал {channel_name}: пустые данные или недостаточно колонок")
                    else:
                        logger.warning(f"Канал {channel_name}: нет данных или атрибута 'data'")
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки канала {channel_name}: {str(e)}")
                    continue
            
            if not valid_channels:
                return False, None, None, "Нет валидных данных каналов для сохранения"
            
            # СОХРАНЯЕМ В CSV
            try:
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    all_data.to_csv(f, index=False)
                logger.info(f"Данные сохранены в {file_path}, форма: {all_data.shape}")
            except Exception as e:
                logger.error(f"Ошибка сохранения CSV: {str(e)}")
                return False, None, None, f"Ошибка сохранения файла: {str(e)}"
            
            # СОЗДАЕМ ПРОЦЕССОР С ПРАВИЛЬНЫМИ ДАННЫМИ
            try:
                processor = Processor(analysis_data)
                analysis_data['processor'] = processor
                logger.debug("Процессор создан успешно")
            except Exception as e:
                logger.error(f"Ошибка создания процессора: {str(e)}")
                return False, None, None, f"Ошибка создания процессора: {str(e)}"
            
            # СОХРАНЯЕМ В СТРУКТУРЕ ДАННЫХ
            self.subjects_data[subject_code]['analyses'][analysis_index] = analysis_data
            
            logger.info(f"Измерение сохранено: {subject_code}, {analysis_index}, каналы: {list(valid_channels.keys())}")
            
            return True, subject_code, analysis_index, file_name
            
        except Exception as e:
            logger.error(f"Критическая ошибка при сохранении измерения: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None, None, f'Критическая ошибка: {str(e)}'
    
    def get_next_analysis_index(self, subject_code):
        """Получение следующего индекса анализа для предмета"""
        if subject_code not in self.subjects_data:
            return 0
        
        analyses = self.subjects_data[subject_code]['analyses']
        if not analyses:
            return 0
        
        return max(analyses.keys()) + 1
    
    def save_analysis(self, tree_manager, save_selected_only=False, parent=None, auto_save=False):
        """Сохранение анализа
        
        Args:
            tree_manager: менеджер дерева
            save_selected_only: сохранять только выбранные анализы
            parent: родительское окно для диалогов
            auto_save: режим автосохранения (без диалогов)
        """
        if not self.subjects_data:
            if not auto_save:  # Не показываем предупреждение при автосохранении
                QMessageBox.warning(parent, 'Предупреждение', 'Нет данных для сохранения')
            return False
        
        if auto_save:
            # Режим автосохранения
            backup_dir = os.path.join(os.path.dirname(__file__), '..', 'emergency_backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Используем фиксированное имя для автосохранения
            file_name = os.path.join(backup_dir, 'autosave.analysis')
            folder_name = os.path.join(backup_dir, 'autosave')
        else:
            # Обычный режим сохранения
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
                'files': {},
                'timestamp': datetime.now().isoformat(),
                'auto_save': auto_save
            }
            
            # Определяем, какие анализы сохранять
            subjects_to_save = {}
            if save_selected_only:
                selected_analyses = tree_manager.get_selected_analyses()
                for subject_code, analysis_index in selected_analyses:
                    if subject_code not in subjects_to_save:
                        subjects_to_save[subject_code] = []
                    subjects_to_save[subject_code].append(analysis_index)
            else:
                for subject_code, subject_data in self.subjects_data.items():
                    subjects_to_save[subject_code] = list(subject_data['analyses'].keys())
            
            # Копируем файлы и сохраняем информацию
            for subject_code, analysis_indices in subjects_to_save.items():
                if subject_code not in self.subjects_data:
                    continue
                
                subject_data = self.subjects_data[subject_code]
                analysis_data['subjects'][subject_code] = {
                    'analyses': {},
                    'metadata': subject_data.get('metadata', {}),
                    'subject_name': tree_manager.get_subject_name(subject_code)
                }
                
                for analysis_index in analysis_indices:
                    if analysis_index not in subject_data['analyses']:
                        continue
                    
                    analysis = subject_data['analyses'][analysis_index]
                    
                    try:
                        standard_filename = self.generate_standard_filename(subject_code, analysis['params'], tree_manager)
                        src_file = analysis['path']
                        dst_file = os.path.join(folder_name, standard_filename)
                        
                        if src_file not in self._locked_files_logged:
                            self._diagnose_file_locking(src_file, f"copy for {subject_code}/{analysis_index}")
                            self._locked_files_logged.add(src_file)
                    
                        # Пробуем скопировать с диагностикой
                        if not self._safe_copy_with_diagnosis(src_file, dst_file, subject_code, analysis_index):
                            logger.warning(f"Не удалось скопировать {src_file}")
                        
                        analysis['file_name'] = standard_filename
                        
                    except Exception as e:
                        logger.error(f"Критическая ошибка при копировании {analysis['file_name']}: {str(e)}")
                    
                    # ВАЖНО: НЕ сохраняем processor в файл анализа
                    analysis_info = {
                        'file_name': standard_filename,
                        'original_file_name': analysis['original_file_name'],
                        'params': analysis['params'],
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
            
            if not auto_save:  # Сообщаем только при ручном сохранении
                QMessageBox.information(parent, 'Успех', 'Анализ успешно сохранен')
            else:
                logger.info(f"Автосохранение выполнено: {file_name}")
            
            return True
            
        except Exception as e:
            if not auto_save:  # Показываем ошибки только при ручном сохранении
                QMessageBox.critical(parent, 'Ошибка', f'Ошибка при сохранении анализа: {str(e)}')
            else:
                logger.error(f"Ошибка при автосохранении: {str(e)}")
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
                    
                    # СОЗДАЕМ НОВЫЙ ИНДЕКС для текущей сессии
                    new_analysis_index = self.get_next_analysis_index(subject_code)
                    
                    # Сохраняем данные анализа с НОВЫМ индексом
                    self.subjects_data[subject_code]['analyses'][new_analysis_index] = {
                        'path': file_path if file_exists else None,
                        'original_file_name': analysis_info.get('original_file_name', analysis_info['file_name']),
                        'file_name': analysis_info['file_name'],
                        'params': analysis_info['params'],
                        'processor': Processor({
                            'channels': channels,
                            'params': analysis_info['params']
                        }),
                        'channels': channels
                    }
                    
                    loaded_data.append({
                        'subject_code': subject_code,
                        'subject_name': subject_info['subject_name'],
                        'analysis_index': new_analysis_index,
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
            
            analysis_data = self.subjects_data[subject_code]['analyses'][analysis_index]
            
            # ЛОГИРУЕМ ДАННЫЕ ПРИ ЗАПРОСЕ
            logger.debug(f"=== ДАННЫЕ АНАЛИЗА ПРИ ЗАПРОСЕ: {subject_code}, {analysis_index} ===")
            for channel_name, channel in analysis_data['channels'].items():
                if hasattr(channel, 'data'):
                    logger.debug(f"Канал {channel_name}: shape={channel.data.shape}, empty={channel.data.empty}")
                else:
                    logger.warning(f"Канал {channel_name}: нет атрибута data")
            
            return analysis_data
        return None
    
    def update_analysis_params(self, subject_code, analysis_index, params):
        """Обновление параметров анализа"""
        analysis_data = self.get_analysis_data(subject_code, analysis_index)
        if analysis_data:
            analysis_data['params'] = params
    
    def move_analysis_data(self, old_subject, new_subject, analysis_index):
        """Перемещение данных анализа между предметами"""
        logger.debug(f"Перемещение данных анализа: {old_subject} -> {new_subject}, {analysis_index}")
        
        analysis_data = self.get_analysis_data(old_subject, analysis_index)
        if not analysis_data:
            logger.warning(f"Данные анализа не найдены: {old_subject}, {analysis_index}")
            return False
        
        # Удаляем из старого предмета
        if old_subject in self.subjects_data and analysis_index in self.subjects_data[old_subject]['analyses']:
            del self.subjects_data[old_subject]['analyses'][analysis_index]
            logger.debug(f"Удалено из старого предмета: {old_subject}")
        
        # Добавляем в новый предмет
        self.initialize_subject(new_subject)
        
        # Создаем копию данных анализа
        new_analysis_data = analysis_data.copy()
        
        self.subjects_data[new_subject]['analyses'][analysis_index] = new_analysis_data
        logger.debug(f"Добавлено в новый предмет: {new_subject}")
        
        return True
    
    def register_dialog(self, subject_code, analysis_index, dialog):
        """Регистрация открытого диалога"""
        self.open_dialogs[(subject_code, analysis_index)] = dialog
    
    def unregister_dialog(self, subject_code, analysis_index):
        """Удаление диалога из регистрации"""
        key = (subject_code, analysis_index)
        if key in self.open_dialogs:
            del self.open_dialogs[key]


    def _safe_copy_with_diagnosis(self, src, dst, subject_code, analysis_index):
        """Безопасное копирование с расширенной диагностикой"""
        import time
        
        for attempt in range(3):
            try:
                # Используем низкоуровневое копирование с контролем
                with open(src, 'rb') as source_file:
                    # Логируем дескриптор файла
                    logger.debug(f"Открыт исходный файл: {src}, fd: {source_file.fileno()}")
                    
                    with open(dst, 'wb') as dest_file:
                        logger.debug(f"Открыт целевой файл: {dst}, fd: {dest_file.fileno()}")
                        shutil.copyfileobj(source_file, dest_file)
                
                logger.debug(f"Успешно скопирован: {src} -> {dst}")
                return True
                
            except PermissionError as e:
                logger.error(f"Попытка {attempt + 1}: Файл заблокирован - {e}")
                
                # Детальная диагностика при ошибке
                self._detailed_file_diagnosis(src, f"copy_attempt_{attempt + 1}")
                
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"Неожиданная ошибка при копировании: {e}")
                return False
    
    def _detailed_file_diagnosis(self, file_path, context):
        """Детальная диагностика файла"""
        logger.error(f"=== ДЕТАЛЬНАЯ ДИАГНОСТИКА ФАЙЛА [{context}] ===")
        logger.error(f"Файл: {file_path}")
        logger.error(f"Существует: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            try:
                file_stat = os.stat(file_path)
                logger.error(f"Размер: {file_stat.st_size} байт")
                logger.error(f"Время изменения: {file_stat.st_mtime}")
            except Exception as e:
                logger.error(f"Не удалось получить stat файла: {e}")
        
        # Проверяем все процессы, блокирующие файл
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    files = proc.open_files()
                    for file in files:
                        if file_path in file.path:
                            logger.error(f"Заблокирован процессом: PID={proc.info['pid']}, Name={proc.info['name']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Ошибка при проверке процессов: {e}")