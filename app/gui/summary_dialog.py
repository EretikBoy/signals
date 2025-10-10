# gui/summary_dialog.py

import os
import tempfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMessageBox, QFileDialog, QProgressBar, QCheckBox, QScrollArea, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, Alignment
import logging

logger = logging.getLogger(__name__)


class LegendWidget(QWidget):
    """Виджет легенды с чекбоксами"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}
        self.lines_mapping = {}  # checkbox -> line object
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса легенды"""
        layout = QVBoxLayout()
        
        # Заголовок
        title_label = QLabel('Легенда')
        title_label.setStyleSheet('font-weight: bold; margin: 5px;')
        layout.addWidget(title_label)
        
        # Фрейм для чекбоксов
        self.checkbox_frame = QFrame()
        self.checkbox_layout = QVBoxLayout(self.checkbox_frame)
        self.checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.checkbox_frame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumWidth(250)
        scroll_area.setMinimumWidth(200)
        
        layout.addWidget(scroll_area)
        self.setLayout(layout)
    
    def add_line(self, label, line, color):
        """Добавление линии в легенду"""
        checkbox = QCheckBox(label)
        checkbox.setChecked(True)
        checkbox.setStyleSheet(f"QCheckBox {{ color: {color}; }}")
        
        # Сохраняем связь
        self.checkboxes[label] = checkbox
        self.lines_mapping[checkbox] = line
        
        self.checkbox_layout.addWidget(checkbox)
        
        # Подключаем сигнал
        checkbox.stateChanged.connect(self.on_checkbox_changed)
    
    def on_checkbox_changed(self):
        """Обработка изменения состояния чекбокса"""
        checkbox = self.sender()
        if checkbox in self.lines_mapping:
            line = self.lines_mapping[checkbox]
            visible = checkbox.isChecked()
            line.set_visible(visible)
            
            # Передаем сигнал родительскому виджету
            if hasattr(self.parent(), 'on_legend_visibility_changed'):
                self.parent().on_legend_visibility_changed()


