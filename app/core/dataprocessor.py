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
        self.channels = data['channels']
        self.params = data['params']
        self._cache = {}
        self._precomputed = {}  # Для данных, не зависящих от параметров
        self._rounding_precision = 12
        self._update_derived_params()


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
        """Обновление параметров и сброс зависимого кэша"""
        self.params.update(new_params)
        self._update_derived_params()
        
        # Сбрасываем только тот кэш, который зависит от параметров
        keys_to_clear = ['cropped_data', 'freq_response', 'channel_parameters']
        for key in keys_to_clear:
            if key in self._cache:
                del self._cache[key]
    
    def set_signal_start_channel(self, channel_name: str):
        """Установка канала для определения начала сигнала"""
        if channel_name in self.channels:
            self.params['signal_start_channel'] = channel_name
            # Сбрасываем кэш, зависящий от начала сигнала
            if 'cropped_data' in self._cache:
                del self._cache['cropped_data']
            if 'freq_response' in self._cache:
                del self._cache['freq_response']
            if 'channel_parameters' in self._cache:
                del self._cache['channel_parameters']
        
    def _update_derived_params(self):
        """Вычисление производных параметров"""
        self.start_freq = self.params.get('start_freq', 1)
        self.end_freq = self.params.get('end_freq', 1)
        self.record_time = self.params.get('record_time', 1)
        self.cut_second = self.params.get('cut_second', 0)
        self.fixedlevel = self.params.get('fixedlevel', 0.6)
        self.gain = self.params.get('gain', 7)
        self.bandwidth = self.end_freq - self.start_freq

    def _precompute_raw_extremums(self):
        """Предварительное вычисление экстремумов исходных данных"""
        if 'raw_extremums' in self._precomputed:
            return self._precomputed['raw_extremums']
            
        raw_extremums = {}
        for name, channel in self.channels.items():
            amplitude = channel.data['Амплитуда'].values
            max_amp = np.max(amplitude)
            min_amp = np.min(amplitude)
            maxamp_idx = np.argmax(amplitude)
            minamp_idx = np.argmin(amplitude)
            
            raw_extremums[name] = {
                'max_amp': max_amp,
                'min_amp': min_amp,
                'maxamp_idx': maxamp_idx,
                'minamp_idx': minamp_idx
            }
        
        self._precomputed['raw_extremums'] = raw_extremums
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
            return self._precomputed['smoothed_data']
            
        smoothed_data = {}
        for name, channel in self.channels.items():
            data_copy = channel.data.copy()
            data_copy['ABS_Amplitude'] = np.abs(data_copy['Амплитуда'])
            data_copy['Smoothed'] = (
                data_copy['ABS_Amplitude'][::-1]
                .rolling(window=15, min_periods=1)
                .mean()[::-1]
            )
            smoothed_data[name] = data_copy
        
        self._precomputed['smoothed_data'] = smoothed_data
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
        
        # Используем выбранный канал для определения начала сигнала
        if self.params['signal_start_channel'] not in smoothed_data:
            logger.error(f"Канал {self.params['signal_start_channel']} не найден в smoothed_data")
            return 0
            
        signal_channel = smoothed_data[self.params['signal_start_channel']]
        total_points = len(signal_channel)
        
        # Находим индекс максимального значения
        max_idx = signal_channel['Амплитуда'].idxmax()
        max_amp = signal_channel['Амплитуда'].max()
        logger.debug(f"Максимальная амплитуда: {max_amp} на индексе {max_idx}")
        
        # Применяем смещение cut_second с защитой от выхода за границы
        if len(signal_channel) < 2:
            logger.error("Недостаточно данных для вычисления time_step")
            return 0
            
        time_step = signal_channel['Время'].iloc[1] - signal_channel['Время'].iloc[0]
        offset_points = int(self.cut_second / time_step) if time_step > 0 else 0
        
        # ЗАЩИТА: не позволяем signal_start выйти за границы массива
        signal_start = max(0, min(max_idx + offset_points, total_points - 1))
        
        logger.debug(f"cut_second: {self.cut_second}, time_step: {time_step}")
        logger.debug(f"offset_points: {offset_points}, total_points: {total_points}")
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
        
        # Используем выбранный канал для определения начала сигнала
        if self.params['signal_start_channel'] not in smoothed_data:
            logger.error(f"Канал {self.params['signal_start_channel']} не найден в smoothed_data")
            return 0, 0
            
        signal_channel = smoothed_data[self.params['signal_start_channel']]
        total_points = len(signal_channel)
        
        logger.debug(f"Используем канал: {self.params['signal_start_channel']}")
        logger.debug(f"Данные канала shape: {signal_channel.shape}")
        
        # Вычисление signal_start с защитой
        signal_start = self._get_signal_start_index()
        
        # Вычисление time_step
        if len(signal_channel) < 2:
            logger.error("Недостаточно данных для вычисления time_step")
            return 0, 0
            
        time_step = signal_channel['Время'].iloc[1] - signal_channel['Время'].iloc[0]
        
        # ВЫЧИСЛЕНИЕ МАКСИМАЛЬНО ВОЗМОЖНОГО points_to_crop
        max_possible_points = total_points - signal_start
        
        # Если record_time слишком большой, корректируем его
        requested_points = int(self.record_time / time_step) if time_step > 0 else 0
        points_to_crop = min(requested_points, max_possible_points)
        
        # Если осталось слишком мало точек, используем все доступные
        if points_to_crop < 10:  # Минимум 10 точек для анализа
            points_to_crop = max_possible_points
            logger.warning(f"Слишком мало точек для обрезки, используем все доступные: {points_to_crop}")
        
        logger.debug(f"record_time: {self.record_time}, time_step: {time_step}")
        logger.debug(f"requested_points: {requested_points}, max_possible_points: {max_possible_points}")
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
            return self._cache['cropped_data']
            
        smoothed_data = self._precompute_smoothed_data()
        signal_start, points_to_crop = self._get_cropped_indices()
        
        cropped_data = {
            name: data.iloc[signal_start:signal_start + points_to_crop]
            for name, data in smoothed_data.items()
        }
        
        self._cache['cropped_data'] = cropped_data
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
            return self._cache['freq_response']
            
        cropped_data = self._get_cropped_data()
        first_channel_data = list(cropped_data.values())[0]
        # Вычисляем временное смещение
        timeshifted = first_channel_data['Время'] - first_channel_data['Время'].iloc[0]

        # Вычисляем частоты
        freqs = self.start_freq + (self.bandwidth / self.record_time) * timeshifted
        
        freq_response_linear = {}
        freq_response_dB = {}
        for name, data in cropped_data.items():
            amplitude_linear = data['Smoothed'].values * self.gain
            freq_response_linear[name] = {
                'freq': freqs.values,
                'amplitude': amplitude_linear
            }
            freq_response_dB[name] = {
                'freq': freqs.values,
                'db_amplitude': 20 * np.log10(data['Smoothed'].values)
            }
        
        self._cache['freq_response'] = {
            'linear': freq_response_linear,
            'dB': freq_response_dB
        }
        return self._cache['freq_response']

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
            return self._cache['channel_parameters']
            
        freq_data = self._get_freq_response_data()
        linear_data = freq_data['linear']
        channel_params = {}
        
        for name, data in linear_data.items():
            amplitude = data['amplitude']
            freq = data['freq']
            
            max_amp = np.max(amplitude)
            max_amp_idx = np.argmax(amplitude)
            resonance_freq = freq[max_amp_idx]
            
            half_power_level = max_amp * 0.707
            above_half_power = amplitude >= half_power_level
            if np.any(above_half_power):
                low_idx = np.where(above_half_power)[0][0]
                high_idx = np.where(above_half_power)[0][-1]
                bandwidth_707 = freq[high_idx] - freq[low_idx]
                bandwidth_707_range = (freq[low_idx], freq[high_idx])
            else:
                bandwidth_707 = 0
                bandwidth_707_range = (0, 0)
            
            above_fixed_level = amplitude >= self.fixedlevel
            if np.any(above_fixed_level):
                low_idx_fixed = np.where(above_fixed_level)[0][0]
                high_idx_fixed = np.where(above_fixed_level)[0][-1]
                bandwidth_fixed = freq[high_idx_fixed] - freq[low_idx_fixed]
                bandwidth_fixed_range = (freq[low_idx_fixed], freq[high_idx_fixed])
            else:
                bandwidth_fixed = 0
                bandwidth_fixed_range = (0, 0)
            
            q_factor = resonance_freq / bandwidth_707 if bandwidth_707 > 0 else 0
            
            channel_params[name] = {
                'max_amplitude': max_amp*2, #NOTE : тут надо быть крайне аккуратным, т.к. с физической точки зрения мы ничего не сделали, а только умножили на 2 значение выводимое пользователю
                'resonance_frequency': resonance_freq,
                'bandwidth_707': bandwidth_707,
                'bandwidth_707_range': bandwidth_707_range,
                'bandwidth_fixed': bandwidth_fixed,
                'bandwidth_fixed_range': bandwidth_fixed_range,
                'q_factor': q_factor
            }
        
        self._cache['channel_parameters'] = channel_params
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
        """Исходные данные"""
        if 'raw_data' not in self._precomputed:
            self._precomputed['raw_data'] = {
                name: channel.data.copy()
                for name, channel in self.channels.items()
            }
        return self._precomputed['raw_data']

    @property
    @rounded_property
    def smoothed_data(self):
        """Сглаженные данные (не зависят от параметров)"""
        return self._precompute_smoothed_data()

    @property
    @rounded_property
    def cropped_data(self):
        """Обрезанные данные (зависят от параметров)"""
        return self._get_cropped_data()

    @property
    @rounded_property
    def rawplot(self):
        """Данные для исходного графика"""
        raw_data = self.raw_data
        return {
            name: {
                'time': data['Время'].values,
                'amplitude': data['Амплитуда'].values
            } for name, data in raw_data.items()
        }

    @property
    @rounded_property
    def smoothedplot(self):
        """Данные для графика сглаженных сигналов"""
        cropped_data = self._get_cropped_data()
        return {
            name: {
                'time': data['Время'].values - data['Время'].values[0],
                'smoothed_amplitude': data['Smoothed'].values
            } for name, data in cropped_data.items()
        }

    @property
    @rounded_property
    def freqresponse_linear(self):
        """Данные для графика АЧХ в линейной шкале"""
        freq_data = self._get_freq_response_data()
        return freq_data['linear']

    @property
    def freqresponse_dB(self):
        """Данные для графика АЧХ в дБ"""
        freq_data = self._get_freq_response_data()
        return freq_data['dB']

    @property
    @rounded_property
    def channel_parameters(self):
        """Параметры каналов"""
        return self._get_channel_parameters()
    
    @property
    def analysis_start_time(self):
        cropped_data = self._get_cropped_data()
        first_channel = list(cropped_data.values())[0]
        return first_channel['Время'].iloc[0]

    @property
    @rounded_property
    def raw_max_amp(self):
        """Максимальная амплитуда в исходных данных по каналам"""
        extremums = self._precompute_raw_extremums()
        return {name: data['max_amp'] for name, data in extremums.items()}

    @property
    @rounded_property
    def raw_min_amp(self):
        """Минимальная амплитуда в исходных данных по каналам"""
        extremums = self._precompute_raw_extremums()
        return {name: data['min_amp'] for name, data in extremums.items()}

    @property
    def raw_maxamp_idx(self):
        """Индексы максимальной амплитуды в исходных данных по каналам"""
        extremums = self._precompute_raw_extremums()
        return {name: data['maxamp_idx'] for name, data in extremums.items()}

    @property
    def raw_minamp_idx(self):
        """Индексы минимальной амплитуды в исходных данных по каналам"""
        extremums = self._precompute_raw_extremums()
        return {name: data['minamp_idx'] for name, data in extremums.items()}