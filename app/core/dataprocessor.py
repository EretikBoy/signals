# core/dataprocessor.py
from typing import Dict, Any, Callable
from functools import wraps

import numpy as np
import logging
logger = logging.getLogger(__name__)

class Processor:
    '''
    Description
    ----------
    Класс отвечает за удобное хранение данных и их обработку, позволяет модулям программы передавая процессор
    прокидывать необходимые данные через один объект без необходимости копий, процессор также отвечает за реализацию
    универсальных алгоритмов обработки любого объекта класса Channel, для последующего удобного вызова необходимого для
    расчётов параметров основной идеей является возможность определить стандартный набор функций, но также возможность
    реализации собственных алгоритмов без необходимости самостоятельно искать часто используемые параметры, такие как
    максимум, среднее, индекс, минимальное и многое другое по мере необходимости

    Parameters
    ----------
    data : Dict
    В словаре для обработки должны быть ключи
    'channels' и 'params'
    в channels должен быть словарь
    ['channels'][channel_name] = channel
    в params
    не нулевые
    'start_freq':
    'end_freq':
    'record_time':
    'cut_second':
    'gain':
    'fixedlevel'

    Returns
    -------
    object class Processor
    To Do enum
    processor.methods
    processor.functions

    See Also
    --------
    class Channel.

    Examples
    --------
    data = Processor({channels:{}, params:{}})
    data.raw_min_amp[channel_name]
    data.channel_parameters.get(self.params['selected_channel'], {})
    print(f"Максимальная амплитуда: {params['max_amplitude']:.4f} В\n")

    '''
    def __init__(self, data: Dict[str, Any]):
        logger.debug("=== ИНИЦИАЛИЗАЦИЯ PROCESSOR ===")
        logger.debug(f"Доступные каналы: {list(data['channels'].keys())}")
        logger.debug(f"Параметры: {data['params']}")
        
        self.channels = data['channels']
        self.params = data['params']
        self._cache = {}
        self._precomputed = {}  # Для данных, не зависящих от параметров
        self._rounding_precision = 12
        self._update_derived_params()
        
        logger.debug("=== ЗАВЕРШЕНИЕ ИНИЦИАЛИЗАЦИИ PROCESSOR ===")

    def _round_data(self, data: Any) -> Any:
        """
        Рекурсивно округляет числа в структурах данных до заданной точности.

        Поддерживает:
        - отдельные числа (int, float)
        - numpy массивы
        - списки и кортежи
        - словари
        - pandas Series и DataFrame (если есть зависимость от pandas)
        """
        if isinstance(data, (int, np.integer)):
            return data
        elif isinstance(data, (float, np.floating)):
            return round(data, self._rounding_precision)
        elif isinstance(data, np.ndarray):
            return np.round(data, self._rounding_precision)
        elif isinstance(data, (list, tuple)):
            return type(data)(self._round_data(item) for item in data)
        elif isinstance(data, dict):
            return {key: self._round_data(value) for key, value in data.items()}
        # Если установлен pandas
        elif hasattr(data, '__class__') and data.__class__.__name__ in ['Series', 'DataFrame']:
            return data.round(self._rounding_precision)
        else:
            return data

    def rounded_property(func: Callable):
        """
        Декоратор для автоматического округления возвращаемых значений свойств.
        """
        @wraps(func)
        def wrapper(self):
            result = func(self)
            return self._round_data(result)
        return wrapper

    def update_params(self, new_params: Dict[str, Any]):
        logger.debug("=== ОБНОВЛЕНИЕ ПАРАМЕТРОВ ===")
        logger.debug(f"Старые параметры: {self.params}")
        logger.debug(f"Новые параметры: {new_params}")
        self.params.update(new_params)
        self._update_derived_params()

        # Сбрасываем только тот кэш, который зависит от параметров
        keys_to_clear = ['cropped_data', 'freq_response', 'channel_parameters']
        for key in keys_to_clear:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Очищен кэш: {key}")

    def set_signal_start_channel(self, channel_name: str):
        logger.debug(f"=== УСТАНОВКА КАНАЛА СИГНАЛА: {channel_name} ===")
        if channel_name in self.channels:
            self.params['signal_start_channel'] = channel_name
            if 'cropped_data' in self._cache:
                del self._cache['cropped_data']
            if 'freq_response' in self._cache:
                del self._cache['freq_response']
            if 'channel_parameters' in self._cache:
                del self._cache['channel_parameters']
            logger.debug("Кэш очищен после смены канала сигнала")
        else:
            logger.error(f"Попытка установить несуществующий канал: {channel_name}")

    def _update_derived_params(self):
        logger.debug("=== ВЫЧИСЛЕНИЕ ПРОИЗВОДНЫХ ПАРАМЕТРОВ ===")
        self.start_freq = self.params.get('start_freq', 1)
        self.end_freq = self.params.get('end_freq', 1)
        self.record_time = self.params.get('record_time', 1)
        self.cut_second = self.params.get('cut_second', 0)
        self.fixedlevel = self.params.get('fixedlevel', 0.6)
        self.gain = self.params.get('gain', 7)
        self.bandwidth = self.end_freq - self.start_freq

        # АВТОМАТИЧЕСКАЯ КОРРЕКЦИЯ signal_start_channel
        current_signal_channel = self.params.get('signal_start_channel')
        available_channels = list(self.channels.keys())
    
        if current_signal_channel not in available_channels:
            if available_channels:
                self.params['signal_start_channel'] = available_channels[0]
                logger.warning(f"Автоматически исправлен signal_start_channel: {current_signal_channel} -> {available_channels[0]}")
            else:
                logger.error("Нет доступных каналов для signal_start_channel")
        
        # logger.debug(f"start_freq: {self.start_freq}")
        # logger.debug(f"end_freq: {self.end_freq}")
        # logger.debug(f"record_time: {self.record_time}")
        # logger.debug(f"cut_second: {self.cut_second}")
        # logger.debug(f"fixedlevel: {self.fixedlevel}")
        # logger.debug(f"gain: {self.gain}")
        # logger.debug(f"bandwidth: {self.bandwidth}")

    def _precompute_raw_extremums(self):
        logger.debug("=== ПРЕДВЫЧИСЛЕНИЕ ЭКСТРЕМУМОВ ===")
        if 'raw_extremums' in self._precomputed:
            logger.debug("Используем кэшированные экстремумы")
            return self._precomputed['raw_extremums']

        raw_extremums = {}
        for name, channel in self.channels.items():
            logger.debug(f"Обработка канала: {name}")
            amplitude = channel.data['Амплитуда'].values
            max_amp = np.max(amplitude)
            min_amp = np.min(amplitude)
            maxamp_idx = np.argmax(amplitude)
            minamp_idx = np.argmin(amplitude)
            
            logger.debug(f"Канал {name}: max_amp={max_amp}, min_amp={min_amp}, maxamp_idx={maxamp_idx}, minamp_idx={minamp_idx}")

            raw_extremums[name] = {
                'max_amp': max_amp,
                'min_amp': min_amp,
                'maxamp_idx': maxamp_idx,
                'minamp_idx': minamp_idx
            }

        self._precomputed['raw_extremums'] = raw_extremums
        logger.debug("Завершено предвычисление экстремумов")
        return raw_extremums

    def _precompute_smoothed_data(self):
        """
        Заранее подготавливает сглаженные данные для всех каналов.

        Этот метод:
        1. Создает копию исходных данных для каждого канала
        2. Добавляет столбец с абсолютными значениями амплитуд
        3. Применяет скользящее среднее для сглаживания данных
        4. Сохраняет результат в кэш, чтобы не вычислять повторно

        Особенности:
        - Использует обратный порядок данных для корректного сглаживания
        - Работает одинаково при любых параметрах обработки
        - Выполняется один раз при первом обращении

        Пример использования:
        Этот метод автоматически вызывается при работе других методов класса
        когда требуются сглаженные данные.
        """
        if 'smoothed_data' in self._precomputed:
            logger.debug("Используем кэшированные сглаженные данные")
            cached_channels = list(self._precomputed['smoothed_data'].keys())
            logger.debug(f"Кэшированные каналы: {cached_channels}")
            return self._precomputed['smoothed_data']

        smoothed_data = {}
        logger.debug(f"Доступные каналы для сглаживания: {list(self.channels.keys())}")
        
        for name, channel in self.channels.items():
            logger.debug(f"Сглаживание канала: {name}")
            logger.debug(f"Размер данных до сглаживания: {len(channel.data)}")
            
            data_copy = channel.data.copy()
            data_copy['ABS_Amplitude'] = np.abs(data_copy['Амплитуда'])
            data_copy['Smoothed'] = (
                data_copy['ABS_Amplitude'][::-1]
                .rolling(window=15, min_periods=1)
                .mean()[::-1]
            )
            smoothed_data[name] = data_copy
            
            logger.debug(f"Размер данных после сглаживания: {len(smoothed_data[name])}")
            logger.debug(f"Столбцы: {list(smoothed_data[name].columns)}")
            if len(smoothed_data[name]) > 0:
                logger.debug(f"Первые 5 строк Smoothed: {smoothed_data[name]['Smoothed'].head().tolist()}")

        self._precomputed['smoothed_data'] = smoothed_data
        logger.debug("Завершено предвычисление сглаженных данных")
        return smoothed_data

    def _get_signal_start_index(self):
        """
        Определяет начальную точку сигнала для анализа.

        Алгоритм работы:
        1. Находит момент максимальной амплитуды в первом канале
        2. Добавляет смещение (cut_second) для точной настройки начала
        3. Рассчитывает смещение в количестве точек на основе шага времени

        Возвращает:
        Индекс начала сигнала с учетом смещения.

        Пример:
        Если максимальная амплитуда на 0.5 сек, а cut_second = 0.1 сек,
        то начало сигнала будет на 0.6 секунде.
        """
        logger.debug("=== НАЧАЛО _get_signal_start_index ===")

        smoothed_data = self._precompute_smoothed_data()
        if not smoothed_data:
            logger.error("Нет smoothed_data для определения начала сигнала")
            return 0

        signal_channel_name = self.params.get('signal_start_channel')
        logger.debug(f"Канал для определения начала сигнала: {signal_channel_name}")
        
        if signal_channel_name not in smoothed_data:
            logger.error(f"Канал {signal_channel_name} не найден в smoothed_data")
            available_channels = list(smoothed_data.keys())
            logger.debug(f"Доступные каналы: {available_channels}")
            return 0

        signal_channel = smoothed_data[signal_channel_name]
        total_points = len(signal_channel)
        logger.debug(f"Общее количество точек в канале: {total_points}")

        if total_points == 0:
            logger.error("Канал для определения начала сигнала пуст")
            return 0

        # Находим индекс максимального значения
        try:
            max_idx = signal_channel['Амплитуда'].idxmax()
            max_amp = signal_channel['Амплитуда'].max()
            logger.debug(f"Максимальная амплитуда: {max_amp} на индексе {max_idx}")
        except Exception as e:
            logger.error(f"Ошибка поиска максимума: {e}")
            return 0

        # Вычисление time_step
        if len(signal_channel) < 2:
            logger.error("Недостаточно данных для вычисления time_step")
            return 0

        time_step = signal_channel['Время'].iloc[1] - signal_channel['Время'].iloc[0]
        logger.debug(f"Шаг времени: {time_step}")

        offset_points = int(self.cut_second / time_step) if time_step > 0 else 0
        logger.debug(f"Смещение в точках: {offset_points} (cut_second={self.cut_second})")

        # Вычисляем начальный индекс
        signal_start = max(0, min(max_idx + offset_points, total_points - 1))
        logger.debug(f"Итоговый signal_start: {signal_start}")

        return signal_start

    def _get_cropped_indices(self):
        """
        Определяет диапазон индексов для обрезки данных.

        Этот метод:
        1. Находит начало сигнала
        2. Рассчитывает количество точек для обрезки на основе record_time
        3. Возвращает начальный индекс и количество точек

        Важно:
        - Зависит от параметров cut_second и record_time
        - При изменении этих параметров результаты обрезки будут пересчитаны
        """
        logger.debug("=== НАЧАЛО _get_cropped_indices ===")

        smoothed_data = self._precompute_smoothed_data()
        if not smoothed_data:
            logger.error("Нет smoothed_data для вычисления индексов")
            return 0, 0

        signal_channel_name = self.params.get('signal_start_channel')
        logger.debug(f"Канал для обрезки: {signal_channel_name}")
        
        if signal_channel_name not in smoothed_data:
            logger.error(f"Канал {signal_channel_name} не найден в smoothed_data")
            return 0, 0

        signal_channel = smoothed_data[signal_channel_name]
        total_points = len(signal_channel)
        logger.debug(f"Общее количество точек: {total_points}")

        # Вычисление signal_start
        signal_start = self._get_signal_start_index()
        logger.debug(f"Полученный signal_start: {signal_start}")

        # Вычисление time_step
        if len(signal_channel) < 2:
            logger.error("Недостаточно данных для вычисления time_step")
            return 0, 0

        time_step = signal_channel['Время'].iloc[1] - signal_channel['Время'].iloc[0]
        logger.debug(f"Шаг времени: {time_step}")

        # Вычисление points_to_crop
        max_possible_points = total_points - signal_start
        logger.debug(f"Максимально возможных точек для обрезки: {max_possible_points}")

        requested_points = int(self.record_time / time_step) if time_step > 0 else 0
        logger.debug(f"Запрошенное количество точек: {requested_points} (record_time={self.record_time})")

        points_to_crop = min(requested_points, max_possible_points)
        logger.debug(f"Итоговое points_to_crop: {points_to_crop}")

        # Защита от нулевых значений
        if points_to_crop <= 0:
            logger.warning(f"points_to_crop <= 0: {points_to_crop}. Используем максимально возможное: {max_possible_points}")
            points_to_crop = max_possible_points

        logger.debug(f"Финальные индексы: signal_start={signal_start}, points_to_crop={points_to_crop}")
        return signal_start, points_to_crop

    def _get_cropped_data(self):
        """
        Получает обрезанные данные для всех каналов.

        Этот метод:
        1. Определяет диапазон обрезки
        2. Вырезает нужную часть данных для каждого канала
        3. Кэширует результат для повторного использования

        Особенности:
        - Результаты зависят от параметров cut_second и record_time
        - При изменении этих параметров кэш автоматически очищается
        - Данные берутся из предварительно сглаженных значений

        Пример использования:
        Этот метод автоматически вызывается при обращении к свойству cropped_data
        или при расчете частотной характеристики.
        """
        if 'cropped_data' in self._cache:
            logger.debug("Используем кэшированные обрезанные данные")
            cached_channels = list(self._cache['cropped_data'].keys())
            logger.debug(f"Кэшированные каналы: {cached_channels}")
            for name, data in self._cache['cropped_data'].items():
                logger.debug(f"Кэш канала {name}: размер {len(data)}")
            return self._cache['cropped_data']

        smoothed_data = self._precompute_smoothed_data()
        logger.debug(f"Доступные каналы в smoothed_data: {list(smoothed_data.keys())}")
        
        signal_start, points_to_crop = self._get_cropped_indices()
        logger.debug(f"Параметры обрезки: signal_start={signal_start}, points_to_crop={points_to_crop}")

        cropped_data = {}
        for name, data in smoothed_data.items():
            logger.debug(f"Обрезка канала: {name}")
            logger.debug(f"Размер данных до обрезки: {len(data)}")
            
            cropped_channel = data.iloc[signal_start:signal_start + points_to_crop]
            cropped_data[name] = cropped_channel
            
            logger.debug(f"Размер данных после обрезки: {len(cropped_data[name])}")
            logger.debug(f"Индексы обрезанных данных: от {signal_start} до {signal_start + points_to_crop}")

        self._cache['cropped_data'] = cropped_data
        logger.debug("Завершено получение обрезанных данных")
        return cropped_data

    def _get_freq_response_data(self):
        """
        Вычисляет амплитудно-частотную характеристику (АЧХ) для всех каналов.

        Этот метод преобразует временные данные в частотные:
        1. Берет обрезанные данные сигналов
        2. Создает массив частот на основе времени и параметров сканирования
        3. Рассчитывает АЧХ в линейном масштабе и в децибелах
        4. Применяет коэффициент усиления (gain) к амплитудам

        Возвращает словарь с двумя вариантами АЧХ:
        - 'linear': данные в линейном масштабе (амплитуда)
        - 'dB': данные в логарифмическом масштабе (децибелы)

        Пример использования:
        Этот метод автоматически вызывается при обращении к свойствам
        freqresponse_linear или freqresponse_dB.
        """
        if 'freq_response' in self._cache:
            logger.debug("Используем кэшированную частотную характеристику")
            return self._cache['freq_response']

        cropped_data = self._get_cropped_data()
        logger.debug(f"Каналы в cropped_data: {list(cropped_data.keys())}")
        
        if not cropped_data:
            logger.error("Нет данных для вычисления частотной характеристики")
            return {'linear': {}, 'dB': {}}

        first_channel_data = list(cropped_data.values())[0]
        logger.debug(f"Размер первого канала: {len(first_channel_data)}")
        
        timeshifted = first_channel_data['Время'] - first_channel_data['Время'].iloc[0]
        logger.debug(f"Временное смещение: от {timeshifted.min()} до {timeshifted.max()}")

        freqs = self.start_freq + (self.bandwidth / self.record_time) * timeshifted
        logger.debug(f"Частоты: от {freqs.min()} до {freqs.max()}")

        freq_response_linear = {}
        freq_response_dB = {}
        for name, data in cropped_data.items():
            logger.debug(f"Обработка канала {name} для АЧХ")
            logger.debug(f"Размер данных: {len(data)}")
            
            amplitude_linear = data['Smoothed'].values * self.gain
            logger.debug(f"Линейная амплитуда: от {np.min(amplitude_linear)} до {np.max(amplitude_linear)}")
            
            freq_response_linear[name] = {
                'freq': freqs.values,
                'amplitude': amplitude_linear
            }
            
            db_amplitude = 20 * np.log10(data['Smoothed'].values)
            logger.debug(f"Амплитуда в дБ: от {np.min(db_amplitude)} до {np.max(db_amplitude)}")
            
            freq_response_dB[name] = {
                'freq': freqs.values,
                'db_amplitude': db_amplitude
            }

        result = {
            'linear': freq_response_linear,
            'dB': freq_response_dB
        }
        self._cache['freq_response'] = result
        logger.debug("Завершено вычисление частотной характеристики")
        return result

    def _get_channel_parameters(self):
        """
        Вычисляет ключевые параметры каждого канала на основе АЧХ.

        Для каждого канала определяет:
        - Максимальную амплитуду и резонансную частоту
        - Полосу пропускания на уровне -3 дБ (0.707 от максимума)
        - Полосу пропускания на заданном уровне (fixedlevel)
        - Добротность системы (Q-factor)

        Эти параметры важны для анализа характеристик системы:
        - Резонансная частота показывает, на какой частоте система наиболее чувствительна
        - Полоса пропускания показывает диапазон частот, которые система хорошо пропускает
        - Добротность характеризует избирательность системы

        Возвращает словарь с параметрами для каждого канала.
        """
        if 'channel_parameters' in self._cache:
            logger.debug("Используем кэшированные параметры каналов")
            return self._cache['channel_parameters']

        freq_data = self._get_freq_response_data()
        linear_data = freq_data['linear']
        logger.debug(f"Каналы для вычисления параметров: {list(linear_data.keys())}")

        channel_params = {}
        for name, data in linear_data.items():
            logger.debug(f"Вычисление параметров для канала: {name}")
            
            amplitude = data['amplitude']
            freq = data['freq']
            logger.debug(f"Размер данных амплитуды: {len(amplitude)}")
            logger.debug(f"Размер данных частоты: {len(freq)}")

            max_amp = np.max(amplitude)
            max_amp_idx = np.argmax(amplitude)
            resonance_freq = freq[max_amp_idx]
            logger.debug(f"Максимальная амплитуда: {max_amp}, резонансная частота: {resonance_freq}")

            # Вычисление полосы пропускания и других параметров
            half_power_level = max_amp * 0.707
            above_half_power = amplitude >= half_power_level
            logger.debug(f"Уровень половинной мощности: {half_power_level}")
            logger.debug(f"Точек выше уровня половинной мощности: {np.sum(above_half_power)}")

            if np.any(above_half_power):
                low_idx = np.where(above_half_power)[0][0]
                high_idx = np.where(above_half_power)[0][-1]
                bandwidth_707 = freq[high_idx] - freq[low_idx]
                bandwidth_707_range = (freq[low_idx], freq[high_idx])
                logger.debug(f"Полоса пропускания -3дБ: {bandwidth_707}, диапазон: {bandwidth_707_range}")
            else:
                bandwidth_707 = 0
                bandwidth_707_range = (0, 0)
                logger.warning("Нет точек выше уровня половинной мощности")

            above_fixed_level = amplitude >= self.fixedlevel
            logger.debug(f"Точек выше фиксированного уровня: {np.sum(above_fixed_level)}")
            
            if np.any(above_fixed_level):
                low_idx_fixed = np.where(above_fixed_level)[0][0]
                high_idx_fixed = np.where(above_fixed_level)[0][-1]
                bandwidth_fixed = freq[high_idx_fixed] - freq[low_idx_fixed]
                bandwidth_fixed_range = (freq[low_idx_fixed], freq[high_idx_fixed])
                logger.debug(f"Полоса пропускания фиксированная: {bandwidth_fixed}, диапазон: {bandwidth_fixed_range}")
            else:
                bandwidth_fixed = 0
                bandwidth_fixed_range = (0, 0)
                logger.warning("Нет точек выше фиксированного уровня")

            q_factor = resonance_freq / bandwidth_707 if bandwidth_707 > 0 else 0
            logger.debug(f"Добротность: {q_factor}")

            channel_params[name] = {
                'max_amplitude': max_amp,
                'resonance_frequency': resonance_freq,
                'bandwidth_707': bandwidth_707,
                'bandwidth_707_range': bandwidth_707_range,
                'bandwidth_fixed': bandwidth_fixed,
                'bandwidth_fixed_range': bandwidth_fixed_range,
                'q_factor': q_factor
            }

        self._cache['channel_parameters'] = channel_params
        logger.debug("Завершено вычисление параметров каналов")
        return channel_params

    def calculate_frequency_forecast(self, channel_name: str, sufficient_criterion: float = 1.0):
        """
        Рассчитывает прогноз полосы частот для проверки.

        Формула:
        нижняя_граница = резонансная_частота - ((критерий_достаточности * время_записи) / 2)
        верхняя_граница = резонансная_частота + ((критерий_достаточности * время_записи) / 2)

        Parameters:
        -----------
        channel_name : str
            Имя канала для расчета
        sufficient_criterion : float
            Критерий достаточности в Гц/с (по умолчанию 1.0)

        Returns:
        --------
        tuple: (нижняя_граница, верхняя_граница) или None если данные недоступны
        """
        if channel_name not in self.channel_parameters:
            return None

        params = self.channel_parameters[channel_name]
        resonance_freq = params['resonance_frequency']
        record_time = self.record_time

        lower_bound = resonance_freq - ((sufficient_criterion * record_time) / 2)
        upper_bound = resonance_freq + ((sufficient_criterion * record_time) / 2)

        return (lower_bound, upper_bound)

    @property
    @rounded_property
    def raw_data(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAW_DATA ===")
        if 'raw_data' not in self._precomputed:
            logger.debug("Вычисление raw_data")
            self._precomputed['raw_data'] = {
                name: channel.data.copy()
                for name, channel in self.channels.items()
            }
        logger.debug(f"Каналы в raw_data: {list(self._precomputed['raw_data'].keys())}")
        return self._precomputed['raw_data']

    @property
    @rounded_property
    def smoothed_data(self):
        logger.debug("=== ПОЛУЧЕНИЕ SMOOTHED_DATA ===")
        result = self._precompute_smoothed_data()
        logger.debug(f"Размер smoothed_data: {len(result)} каналов")
        return result

    @property
    @rounded_property
    def cropped_data(self):
        logger.debug("=== ПОЛУЧЕНИЕ CROPPED_DATA ===")
        result = self._get_cropped_data()
        logger.debug(f"Размер cropped_data: {len(result)} каналов")
        for name, data in result.items():
            logger.debug(f"Канал {name}: {len(data)} точек")
        return result

    @property
    @rounded_property
    def rawplot(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAWPLOT ===")
        raw_data = self.raw_data
        result = {
            name: {
                'time': data['Время'].values,
                'amplitude': data['Амплитуда'].values
            } for name, data in raw_data.items()
        }
        logger.debug(f"Размер rawplot: {len(result)} каналов")
        return result

    @property
    @rounded_property
    def smoothedplot(self):
        logger.debug("=== ПОЛУЧЕНИЕ SMOOTHEDPLOT ===")
        cropped_data = self._get_cropped_data()
        result = {}
        
        for name, data in cropped_data.items():
            logger.debug(f"Обработка канала {name} для smoothedplot")
            logger.debug(f"Размер данных: {len(data)}")
            
            if len(data) == 0:
                logger.error(f"Пустые данные для канала {name} в smoothedplot")
                continue
                
            try:
                time_values = data['Время'].values
                result[name] = {
                    'time': time_values - time_values[0],
                    'smoothed_amplitude': data['Smoothed'].values
                }
                logger.debug(f"Успешно обработан канал {name}")
            except Exception as e:
                logger.error(f"Ошибка обработки канала {name}: {e}")
                continue
                
        logger.debug(f"Итоговый размер smoothedplot: {len(result)} каналов")
        return result

    @property
    @rounded_property
    def freqresponse_linear(self):
        logger.debug("=== ПОЛУЧЕНИЕ FREQRESPONSE_LINEAR ===")
        freq_data = self._get_freq_response_data()
        result = freq_data['linear']
        logger.debug(f"Размер freqresponse_linear: {len(result)} каналов")
        return result

    @property
    def freqresponse_dB(self):
        logger.debug("=== ПОЛУЧЕНИЕ FREQRESPONSE_DB ===")
        freq_data = self._get_freq_response_data()
        result = freq_data['dB']
        logger.debug(f"Размер freqresponse_dB: {len(result)} каналов")
        return result

    @property
    @rounded_property
    def channel_parameters(self):
        logger.debug("=== ПОЛУЧЕНИЕ CHANNEL_PARAMETERS ===")
        result = self._get_channel_parameters()
        logger.debug(f"Размер channel_parameters: {len(result)} каналов")
        return result

    @property
    def analysis_start_time(self):
        logger.debug("=== ПОЛУЧЕНИЕ ANALYSIS_START_TIME ===")
        cropped_data = self._get_cropped_data()
        if not cropped_data:
            logger.error("Нет данных для определения analysis_start_time")
            return 0
            
        first_channel = list(cropped_data.values())[0]
        result = first_channel['Время'].iloc[0]
        logger.debug(f"Analysis start time: {result}")
        return result

    @property
    @rounded_property
    def raw_max_amp(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAW_MAX_AMP ===")
        extremums = self._precompute_raw_extremums()
        result = {name: data['max_amp'] for name, data in extremums.items()}
        logger.debug(f"Raw max amp: {result}")
        return result

    @property
    @rounded_property
    def raw_min_amp(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAW_MIN_AMP ===")
        extremums = self._precompute_raw_extremums()
        result = {name: data['min_amp'] for name, data in extremums.items()}
        logger.debug(f"Raw min amp: {result}")
        return result

    @property
    def raw_maxamp_idx(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAW_MAXAMP_IDX ===")
        extremums = self._precompute_raw_extremums()
        result = {name: data['maxamp_idx'] for name, data in extremums.items()}
        logger.debug(f"Raw maxamp idx: {result}")
        return result

    @property
    def raw_minamp_idx(self):
        logger.debug("=== ПОЛУЧЕНИЕ RAW_MINAMP_IDX ===")
        extremums = self._precompute_raw_extremums()
        result = {name: data['minamp_idx'] for name, data in extremums.items()}
        logger.debug(f"Raw minamp idx: {result}")
        return result