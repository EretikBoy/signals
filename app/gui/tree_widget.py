#gui/tree_widget.py

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

import logging
logger = logging.getLogger(__name__)


class TreeWidget(QTreeWidget):
    """Кастомное дерево с обработкой перетаскивания анализов между предметами"""
    
    analysis_moved = pyqtSignal(str, str, int)  # old_subject, new_subject, analysis_index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        
        # Для отслеживания перетаскиваемого элемента
        self.dragged_item = None
        self.dragged_subject = None
        self.dragged_analysis_index = None
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработка входа drag события"""
        logger.debug("Drag enter event")
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Обработка движения при drag"""
        logger.debug("Drag move event")
        # Разрешаем перетаскивание только анализов (дочерних элементов)
        item = self.itemAt(event.position().toPoint())
        if item and not item.parent():  # Разрешаем сброс на предметы (корневые элементы)
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def startDrag(self, supportedActions):
        """Начало перетаскивания - сохраняем информацию о перетаскиваемом элементе"""
        logger.debug("Start drag")
        items = self.selectedItems()
        if items and items[0].parent():  # Перетаскиваем только анализы (дочерние элементы)
            self.dragged_item = items[0]
            self.dragged_subject = self.dragged_item.parent().text(1)
            
            # Получаем analysis_index из данных элемента
            self.dragged_analysis_index = self.dragged_item.data(0, Qt.ItemDataRole.UserRole)
            logger.debug(f"Начато перетаскивание: {self.dragged_subject}, {self.dragged_analysis_index}")
            
        super().startDrag(supportedActions)
    
    def dropEvent(self, event: QDropEvent):
        """Обработка сброса элемента"""
        logger.debug("Drop event")
        if not self.dragged_item or self.dragged_analysis_index is None:
            logger.debug("Нет перетаскиваемого элемента")
            event.ignore()
            return
        
        # Получаем целевой предмет
        target_item = self.itemAt(event.position().toPoint())
        if not target_item or target_item.parent():
            # Сбрасываем только на предметы (корневые элементы)
            logger.debug("Сброс разрешен только на предметы")
            event.ignore()
            return
        
        new_subject = target_item.text(1)
        logger.debug(f"Целевой предмет: {new_subject}")
        
        if new_subject == self.dragged_subject:
            # Не перемещаем в тот же предмет
            logger.debug("Попытка переместить в тот же предмет")
            event.ignore()
            return
        
        # Перемещаем элемент
        old_parent = self.dragged_item.parent()
        new_parent = target_item
        
        logger.debug(f"Перемещение из {self.dragged_subject} в {new_subject}")
        
        # Удаляем из старого родителя
        old_parent.removeChild(self.dragged_item)
        
        # Добавляем к новому родителю
        new_parent.addChild(self.dragged_item)
        new_parent.setExpanded(True)
        
        # Обновляем отображение кода предмета в анализе (столбец 1)
        self.dragged_item.setText(1, "")  # Наследуется от родителя
        
        # Испускаем сигнал о перемещении
        self.analysis_moved.emit(self.dragged_subject, new_subject, self.dragged_analysis_index)
        logger.debug(f"Сигнал перемещения отправлен: {self.dragged_subject} -> {new_subject}, {self.dragged_analysis_index}")
        
        # Сбрасываем состояние
        self.dragged_item = None
        self.dragged_subject = None
        self.dragged_analysis_index = None
        
        event.acceptProposedAction()