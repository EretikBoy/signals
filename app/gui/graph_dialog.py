# gui/graph_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout,
    QComboBox, QTextEdit
)

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QCursor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from core.dataprocessor import Processor

class CustomNavigationToolbar(NavigationToolbar):
    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        self.coord_label = QLabel()
        self.coord_label.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.coord_label.setStyleSheet("background-color: white; border: 1px solid black;")
        self.coord_label.hide()
        
    def addmousecoords(self):
        self.canvas.mpl_connect('motion_notify_event', self._update_mouse_coords)

    def _update_mouse_coords(self, event):
        if event.inaxes:
            x, y = event.xdata, event.ydata
            text = f"x: {x:.3f}, y: {y:.3f}"
            self.coord_label.setText(text)
            self.coord_label.adjustSize()
            
            # Позиционируем метку рядом с курсором (глобальные координаты)
            pos = QCursor.pos()
            self.coord_label.move(pos + QPoint(15, 15))
            self.coord_label.show()
        else:
            self.coord_label.hide()

class GraphDialog(QDialog):
    '''Диалоговое окно с графиками и настройками параметров'''
    
    def __init__(self, channels, params, processor, file_name, parent=None):
        super().__init__(parent)
        self.channels = channels
        self.params = params
        self.processor = processor
        self.selected_channel = 'CH2'  # По умолчанию выбираем CH2
        self.setWindowTitle(f'Графики и настройка параметров - {file_name}')
        self.setGeometry(200, 200, 1200, 800)
        
        self.init_ui()
        self.update_plots()
    
    def init_ui(self):
        '''Инициализация пользовательского интерфейса'''
        layout = QHBoxLayout(self)
        
        # Панель настроек
        settings_group = QGroupBox('Настройки параметров')
        settings_layout = QGridLayout(settings_group)
        
        row = 0
        
        # Выбор канала для анализа
        settings_layout.addWidget(QLabel('Канал для анализа:'), row, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(list(self.channels.keys()))
        self.channel_combo.setCurrentText(self.selected_channel)
        self.channel_combo.currentTextChanged.connect(self.channel_changed)
        settings_layout.addWidget(self.channel_combo, row, 1)
        row += 1
        
        # Поля для настройки параметров
        settings_layout.addWidget(QLabel('Стартовая частота (Гц):'), row, 0)
        self.start_freq_spin = QSpinBox()
        self.start_freq_spin.setRange(0, 100000)
        self.start_freq_spin.setValue(int(self.params.get('start_freq', 0)))
        self.start_freq_spin.valueChanged.connect(self.param_changed)
        settings_layout.addWidget(self.start_freq_spin, row, 1)
        row += 1
        
        settings_layout.addWidget(QLabel('Конечная частота (Гц):'), row, 0)
        self.end_freq_spin = QSpinBox()
        self.end_freq_spin.setRange(0, 100000)
        self.end_freq_spin.setValue(int(self.params.get('end_freq', 0)))
        self.end_freq_spin.valueChanged.connect(self.param_changed)
        settings_layout.addWidget(self.end_freq_spin, row, 1)
        row += 1
        
        settings_layout.addWidget(QLabel('Время записи (с):'), row, 0)
        self.record_time_spin = QDoubleSpinBox()
        self.record_time_spin.setRange(0.1, 100.0)
        self.record_time_spin.setSingleStep(0.1)
        self.record_time_spin.setValue(self.params.get('record_time', 1.0))
        self.record_time_spin.valueChanged.connect(self.param_changed)
        settings_layout.addWidget(self.record_time_spin, row, 1)
        row += 1
        
        settings_layout.addWidget(QLabel("Относительное смещение строба (c):"), row, 0)
        self.cut_second_spin = QDoubleSpinBox()
        self.cut_second_spin.setRange(-100, 100.0)
        self.cut_second_spin.setSingleStep(0.1)
        self.cut_second_spin.setValue(self.params.get('cut_second', 0.0))
        self.cut_second_spin.valueChanged.connect(self.apply_values)
        settings_layout.addWidget(self.cut_second_spin, row, 1)
        row += 1
        
        # Новые поля: коэффициент усиления и пороговый уровень
        settings_layout.addWidget(QLabel('Коэффициент усиления:'), row, 0)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0.1, 100.0)
        self.gain_spin.setSingleStep(0.1)
        self.gain_spin.setValue(self.params.get('gain', 1.0))
        self.gain_spin.valueChanged.connect(self.apply_values)
        settings_layout.addWidget(self.gain_spin, row, 1)
        row += 1
        
        settings_layout.addWidget(QLabel('Пороговый уровень (В):'), row, 0)
        self.fixedlevel_spin = QDoubleSpinBox()
        self.fixedlevel_spin.setRange(0.0, 1.0)
        self.fixedlevel_spin.setSingleStep(0.01)
        self.fixedlevel_spin.setValue(self.params.get('fixedlevel', 0.1))
        self.fixedlevel_spin.valueChanged.connect(self.apply_values)
        settings_layout.addWidget(self.fixedlevel_spin, row, 1)
        row += 1
        
        # Кнопка применения
        apply_button = QPushButton('Применить значения')
        apply_button.clicked.connect(self.apply_values)
        settings_layout.addWidget(apply_button, row, 0, 1, 2)
        row += 1
        
        # Кнопка закрытия
        close_button = QPushButton('Закрыть')
        close_button.clicked.connect(self.accept)
        settings_layout.addWidget(close_button, row, 0, 1, 2)
        
        # Область с графиками
        plots_widget = QGroupBox('Графики')
        plots_layout = QVBoxLayout(plots_widget)
        
        # Создаем три графика
        self.figure = Figure(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        # Добавляем навигационную панель
        self.toolbar = CustomNavigationToolbar(self.canvas, self)
        plots_layout.addWidget(self.toolbar)
        self.toolbar.addmousecoords()
        
        # Создаем три субплога
        self.ax1 = self.figure.add_subplot(311)
        self.ax2 = self.figure.add_subplot(312)
        self.ax3 = self.figure.add_subplot(313)
        
        self.figure.tight_layout(pad=1.0)
        plots_layout.addWidget(self.canvas)
        
        # Добавим отображение параметров канала
        self.params_display = QTextEdit()
        self.params_display.setReadOnly(True)
        self.params_display.setMaximumHeight(200)

        # Добавляем объекты в основной layout
        layout.addWidget(settings_group, 1)
        layout.addWidget(plots_widget, 3)
        layout.addWidget(self.params_display, 1)
    
    def channel_changed(self, channel_name):
        """Обработчик изменения выбранного канала"""
        self.selected_channel = channel_name
        self.update_plots()
    
    def param_changed(self):
        """Обработчик изменения параметров"""
        # При изменении параметров просто обновляем графики без применения к процессору
        self.update_plots()
    
    def apply_values(self):
        '''Применение выбранных значений параметров'''
        new_params = {
            'start_freq': self.start_freq_spin.value(),
            'end_freq': self.end_freq_spin.value(),
            'record_time': self.record_time_spin.value(),
            'cut_second': self.cut_second_spin.value(),
            'gain': self.gain_spin.value(),
            'fixedlevel': self.fixedlevel_spin.value()
        }
        
        # Обновляем параметры в процессоре
        self.processor.update_params(new_params)
        
        # Обновляем графики
        self.update_plots()
    
    def update_plots(self):
        '''Обновление графиков с текущими параметрами'''
        # Очищаем графики
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()
        
        # Получаем данные из процессора
        raw_data = self.processor.rawplot
        smoothed_data = self.processor.smoothedplot
        freq_response = self.processor.freqresponse_linear
        
        # Определяем анализируемый отрезок времени
        cut_second = self.cut_second_spin.value()
        record_time = self.record_time_spin.value()
        
        # Строим исходные графики
        y_min, y_max = float('inf'), float('-inf')
        for channel_name, data in raw_data.items():
            if channel_name in self.channels:  # Отображаем только выбранные каналы
                self.ax1.plot(data['time'], data['amplitude'], label=channel_name)
                
                # Определяем min/max амплитуды для отрисовки строба
                channel_min = self.processor.raw_min_amp[channel_name]
                channel_max = self.processor.raw_max_amp[channel_name]
                y_min = min(y_min, channel_min)
                y_max = max(y_max, channel_max)
        
        # Добавляем строб (прямоугольник выделения анализируемого отрезка)
        if y_min != float('inf') and y_max != float('-inf'):
            start_time = self.processor.analysis_start_time
            rect = Rectangle((start_time, y_min), record_time, y_max - y_min,
                            linewidth=1, edgecolor='r', facecolor='r', alpha=0.2)
            self.ax1.add_patch(rect)
            # Добавляем запись в легенду
            self.ax1.plot([], [], color='r', alpha=0.2, linewidth=10, label='Анализируемый отрезок')
        
        # Строим сглаженные графики
        for channel_name, data in smoothed_data.items():
            if channel_name in self.channels:  # Отображаем только выбранные каналы
                self.ax2.plot(data['time'], data['smoothed_amplitude'], label=channel_name)
        
        # Строим АЧХ только для выбранного канала (линейная шкала с усилением)
        if self.selected_channel in freq_response:
            data = freq_response[self.selected_channel]
            self.ax3.plot(data['freq'], data['amplitude'], label=self.selected_channel, color='red')
            
            # Добавляем маркеры для важных точек
            params = self.processor.channel_parameters.get(self.selected_channel, {})
            if params:
                # Резонансная частота
                self.ax3.axvline(x=params['resonance_frequency'], color='green', linestyle='--', 
                                label=f'Резонанс: {params["resonance_frequency"]:.2f} Гц')
                
                # Уровень 0.707
                self.ax3.axhline(y=params['max_amplitude'] * 0.707, color='blue', linestyle='--', 
                                label='Уровень 0.707')
                
                # Уровень fixedlevel
                fixedlevel = self.fixedlevel_spin.value()
                self.ax3.axhline(y=fixedlevel, color='orange', linestyle='--', 
                                label=f'Уровень {fixedlevel}')
        
        # Настраиваем графики
        self.ax1.set_title("Исходные сигналы")
        self.ax1.set_xlabel("Время (с)")
        self.ax1.set_ylabel("Амплитуда (В)")
        self.ax1.legend()
        self.ax1.grid(True)
        
        self.ax2.set_title("Сглаженные сигналы")
        self.ax2.set_xlabel("Время (с)")
        self.ax2.set_ylabel("Амплитуда (В)")
        self.ax2.legend()
        self.ax2.grid(True)
        
        self.ax3.set_title("АЧХ (линейная шкала с усилением)")
        self.ax3.set_xlabel("Частота (Гц)")
        self.ax3.set_ylabel("Амплитуда сигнала")
        self.ax3.legend()
        self.ax3.grid(True)
        
        # Обновляем отображение параметров
        self.update_parameters_display()
        
        # Обновляем canvas
        self.figure.tight_layout(pad=3.0)
        self.canvas.draw()

    def update_parameters_display(self):
        """Обновление отображения параметров выбранного канала"""
        params = self.processor.channel_parameters.get(self.selected_channel, {})
        if not params:
            self.params_display.setPlainText("Параметры не рассчитаны")
            return
        
        # Получаем текущие значения параметров из spin-боксов
        fixedlevel = self.fixedlevel_spin.value()
        
        text = f"Параметры канала {self.selected_channel}:\n\n"
        text += f"Максимальная амплитуда: {params['max_amplitude']:.4f} В\n"
        text += f"Резонансная частота: {params['resonance_frequency']:.2f} Гц\n"
        text += f"Ширина полосы (0.707): {params['bandwidth_707']:.2f} Гц\n"
        text += f"  (от {params['bandwidth_707_range'][0]:.2f} до {params['bandwidth_707_range'][1]:.2f} Гц)\n"
        text += f"Ширина полосы (уровень {fixedlevel}): {params['bandwidth_fixed']:.2f} Гц\n"
        text += f"  (от {params['bandwidth_fixed_range'][0]:.2f} до {params['bandwidth_fixed_range'][1]:.2f} Гц)\n"
        text += f"Добротность: {params['q_factor']:.2f}"
        
        self.params_display.setPlainText(text)