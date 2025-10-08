#core/instrumenthandler.py

from modules.gwinstekprovider import GWInstekProvider
from modules.tektronixprovider import TektronixProvider
from modules.rigolprovider import RigolProvider

import time
import pyvisa
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

class InstrumentDetectorThread(QThread):
    """Поток для асинхронного обнаружения приборов"""
    detection_finished = pyqtSignal(dict)
    detection_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        """Основной метод потока - обнаружение приборов"""
        try:
            instruments = {
                'oscilloscopes': [],
                'generators': []
            }
            
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            for resource in resources:
                try:
                    # Пытаемся идентифицировать прибор
                    instr = rm.open_resource(resource)
                    instr.write('*IDN?')
                    time.sleep(0.1)
                    idn = instr.read()
                    instr.close()
                    
                    # Анализируем ответ на идентификацию
                    if 'tektronix' in idn.lower():
                        # Проверяем, является ли осциллографом
                        if any(model in idn.lower() for model in ['mdo', 'dpo', 'tds']):
                            instruments['oscilloscopes'].append({
                                'resource': resource,
                                'idn': idn,
                                'provider': 'tektronix'
                            })
                        # Проверяем, является ли генератором
                        if any(model in idn.lower() for model in ['afg', 'fg']):
                            instruments['generators'].append({
                                'resource': resource,
                                'idn': idn,
                                'provider': 'tektronix'
                            })
                    
                    elif 'rigol' in idn.lower():
                        instruments['generators'].append({
                            'resource': resource,
                            'idn': idn,
                            'provider': 'rigol'
                        })
                    
                    elif 'gw' in idn.lower():
                        instruments['oscilloscopes'].append({
                            'resource': resource,
                            'idn': idn,
                            'provider': 'gwinstek'
                        })
                    
                except Exception as e:
                    # Пропускаем приборы, которые не отвечают на запрос идентификации
                    continue
            
            self.detection_finished.emit(instruments)
                    
        except Exception as e:
            self.detection_error.emit(f"Ошибка при обнаружении приборов: {str(e)}")