class SummaryDialog(QDialog):
    """Диалог для построения сводного графика АЧХ из выбранных анализов"""
    
    def __init__(self, data_manager, tree_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.tree_manager = tree_manager
        self.setWindowTitle('Сводный график АЧХ')
        self.setGeometry(100, 100, 1400, 900)
        
        # Данные для графиков
        self.frequency_responses = {}  # (subject_code, analysis_index, channel_name) -> (freqs, response)
        self.lines = {}  # (subject_code, analysis_index, channel_name) -> line object
        
        self.setup_ui()
        self.load_selected_analyses()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        main_layout = QHBoxLayout()
        
        # Левая часть - график
        left_layout = QVBoxLayout()
        
        # Заголовок
        title_label = QLabel('Сводный график АЧХ выбранных анализов')
        title_label.setStyleSheet('font-size: 14px; font-weight: bold; margin: 10px;')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title_label)
        
        # График
        self.setup_plot(left_layout)
        
        # Элементы управления
        self.setup_controls(left_layout)
        
        # Кнопки
        self.setup_buttons(left_layout)
        
        # Правая часть - легенда
        self.legend_widget = LegendWidget(self)
        
        # Добавляем обе части в основной layout
        main_layout.addLayout(left_layout, 4)  # 4/5 ширины для графика
        main_layout.addWidget(self.legend_widget, 1)  # 1/5 ширины для легенды
        
        self.setLayout(main_layout)
    
    def setup_plot(self, layout):
        """Настройка области графика"""
        # Создаем фигуру и canvas
        self.figure = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Создаем оси
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Частота (Гц)')
        self.ax.set_ylabel('Амплитуда (В)')
        self.ax.set_title('Амплитудно-частотная характеристика')
        self.ax.grid(True, alpha=0.3)
        
        # Сохраняем исходные пределы осей
        self.original_xlim = None
        self.original_ylim = None
    
    def setup_controls(self, layout):
        """Настройка элементов управления"""
        controls_layout = QHBoxLayout()
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Чекбокс для автоматического обновления
        self.auto_update_cb = QCheckBox("Автообновление масштаба")
        self.auto_update_cb.setChecked(True)
        
        # Кнопка сброса масштаба
        self.reset_zoom_btn = QPushButton('Сбросить масштаб')
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)
        
        controls_layout.addWidget(self.progress_bar)
        controls_layout.addWidget(self.auto_update_cb)
        controls_layout.addWidget(self.reset_zoom_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
    
    def setup_buttons(self, layout):
        """Настройка кнопок"""
        buttons_layout = QHBoxLayout()
        
        # Кнопка обновления
        self.update_btn = QPushButton('Обновить график')
        self.update_btn.clicked.connect(self.load_selected_analyses)
        
        # Кнопка экспорта
        self.export_btn = QPushButton('Экспорт в Excel')
        self.export_btn.clicked.connect(self.export_to_excel)
        
        # Кнопка закрытия
        self.close_btn = QPushButton('Закрыть')
        self.close_btn.clicked.connect(self.close)
        
        buttons_layout.addWidget(self.update_btn)
        buttons_layout.addWidget(self.export_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.close_btn)
        
        layout.addLayout(buttons_layout)
    
    def reset_zoom(self):
        """Сброс масштаба к исходному"""
        if self.original_xlim and self.original_ylim:
            self.ax.set_xlim(self.original_xlim)
            self.ax.set_ylim(self.original_ylim)
            self.canvas.draw()
    
    def on_legend_visibility_changed(self):
        """Обработка изменения видимости через легенду"""
        if self.auto_update_cb.isChecked():
            self.auto_adjust_axes()
        self.canvas.draw()
    
    def load_selected_analyses(self):
        """Загрузка выбранных анализов и построение графиков в абсолютных величинах"""
        try:
            # Получаем выбранные анализы
            selected_analyses = self.tree_manager.get_selected_analyses()
            
            if not selected_analyses:
                QMessageBox.information(self, 'Информация', 'Не выбрано ни одного анализа')
                return
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, len(selected_analyses))
            
            # Очищаем предыдущие данные
            self.frequency_responses.clear()
            self.lines.clear()
            self.legend_widget.checkboxes.clear()
            self.legend_widget.lines_mapping.clear()
            
            # Очищаем layout легенды
            for i in reversed(range(self.legend_widget.checkbox_layout.count())):
                widget = self.legend_widget.checkbox_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            
            self.ax.clear()
            
            processed_count = 0
            valid_analyses = 0
            
            for i, (subject_code, analysis_index) in enumerate(selected_analyses):
                self.progress_bar.setValue(i)
                
                try:
                    # Получаем данные анализа
                    analysis_data = self.data_manager.get_analysis_data(subject_code, analysis_index)
                    if not analysis_data:
                        logger.warning(f"Данные анализа не найдены: {subject_code}, {analysis_index}")
                        continue
                    
                    # Получаем процессор
                    processor = analysis_data.get('processor')
                    if not processor:
                        logger.warning(f"Процессор не найден: {subject_code}, {analysis_index}")
                        continue
                    
                    # Получаем данные АЧХ в абсолютных величинах для всех каналов
                    freq_response_data = processor.freqresponse_linear
                    
                    if not freq_response_data:
                        logger.warning(f"Нет данных АЧХ для анализа: {subject_code}, {analysis_index}")
                        continue
                    
                    # Обрабатываем каждый канал
                    for channel_name, channel_data in freq_response_data.items():
                        freqs = channel_data['freq']
                        amplitude = channel_data['amplitude']  # Абсолютные величины в Вольтах
                        
                        # Проверяем валидность данных
                        if (freqs is not None and amplitude is not None and 
                            len(freqs) > 0 and len(amplitude) > 0 and
                            not np.all(np.isnan(amplitude)) and not np.all(np.isinf(amplitude))):
                            
                            # Заменяем inf/nan на минимальное/максимальное значение
                            valid_mask = np.isfinite(amplitude)
                            if np.any(valid_mask):
                                # Используем только валидные точки
                                valid_freqs = freqs[valid_mask]
                                valid_amplitude = amplitude[valid_mask]
                                
                                # Заменяем оставшиеся inf/nan
                                if len(valid_amplitude) > 0:
                                    min_amp = np.min(valid_amplitude)
                                    max_amp = np.max(valid_amplitude)
                                    valid_amplitude = np.where(
                                        np.isinf(valid_amplitude) | np.isnan(valid_amplitude), 
                                        min_amp, valid_amplitude
                                    )
                                
                                # Сохраняем данные
                                key = (subject_code, analysis_index, channel_name)
                                self.frequency_responses[key] = (valid_freqs, valid_amplitude)
                                valid_analyses += 1
                                
                                # Строим график
                                label = f"{subject_code}_{analysis_index}_{channel_name}"
                                line, = self.ax.plot(valid_freqs, valid_amplitude, linewidth=2)
                                self.lines[key] = line
                                
                                # Добавляем в легенду
                                color = line.get_color()
                                self.legend_widget.add_line(label, line, color)
                            
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки анализа {subject_code}_{analysis_index}: {str(e)}")
                    continue
            
            if valid_analyses == 0:
                self.ax.text(0.5, 0.5, 'Нет данных для построения графика', 
                           transform=self.ax.transAxes, ha='center', va='center')
                self.ax.set_xlabel('Частота (Гц)')
                self.ax.set_ylabel('Амплитуда (В)')
                self.ax.set_title('Амплитудно-частотная характеристика')
            else:
                self.ax.set_xlabel('Частота (Гц)')
                self.ax.set_ylabel('Амплитуда (В)')
                self.ax.set_title(f'Сводный график АЧХ')
                self.ax.grid(True, alpha=0.3)
                
                # Сохраняем исходные пределы осей
                self.original_xlim = self.ax.get_xlim()
                self.original_ylim = self.ax.get_ylim()
                
                # Автоматически настраиваем масштаб
                self.auto_adjust_axes()
            
            self.canvas.draw()
            self.progress_bar.setVisible(False)
            
            logger.info(f"Обработано {processed_count} анализов, построено {valid_analyses} графиков")
            
        except Exception as e:
            logger.error(f"Ошибка при построении сводного графика: {str(e)}")
            QMessageBox.critical(self, 'Ошибка', f'Не удалось построить график: {str(e)}')
            self.progress_bar.setVisible(False)
    
    def auto_adjust_axes(self):
        """Автоматическая подстройка масштаба осей для видимых линий"""
        if not self.auto_update_cb.isChecked():
            return
            
        try:
            # Собираем все видимые данные
            all_visible_freqs = []
            all_visible_responses = []
            
            for key, line in self.lines.items():
                if line.get_visible():
                    freqs, response = self.frequency_responses[key]
                    all_visible_freqs.extend(freqs)
                    all_visible_responses.extend(response)
            
            if not all_visible_freqs or not all_visible_responses:
                return
            
            # Преобразуем в numpy arrays для вычислений
            all_visible_freqs = np.array(all_visible_freqs)
            all_visible_responses = np.array(all_visible_responses)
            
            # Убираем NaN и inf значения
            valid_mask = np.isfinite(all_visible_responses) & np.isfinite(all_visible_freqs)
            if not np.any(valid_mask):
                return
            
            all_visible_freqs = all_visible_freqs[valid_mask]
            all_visible_responses = all_visible_responses[valid_mask]
            
            # Вычисляем пределы с небольшим отступом
            x_min, x_max = np.min(all_visible_freqs), np.max(all_visible_freqs)
            y_min, y_max = np.min(all_visible_responses), np.max(all_visible_responses)
            
            # Добавляем отступы (5% от диапазона)
            x_range = x_max - x_min
            y_range = y_max - y_min
            
            x_padding = x_range * 0.05 if x_range > 0 else 1
            y_padding = y_range * 0.05 if y_range > 0 else 1
            
            self.ax.set_xlim(x_min - x_padding, x_max + x_padding)
            self.ax.set_ylim(y_min - y_padding, y_max + y_padding)
            
        except Exception as e:
            logger.error(f"Ошибка при автоматической подстройке осей: {str(e)}")
    
    def get_visible_analyses(self):
        """Получение списка видимых анализов"""
        visible_keys = []
        for key, line in self.lines.items():
            if line.get_visible():
                visible_keys.append(key)
        return visible_keys
    
    def format_channel_parameters(self, channel_params, fixedlevel):
        """Форматирование параметров канала в текстовый вид"""
        if not channel_params:
            return "Параметры не рассчитаны"
        
        text = ""
        text += f"Максимальная амплитуда: {channel_params.get('max_amplitude', 0):.4f} В\n"
        text += f"Резонансная частота: {channel_params.get('resonance_frequency', 0):.2f} Гц\n"
        text += f"Ширина полосы (0.707): {channel_params.get('bandwidth_707', 0):.2f} Гц\n"
        
        bandwidth_707_range = channel_params.get('bandwidth_707_range', (0, 0))
        text += f"  (от {bandwidth_707_range[0]:.2f} до {bandwidth_707_range[1]:.2f} Гц)\n"
        
        text += f"Ширина полосы (уровень {fixedlevel}): {channel_params.get('bandwidth_fixed', 0):.2f} Гц\n"
        
        bandwidth_fixed_range = channel_params.get('bandwidth_fixed_range', (0, 0))
        text += f"  (от {bandwidth_fixed_range[0]:.2f} до {bandwidth_fixed_range[1]:.2f} Гц)\n"
        
        text += f"Добротность: {channel_params.get('q_factor', 0):.2f}"
        
        return text
    
    def export_to_excel(self):
        """Экспорт данных в Excel - только видимые графики в абсолютных величинах со всеми точками"""
        # Получаем только видимые анализы
        visible_keys = self.get_visible_analyses()
        
        if not visible_keys:
            QMessageBox.warning(self, 'Предупреждение', 'Нет видимых графиков для экспорта')
            return
        
        try:
            # Запрашиваем файл для сохранения
            file_name, _ = QFileDialog.getSaveFileName(
                self, 
                'Экспорт в Excel', 
                'summary_analysis.xlsx', 
                'Excel Files (*.xlsx)'
            )
            
            if not file_name:
                return
            
            self.progress_bar.setVisible(True)
            total_items = len(visible_keys)
            self.progress_bar.setRange(0, total_items + 2)
            
            # Создаем временное изображение графика
            temp_img_path = os.path.join(tempfile.gettempdir(), 'summary_plot.png')
            self.figure.savefig(temp_img_path, dpi=150, bbox_inches='tight')
            
            # Создаем Excel workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Сводный анализ АЧХ"
            
            # Устанавливаем ширину колонок
            ws.column_dimensions['A'].width = 25
            ws.column_dimensions['B'].width = 20
            ws.column_dimensions['C'].width = 15
            ws.column_dimensions['D'].width = 15
            
            # Заголовок
            title_cell = ws['A1']
            title_cell.value = "Сводный анализ АЧХ (только видимые графики, абсолютные величины)"
            title_cell.font = Font(bold=True, size=16)
            ws.merge_cells('A1:D1')
            title_cell.alignment = Alignment(horizontal='center')
            
            current_row = 3
            progress_count = 0
            
            # Определяем максимальное количество точек среди всех каналов
            max_points = 0
            all_data = {}  # Сохраняем все данные для второго прохода
            
            # Первый проход: собираем данные и находим максимальное количество точек
            for key in visible_keys:
                subject_code, analysis_index, channel_name = key
                
                analysis_data = self.data_manager.get_analysis_data(subject_code, analysis_index)
                if not analysis_data:
                    continue
                
                processor = analysis_data.get('processor')
                if not processor:
                    continue
                
                # Получаем параметры анализа
                params = analysis_data.get('params', {})
                if not isinstance(params, dict):
                    params = {}
                
                # Получаем параметры канала
                channel_params = {}
                if hasattr(processor, 'channel_parameters'):
                    channel_params_dict = processor.channel_parameters
                    if isinstance(channel_params_dict, dict):
                        channel_params = channel_params_dict.get(channel_name, {})
                
                # Получаем линейные данные АЧХ (абсолютные величины) - ВСЕ точки
                linear_data = {}
                if hasattr(processor, 'freqresponse_linear'):
                    linear_response_data = processor.freqresponse_linear
                    if channel_name in linear_response_data:
                        linear_data = linear_response_data[channel_name]
                
                if linear_data and 'freq' in linear_data and 'amplitude' in linear_data:
                    freqs = linear_data['freq']
                    amplitudes = linear_data['amplitude']
                    
                    if len(freqs) > 0 and len(amplitudes) > 0:
                        max_points = max(max_points, len(freqs))
                        
                        # Сохраняем данные для второго прохода
                        all_data[key] = {
                            'freqs': freqs,
                            'amplitudes': amplitudes,
                            'subject_code': subject_code,
                            'analysis_index': analysis_index,
                            'channel_name': channel_name,
                            'params': params,
                            'channel_params': channel_params
                        }
            
            # Второй проход: записываем данные в Excel по горизонтали
            current_col = 1  # Начинаем с колонки A (индекс 1)
            
            for key in visible_keys:
                if key not in all_data:
                    continue
                    
                progress_count += 1
                self.progress_bar.setValue(progress_count)
                
                data = all_data[key]
                freqs = data['freqs']
                amplitudes = data['amplitudes']
                subject_code = data['subject_code']
                analysis_index = data['analysis_index']
                channel_name = data['channel_name']
                params = data['params']
                channel_params = data['channel_params']
                
                # Заголовок анализа и канала
                title_cell = ws.cell(row=current_row, column=current_col)
                title_cell.value = f"Анализ: {subject_code}_{analysis_index} - Канал: {channel_name}"
                title_cell.font = Font(bold=True)
                current_row += 1
                
                # Форматируем параметры канала (полная версия из исходного кода)
                fixedlevel = params.get('fixedlevel', 0.6)
                parameters_text = self.format_channel_parameters(channel_params, fixedlevel)
                
                # Разбиваем текст параметров на строки и записываем в Excel
                lines = parameters_text.split('\n')
                for i, line in enumerate(lines):
                    param_cell = ws.cell(row=current_row + i, column=current_col)
                    param_cell.value = line
                
                current_row += len(lines) + 1  # Отступ после параметров
                
                # Заголовки таблицы данных
                freq_header = ws.cell(row=current_row, column=current_col)
                freq_header.value = "Частота (Гц)"
                freq_header.font = Font(bold=True)
                
                amp_header = ws.cell(row=current_row, column=current_col + 1)
                amp_header.value = "Амплитуда (В)"
                amp_header.font = Font(bold=True)
                
                current_row += 1
                
                # Записываем ВСЕ точки данных
                for i in range(len(freqs)):
                    freq_cell = ws.cell(row=current_row + i, column=current_col)
                    amp_cell = ws.cell(row=current_row + i, column=current_col + 1)
                    
                    freq_cell.value = float(freqs[i])
                    amp_cell.value = float(amplitudes[i])
                
                # Переходим к следующей группе колонок (с отступом в 2 колонки)
                current_col += 3
                # Сбрасываем строку для следующего канала
                current_row = 3
            
            # Добавляем изображение графика СПРАВА от данных
            if os.path.exists(temp_img_path):
                try:
                    img = XLImage(temp_img_path)
                    # Размещаем изображение справа от данных (колонка после последней группы данных)
                    image_start_col = current_col + 1
                    img.anchor = f'{chr(64 + image_start_col)}3'  # Например, 'E3' если current_col=4
                    ws.add_image(img)
                except Exception as e:
                    logger.error(f"Ошибка при добавлении изображения в Excel: {str(e)}")
            
            # Сохраняем файл
            try:
                wb.save(file_name)
                logger.info(f"Файл успешно сохранен: {file_name}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении Excel файла: {str(e)}")
                raise
            
            # Удаляем временный файл
            try:
                os.remove(temp_img_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл: {str(e)}")
            
            self.progress_bar.setVisible(False)
            QMessageBox.information(self, 'Успех', f'Данные экспортированы в {file_name}\n(только видимые графики, абсолютные величины, все точки)')
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте в Excel: {str(e)}", exc_info=True)
            QMessageBox.critical(self, 'Ошибка', f'Не удалось экспортировать данные: {str(e)}')
            self.progress_bar.setVisible(False)