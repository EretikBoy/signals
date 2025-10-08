# gui/tree_widget.py

from PyQt6.QtWidgets import QTreeWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QDropEvent

from gui.tree_items import SubjectItem, AnalysisItem

import logging
logger = logging.getLogger(__name__)


class TreeWidget(QTreeWidget):
    """Кастомное дерево с поддержкой drag & drop между предметами"""
    
    analysis_moved = pyqtSignal(str, str, int)  # old_subject, new_subject, analysis_index
    
    def __init__(self):
        super().__init__()
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
    
    def dropEvent(self, event: QDropEvent):
        """Обработка события drop для перемещения анализов между предметами"""
        try:
            # Получаем источник и целевой элемент
            source_item = self.currentItem()
            
            # ИСПРАВЛЕНИЕ: используем position().toPoint() вместо pos() для PyQt6
            target_item = self.itemAt(event.position().toPoint())
            
            # Проверяем, что перетаскиваем анализ и бросаем на предмет
            if (isinstance(source_item, AnalysisItem) and 
                isinstance(target_item, SubjectItem)):
                
                old_subject = source_item.subject_code
                new_subject = target_item.subject_code
                analysis_index = source_item.analysis_index
                
                logger.debug(f"Перемещение анализа: {old_subject} -> {new_subject}, индекс: {analysis_index}")
                
                # Вызываем родительский метод для фактического перемещения в дереве
                super().dropEvent(event)
                
                # Испускаем сигнал о перемещении
                self.analysis_moved.emit(old_subject, new_subject, analysis_index)
            else:
                # Для других случаев используем стандартное поведение
                super().dropEvent(event)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке drop: {e}")
            super().dropEvent(event)