class InstrumentWorker(QThread):
    """Рабочий поток для асинхронной работы с приборами"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, generator_resource, oscilloscope_resource, generator_type, oscilloscope_type, params):
        super().__init__()
        self.generator_resource = generator_resource
        self.oscilloscope_resource = oscilloscope_resource
        self.generator_type = generator_type
        self.oscilloscope_type = oscilloscope_type
        self.params = params
        self.is_running = True
        
    def run(self):
        """Основной метод потока - выполнение измерения"""
        try:
            self.update_signal.emit("Подключение к приборам...")
            
            # Подключаемся к генератору
            try:
                if self.generator_type == 'rigol':
                    generator = RigolProvider(self.generator_resource)
                elif self.generator_type == 'tektronix':
                    generator = TektronixProvider(self.generator_resource)
                else:
                    raise ValueError(f"Неизвестный тип генератора: {self.generator_type}")
                
                generator.connect()
                self.update_signal.emit(f"Подключено к генератору: {generator.model_name}")
            except Exception as e:
                self.error_signal.emit(f"Ошибка подключения к генератору: {str(e)}")
                return
                
            # Подключаемся к осциллографу
            try:
                if self.oscilloscope_type == 'gwinstek':
                    oscilloscope = GWInstekProvider(self.oscilloscope_resource)
                elif self.oscilloscope_type == 'tektronix':
                    oscilloscope = TektronixProvider(self.oscilloscope_resource)
                else:
                    raise ValueError(f"Неизвестный тип осциллографа: {self.oscilloscope_type}")
                
                oscilloscope.connect()
                self.update_signal.emit(f"Подключено к осциллографу: {oscilloscope.model_name}")
            except Exception as e:
                generator.disconnect()
                self.error_signal.emit(f"Ошибка подключения к осциллографа: {str(e)}")
                return
            
            # Настраиваем генератор
            try:
                self.update_signal.emit("Настройка генератора...")
                
                if self.generator_type == 'rigol':
                    generator.configure_sweep(
                        start_freq=self.params['start_freq'],
                        stop_freq=self.params['end_freq'],
                        sweep_time=self.params['record_time'],
                        function="SIN",
                        amplitude=self.params['amplitude'],
                        offset=self.params['offset']
                    )
                elif self.generator_type == 'tektronix':
                    # Реализовать настройку для Tektronix при необходимости
                    generator.configure_sweep(
                        start_freq=self.params['start_freq'],
                        stop_freq=self.params['end_freq'],
                        sweep_time=self.params['record_time'],
                        amplitude=self.params['amplitude'],
                        offset=self.params['offset']
                    )
                
                self.update_signal.emit("Генератор настроен")
            except Exception as e:
                generator.disconnect()
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка настройки генератора: {str(e)}")
                return
            
            # Запускаем генератор
            try:
                self.update_signal.emit("Запуск генератора...")
                time.sleep(0.5)
                generator.set_output(True)
                self.update_signal.emit("Генератор запущен")
            except Exception as e:
                generator.disconnect()
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка запуска генератора: {str(e)}")
                return
            
            # Ждем завершения измерения
            try:
                total_time = self.params['record_time']
                step = 0.1  # шаг обновления прогресса (секунды)
                
                for i in range(int(total_time / step)):
                    if not self.is_running:
                        break
                    
                    progress = min(100, int((i * step) / total_time * 100))
                    self.progress_signal.emit(progress)
                    self.update_signal.emit(f"Измерение... {progress}%")
                    self.msleep(int(step * 1000))  # неблокирующая задержка
                
                if self.is_running:
                    self.progress_signal.emit(100)
                    self.update_signal.emit("Измерение завершено")
            except Exception as e:
                generator.set_output(False)
                generator.disconnect()
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка во время измерения: {str(e)}")
                return
            
            # Собираем данные с осциллографа
            try:
                self.update_signal.emit("Чтение данных с осциллографа...")
                channels_data = {}
                
                for ch in range(1, oscilloscope.chnum + 1):
                    if not self.is_running:
                        break
                    
                    self.update_signal.emit(f"Чтение канала {ch}...")
                    channel = oscilloscope.get_channel_data(ch)
                    if channel:
                        channels_data[f"CH{ch}"] = channel
                        self.update_signal.emit(f"Канал {ch} прочитан")
                
                if self.is_running:
                    self.update_signal.emit("Все данные получены")
            except Exception as e:
                generator.set_output(False)
                generator.disconnect()
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка чтения данных: {str(e)}")
                return
            
            # Выключаем генератор и отключаемся
            try:
                generator.set_output(False)
                generator.disconnect()
                oscilloscope.disconnect()
                self.update_signal.emit("Приборы отключены")
            except Exception as e:
                self.error_signal.emit(f"Ошибка при отключении приборов: {str(e)}")
                return
            
            if self.is_running:
                self.finished_signal.emit(channels_data)
                
        except Exception as e:
            self.error_signal.emit(f"Неожиданная ошибка: {str(e)}")
    
    def stop(self):
        """Остановка измерения"""
        self.is_running = False
        self.update_signal.emit("Остановка измерения...")

class OscilloscopeReaderThread(QThread):
    """Поток для чтения данных с осциллографа без измерения"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, oscilloscope_resource, oscilloscope_type):
        super().__init__()
        self.oscilloscope_resource = oscilloscope_resource
        self.oscilloscope_type = oscilloscope_type
        
    def run(self):
        """Основной метод потока - чтение данных с осциллографа"""
        try:
            self.update_signal.emit("Подключение к осциллографу...")
            
            # Подключаемся к осциллографу
            try:
                if self.oscilloscope_type == 'gwinstek':
                    oscilloscope = GWInstekProvider(self.oscilloscope_resource)
                elif self.oscilloscope_type == 'tektronix':
                    oscilloscope = TektronixProvider(self.oscilloscope_resource)
                else:
                    raise ValueError(f"Неизвестный тип осциллографа: {self.oscilloscope_type}")
                
                oscilloscope.connect()
                self.update_signal.emit(f"Подключено к осциллографу: {oscilloscope.model_name}")
            except Exception as e:
                self.error_signal.emit(f"Ошибка подключения к осциллографу: {str(e)}")
                return
            
            # Собираем данные с осциллографа
            try:
                self.update_signal.emit("Чтение данных с осциллографа...")
                channels_data = {}
                
                for ch in range(1, oscilloscope.chnum + 1):
                    self.update_signal.emit(f"Чтение канала {ch}...")
                    channel = oscilloscope.get_channel_data(ch)
                    if channel:
                        channels_data[f"CH{ch}"] = channel
                        self.update_signal.emit(f"Канал {ch} прочитан")
                
                self.update_signal.emit("Все данные получены")
            except Exception as e:
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка чтения данных: {str(e)}")
                return
            
            # Отключаемся
            try:
                oscilloscope.disconnect()
                self.update_signal.emit("Осциллограф отключен")
            except Exception as e:
                self.error_signal.emit(f"Ошибка при отключении осциллографа: {str(e)}")
                return
            
            self.finished_signal.emit(channels_data)
                
        except Exception as e:
            self.error_signal.emit(f"Неожиданная ошибка: {str(e)}")