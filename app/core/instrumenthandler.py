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

class OscilloscopePollingThread(QThread):
    """Поток для периодического опроса осциллографа"""

    update_signal = pyqtSignal(str)
    data_ready = pyqtSignal(dict)  # channels_data с временной меткой
    error_signal = pyqtSignal(str)
    polling_status = pyqtSignal(bool)  # Статус опроса (True - запущен, False - остановлен)

    def __init__(self, oscilloscope_resource, oscilloscope_type, polling_interval=1.0):
        super().__init__()
        self.oscilloscope_resource = oscilloscope_resource
        self.oscilloscope_type = oscilloscope_type
        self.polling_interval = polling_interval  # Интервал в секундах
        self._is_running = False
        self._stop_requested = False
        self.provider = None

    def run(self):
        """Основной цикл опроса"""
        try:
            self._is_running = True
            self.polling_status.emit(True)
            self.update_signal.emit(f"Запущен периодический опрос с интервалом {self.polling_interval} сек")

            # Создаем провайдер для осциллографа
            if self.oscilloscope_type == "Tektronix":
                from modules.tektronixprovider import TektronixProvider
                self.provider = TektronixProvider(self.oscilloscope_resource)
            else:
                self.error_signal.emit(f"Неподдерживаемый тип осциллографа: {self.oscilloscope_type}")
                return

            # Подключаемся к осциллографу
            if not self.provider.connect():
                self.error_signal.emit("Не удалось подключиться к осциллографу")
                return

            # Настраиваем осциллограф для однократного захвата
            self._setup_oscilloscope_for_single()

            # Основной цикл опроса
            while not self._stop_requested:
                try:
                    # Эмулируем нажатие кнопки Single
                    single_success = self._emulate_single_button()

                    if single_success:
                        # Получаем данные
                        channels_data = self._get_oscilloscope_data()
                        if channels_data:
                            # Добавляем временную метку
                            channels_data['timestamp'] = datetime.now()
                            channels_data['polling_interval'] = self.polling_interval

                            self.data_ready.emit(channels_data)
                            self.update_signal.emit(f"Получены данные: {datetime.now().strftime('%H:%M:%S')}")
                        else:
                            self.update_signal.emit("Не удалось получить данные с осциллографа")
                    else:
                        self.update_signal.emit("Ошибка эмуляции кнопки Single")

                except Exception as e:
                    self.error_signal.emit(f"Ошибка в цикле опроса: {str(e)}")

                # Ждем указанный интервал
                for i in range(int(self.polling_interval * 10)):
                    if self._stop_requested:
                        break
                    time.sleep(0.1)

        except Exception as e:
            self.error_signal.emit(f"Ошибка в потоке опроса: {str(e)}")
        finally:
            self._cleanup()

    def _setup_oscilloscope_for_single(self):
        """Настройка осциллографа для режима однократного захвата"""
        try:
            # Устанавливаем режим однократного захвата
            self.provider.set_stop_after_mode("SEQuence")
            self.provider.set_acquisition_mode("SAMple")

            # Настраиваем триггер для синхронизации по уровню
            self._setup_trigger()

            self.update_signal.emit("Осциллограф настроен для однократного захвата")
            return True

        except Exception as e:
            self.error_signal.emit(f"Ошибка настройки осциллографа: {str(e)}")
            return False

    def _setup_trigger(self):
        """Настройка триггера для синхронизации по уровню"""
        try:
            # Используем команды триггера для настройки синхронизации по уровню
            # Устанавливаем источник триггера (канал 1)
            self.provider.scope.commands.trigger.a.source.write("CH1")

            # Устанавливаем тип триггера - фронт
            self.provider.scope.commands.trigger.a.type.write("EDGE")

            # Устанавливаем уровень триггера (50% от амплитуды)
            self.provider.scope.commands.trigger.a.level.write("50%")

            # Устанавливаем режим триггера - нормальный
            self.provider.scope.commands.trigger.a.mode.write("NORMal")

            self.update_signal.emit("Триггер настроен для синхронизации по уровню")

        except Exception as e:
            self.update_signal.emit(f"Предупреждение: не удалось настроить триггер: {str(e)}")

    def _emulate_single_button(self):
        """Эмуляция нажатия кнопки Single"""
        try:
            # Останавливаем текущий захват
            self.provider.stop_acquisition()

            # Устанавливаем режим однократного захвата
            self.provider.set_stop_after_mode("SEQuence")

            # Запускаем захват
            self.provider.start_acquisition()

            # Ждем завершения захвата с таймаутом
            timeout = 10.0  # секунд
            start_time = time.time()

            while time.time() - start_time < timeout:
                state = self.provider.get_acquisition_state()
                if state == "0":  # 0 означает остановлен (захват завершен)
                    return True
                time.sleep(0.1)

            self.update_signal.emit("Таймаут ожидания захвата")
            return False

        except Exception as e:
            self.error_signal.emit(f"Ошибка эмуляции кнопки Single: {str(e)}")
            return False

    def _get_oscilloscope_data(self):
        """Получение данных с осциллографа"""
        try:
            # Получаем данные со всех активных каналов
            channels_data = self.provider.get_all_channels_data()
            return channels_data

        except Exception as e:
            self.error_signal.emit(f"Ошибка получения данных: {str(e)}")
            return None

    def stop(self):
        """Остановка опроса"""
        self._stop_requested = True
        self.update_signal.emit("Остановка периодического опроса...")

    def _cleanup(self):
        """Очистка ресурсов"""
        self._is_running = False
        self.polling_status.emit(False)

        if self.provider:
            try:
                self.provider.disconnect()
            except:
                pass

        self.update_signal.emit("Периодический опрос остановлен")

    def is_running(self):
        """Проверка, выполняется ли опрос"""
        return self._is_running and not self._stop_requested

    def set_polling_interval(self, interval):
        """Установка нового интервала опроса"""
        self.polling_interval = max(0.1, interval)  # Минимум 100 мс
        self.update_signal.emit(f"Интервал опроса изменен на {self.polling_interval} сек")


class OscilloscopeSingleShotThread(QThread):
    """Поток для одиночного измерения с осциллографа"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, oscilloscope_resource, oscilloscope_type):
        super().__init__()
        self.oscilloscope_resource = oscilloscope_resource
        self.oscilloscope_type = oscilloscope_type

    def run(self):
        """Основной метод потока - одиночное измерение с осциллографа"""
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

            # Настраиваем одиночное измерение
            try:
                self.update_signal.emit("Настройка одиночного измерения...")
                
                # Для Tektronix используем команды одиночного измерения
                if self.oscilloscope_type == 'tektronix':
                    # Устанавливаем режим одиночного измерения
                    oscilloscope.scope.commands.acquire.stopafter.write("SEQUENCE")
                    # Запускаем измерение
                    oscilloscope.scope.commands.acquire.state.write("1")
                    
                    # Ждем завершения измерения
                    self.update_signal.emit("Ожидание завершения измерения...")
                    time.sleep(2)  # Базовая задержка
                    
                    # Проверяем статус измерения
                    while True:
                        status = oscilloscope.scope.commands.acquire.state.query()
                        if status == "0":  # Измерение завершено
                            break
                        time.sleep(0.1)
                
                self.update_signal.emit("Измерение завершено")

            except Exception as e:
                oscilloscope.disconnect()
                self.error_signal.emit(f"Ошибка настройки измерения: {str(e)}")
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