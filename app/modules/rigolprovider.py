# modules/rigolprovider.py
import logging
from typing import Dict, Any, Optional
import time
from core.VISA_provider import VISAProvider

# Настройка логирования
logger = logging.getLogger(__name__)

class RigolError(Exception):
    """Базовое исключение для ошибок Rigol"""
    pass

class RigolCommunicationError(RigolError):
    """Ошибка связи с прибором"""
    pass

class RigolConfigurationError(RigolError):
    """Ошибка конфигурации прибора"""
    pass

class RigolValidationError(RigolError):
    """Ошибка валидации параметров"""
    pass

class RigolProvider:
    def __init__(self, resource_name: str = None):
        self.visa = VISAProvider(resource_name)
        self.connection_status = 0
        self.model_name = ""
        
        # Пределы параметров для различных моделей Rigol (в зависимости от модели)
        self._parameter_limits = {
            # DG1000 series limits
            "DG1022": {
                "frequency": {"min": 0.001, "max": 20e6},  # 1 mHz - 60 MHz
                "amplitude": {"min": 0.001, "max": 20.0},  # 1 mVpp - 10 Vpp
                "offset": {"min": -5.0, "max": 5.0},       # -5V - +5V
                "sweep_time": {"min": 0.001, "max": 500.0}, # 1 ms - 500 s
            },
            # Default limits for unknown models
            "default": {
                "frequency": {"min": 0.001, "max": 20e6},
                "amplitude": {"min": 0.001, "max": 20.0},
                "offset": {"min": -5.0, "max": 5.0},
                "sweep_time": {"min": 0.001, "max": 500.0},
            }
        }
        
        # Текущие используемые пределы
        self._current_limits = self._parameter_limits["default"]
    
    def _get_model_limits(self, model_name: str) -> Dict[str, Any]:
        """Получить пределы параметров для конкретной модели"""
        model_upper = model_name.upper()
        
        if "DG1000" in model_upper or "DG1062" in model_upper or "DG1032" in model_upper:
            return self._parameter_limits["DG1000Z"]
        elif "DG800" in model_upper:
            return self._parameter_limits["DG800"]
        else:
            logger.warning(f"Unknown model {model_name}, using default limits")
            return self._parameter_limits["default"]
    
    def _validate_frequency(self, frequency: float) -> None:
        """Валидация частоты"""
        min_freq = self._current_limits["frequency"]["min"]
        max_freq = self._current_limits["frequency"]["max"]
        
        if not (min_freq <= frequency <= max_freq):
            raise RigolValidationError(
                f"Частота {frequency} Hz вне допустимого диапазона: "
                f"{min_freq} - {max_freq} Hz"
            )
    
    def _validate_amplitude(self, amplitude: float) -> None:
        """Валидация амплитуды"""
        min_amp = self._current_limits["amplitude"]["min"]
        max_amp = self._current_limits["amplitude"]["max"]
        
        if not (min_amp <= amplitude <= max_amp):
            raise RigolValidationError(
                f"Амплитуда {amplitude} V вне допустимого диапазона: "
                f"{min_amp} - {max_amp} V"
            )
    
    def _validate_offset(self, offset: float) -> None:
        """Валидация смещения"""
        min_offset = self._current_limits["offset"]["min"]
        max_offset = self._current_limits["offset"]["max"]
        
        if not (min_offset <= offset <= max_offset):
            raise RigolValidationError(
                f"Смещение {offset} V вне допустимого диапазона: "
                f"{min_offset} - {max_offset} V"
            )
    
    def _validate_sweep_time(self, sweep_time: float) -> None:
        """Валидация времени развертки"""
        min_time = self._current_limits["sweep_time"]["min"]
        max_time = self._current_limits["sweep_time"]["max"]
        
        if not (min_time <= sweep_time <= max_time):
            raise RigolValidationError(
                f"Время развертки {sweep_time} s вне допустимого диапазона: "
                f"{min_time} - {max_time} s"
            )
    
    def _validate_sweep_range(self, start_freq: float, stop_freq: float) -> None:
        """Валидация диапазона развертки"""
        self._validate_frequency(start_freq)
        self._validate_frequency(stop_freq)
        
        if start_freq >= stop_freq:
            raise RigolValidationError(
                f"Начальная частота ({start_freq} Hz) должна быть меньше конечной ({stop_freq} Hz)"
            )
    
    def _safe_execute(self, operation: str, func, *args, **kwargs) -> Any:
        """Безопасное выполнение операции с обработкой ошибок"""
        try:
            return func(*args, **kwargs)
        except RigolValidationError as e:
            logger.error(f"Ошибка валидации при {operation}: {str(e)}")
            raise
        except RigolConfigurationError as e:
            logger.error(f"Ошибка конфигурации при {operation}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при {operation}: {str(e)}")
            raise RigolCommunicationError(f"Ошибка при {operation}: {str(e)}")
    
    def connect(self) -> bool:
        """Установка соединения с прибором"""
        try:
            if not self.visa.connect():
                raise RigolCommunicationError("Failed to establish VISA connection")
            
            response = self.visa.query("*IDN?", delay=0.5)
            if not response:
                raise RigolCommunicationError("No response to IDN query")
            
            parts = response.split(',')
            if len(parts) < 2:
                raise RigolCommunicationError(f"Invalid IDN response: {response}")
            
            self.model_name = parts[1]
            
            # Устанавливаем пределы для конкретной модели
            self._current_limits = self._get_model_limits(self.model_name)
            
            self.connection_status = 1
            logger.info(f"Connected to {self.model_name} with limits: {self._current_limits}")
            return True
            
        except Exception as e:
            self.connection_status = 0
            logger.error(f"Connection failed: {str(e)}")
            raise RigolCommunicationError(f"Connection failed: {str(e)}")
        
    def disconnect(self):
        """Разрыв соединения с прибором"""
        try:
            self.visa.disconnect()
            self.connection_status = 0
            logger.info("Disconnected from device")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            raise RigolCommunicationError(f"Disconnect failed: {str(e)}")
    
    def get_parameter_limits(self) -> Dict[str, Any]:
        """Получить текущие пределы параметров"""
        return {
            "frequency": self._current_limits["frequency"].copy(),
            "amplitude": self._current_limits["amplitude"].copy(),
            "offset": self._current_limits["offset"].copy(),
            "sweep_time": self._current_limits["sweep_time"].copy(),
            "model": self.model_name
        }
    
    def set_function(self, function: str) -> None:
        """Установка формы сигнала"""
        valid_functions = ["SIN", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"]
        if function.upper() not in valid_functions:
            raise RigolValidationError(f"Недопустимая функция: {function}. Допустимые: {valid_functions}")
        
        self._safe_execute(f"set function {function}", lambda: self.visa.write(f"FUNC {function}"))
        time.sleep(0.1)
    
    def set_frequency(self, frequency: float) -> None:
        """Установка частоты сигнала с валидацией"""
        self._validate_frequency(frequency)
        self._safe_execute(f"set frequency {frequency}", lambda: self.visa.write(f"FREQ {frequency}"))
        time.sleep(0.1)
    
    def set_amplitude(self, amplitude: float) -> None:
        """Установка амплитуды сигнала с валидацией"""
        self._validate_amplitude(amplitude)
        self._safe_execute(f"set amplitude {amplitude}", lambda: self.visa.write(f"VOLT {amplitude}"))
        time.sleep(0.1)
    
    def set_offset(self, offset: float) -> None:
        """Установка смещения сигнала с валидацией"""
        self._validate_offset(offset)
        self._safe_execute(f"set offset {offset}", lambda: self.visa.write(f"VOLT:OFFS {offset}"))
        time.sleep(0.1)
    
    def enable_sweep(self, enable: bool = True) -> None:
        """Включение/выключение режима развертки"""
        state = "ON" if enable else "OFF"
        self._safe_execute(f"set sweep {state}", lambda: self.visa.write(f"SWE:STAT {state}"))
        time.sleep(0.1)
    
    def set_sweep_spacing(self, spacing: str) -> None:
        """Установка типа развертки (LIN - линейная, LOG - логарифмическая)"""
        valid_spacings = ["LIN", "LOG"]
        if spacing.upper() not in valid_spacings:
            raise RigolValidationError(f"Недопустимый тип развертки: {spacing}. Допустимые: {valid_spacings}")
        
        self._safe_execute(f"set sweep spacing {spacing}", lambda: self.visa.write(f"SWE:SPAC {spacing}"))
        time.sleep(0.1)
    
    def set_sweep_start_frequency(self, frequency: float) -> None:
        """Установка начальной частоты развертки с валидацией"""
        self._validate_frequency(frequency)
        self._safe_execute(f"set sweep start {frequency}", lambda: self.visa.write(f"FREQ:STAR {frequency}"))
        time.sleep(0.1)
    
    def set_sweep_stop_frequency(self, frequency: float) -> None:
        """Установка конечной частоты развертки с валидацией"""
        self._validate_frequency(frequency)
        self._safe_execute(f"set sweep stop {frequency}", lambda: self.visa.write(f"FREQ:STOP {frequency}"))
        time.sleep(0.1)
    
    def set_sweep_time(self, sweep_time: float) -> None:
        """Установка времени развертки с валидацией"""
        self._validate_sweep_time(sweep_time)
        self._safe_execute(f"set sweep time {sweep_time}", lambda: self.visa.write(f"SWE:TIME {sweep_time}"))
        time.sleep(0.1)
    
    def set_trigger_source(self, source: str = "IMM") -> None:
        """Установка источника триггера"""
        valid_sources = ["IMM", "EXT", "MAN"]
        if source.upper() not in valid_sources:
            raise RigolValidationError(f"Недопустимый источник триггера: {source}. Допустимые: {valid_sources}")
        
        self._safe_execute(f"set trigger source {source}", lambda: self.visa.write(f"TRIG:SOUR {source}"))
        time.sleep(0.1)
    
    def set_output(self, enable: bool = True) -> None:
        """Включение/выключение выхода"""
        state = "ON" if enable else "OFF"
        self._safe_execute(f"set output {state}", lambda: self.visa.write(f"OUTP {state}"))
    
    def configure_sweep(self, start_freq: float, stop_freq: float, sweep_time: float, 
                        function: str = "SIN", amplitude: float = 1.0, offset: float = 0.0) -> None:
        """Конфигурация полного цикла развертки с валидацией всех параметров"""
        try:
            # Валидация всех параметров перед настройкой
            self._validate_sweep_range(start_freq, stop_freq)
            self._validate_sweep_time(sweep_time)
            self._validate_amplitude(amplitude)
            self._validate_offset(offset)
            
            # Настройка прибора
            self.set_function(function)
            self.set_amplitude(amplitude)
            self.set_offset(offset)
            self.enable_sweep(True)
            self.set_sweep_spacing("LIN")
            self.set_sweep_start_frequency(start_freq)
            self.set_sweep_stop_frequency(stop_freq)
            self.set_sweep_time(sweep_time)
            self.set_trigger_source("IMM")
            
            logger.info(f"Sweep configured: {start_freq}-{stop_freq}Hz, {sweep_time}s, {amplitude}V, {offset}V")
            
        except Exception as e:
            logger.error(f"Failed to configure sweep: {str(e)}")
            raise RigolConfigurationError(f"Failed to configure sweep: {str(e)}")
    
    def run_sweep(self, duration: float = 10.0) -> None:
        """Запуск развертки на указанное время"""
        if duration <= 0:
            raise RigolValidationError(f"Длительность развертки должна быть положительной: {duration}")
        
        try:
            self.set_output(True)
            logger.info(f"Sweep started for {duration} seconds")
            time.sleep(duration)
            self.set_output(False)
            logger.info("Sweep finished")
        except Exception as e:
            logger.error(f"Failed to run sweep: {str(e)}")
            # Пытаемся выключить выход при ошибке
            try:
                self.set_output(False)
            except:
                pass
            raise RigolConfigurationError(f"Failed to run sweep: {str(e)}")
    
    def test_connection(self) -> bool:
        """Тестирование соединения с прибором"""
        try:
            response = self.visa.query("*IDN?", delay=0.5)
            return bool(response and self.model_name in response)
        except:
            return False
    
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()