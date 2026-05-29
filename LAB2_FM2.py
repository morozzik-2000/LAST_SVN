
import sys
import numpy as np
from scipy import signal
from PySide6.QtWidgets import *
from PySide6.QtCore import QThread, Signal, Qt
from PySide6 import QtWidgets, QtGui, QtCore
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QDialog
from scipy.signal import correlate
import math
from scipy.signal import welch, savgol_filter
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PySide6.QtWidgets import QToolButton


class CustomNavigationToolbar(NavigationToolbar):
    """Кастомный тулбар с дополнительной кнопкой-переключателем"""

    def __init__(self, canvas, parent, callback):
        super().__init__(canvas, parent)
        self.callback = callback
        self._add_mode_button()

    def _add_mode_button(self):
        """Добавляет кнопку-переключатель режима"""
        self.addSeparator()

        # Создаем кнопку-переключатель
        self.mode_button = QToolButton(self)
        self.mode_button.setText("📊 Импульсы")
        self.mode_button.setCheckable(True)
        self.mode_button.setChecked(True)
        self.mode_button.setToolTip("Переключить между отсчётами и ступеньками")
        self.mode_button.setStyleSheet("""
            QToolButton {
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border: none;
            }
            QToolButton:hover {
                background-color: #45a049;
            }
            QToolButton:pressed {
                background-color: #3d8b40;
            }
        """)

        self.mode_button.toggled.connect(self._on_mode_toggled)
        self.addWidget(self.mode_button)

    def _on_mode_toggled(self, checked):
        """Обработчик переключения режима"""
        if checked:
            self.mode_button.setText("📊 Импульсы")
        else:
            self.mode_button.setText("📈 Отсчёты")
        self.callback(checked)

class LegendWindow(QWidget):
    """Отдельное окно с легендой (без обводки)"""

    def __init__(self, legend_data, is_scatter_mode, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Легенда графиков")
        self.setWindowFlags(Qt.Tool)  # Всплывающее окно, не мешает основному
        self.setFixedWidth(280)
        self.setAttribute(Qt.WA_DeleteOnClose)  # Закрывается при закрытии

        # Убираем обводку у окна легенды
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: none;
            }
            QLabel {
                color: #333;
                font-size: 12px;
                background-color: transparent;
                border: none;
            }
        """)

        self.legend_data = legend_data
        self.is_scatter_mode = is_scatter_mode
        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)



        # Контейнер для элементов легенды
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(8)

        # Добавляем элементы
        self.add_legend_items()

        layout.addLayout(self.items_layout)
        layout.addStretch()

        self.setLayout(layout)

    def add_legend_items(self):
        """Добавляет элементы легенды без обводки"""
        # Очищаем существующие элементы
        for i in reversed(range(self.items_layout.count())):
            item = self.items_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        for name, color, plot_type in self.legend_data:
            item_widget = QWidget()
            # Убираем обводку у виджета элемента
            item_widget.setStyleSheet("border: none; background-color: transparent;")

            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(5, 2, 5, 2)
            item_layout.setSpacing(10)

            # Цветной индикатор (без обводки)
            indicator = QLabel()
            indicator.setFixedSize(24, 24)
            indicator.setStyleSheet("border: none; background-color: transparent;")

            # Создаем пиксельную карту для индикатора
            pixmap = QtGui.QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            if plot_type == 'scatter':
                # Только точка, без обводки
                painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))  # Убираем обводку
                painter.setBrush(QtGui.QBrush(QtGui.QColor(color)))
                painter.drawEllipse(8, 8, 8, 8)
            elif plot_type == 'step':
                # Ступенчатый график - только линия
                painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
                painter.setBrush(QtCore.Qt.NoBrush)
                # Рисуем линию (без точек)
                painter.drawLine(4, 12, 20, 12)
            else:  # line
                # Обычная линия
                painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawLine(4, 12, 20, 12)

            painter.end()
            indicator.setPixmap(pixmap)

            # Название графика (убираем лишние символы)
            clean_name = name

            name_label = QLabel(clean_name)
            name_label.setWordWrap(True)
            name_label.setStyleSheet("""
                color: #333;
                border: none;
                background-color: transparent;
                font-size: 12px;
            """)

            item_layout.addWidget(indicator)
            item_layout.addWidget(name_label, stretch=1)
            item_widget.setLayout(item_layout)

            self.items_layout.addWidget(item_widget)

    def update_legend(self, legend_data, is_scatter_mode):
        """Обновляет содержимое легенды"""
        self.legend_data = legend_data
        self.is_scatter_mode = is_scatter_mode
        self.add_legend_items()


class PlotTabWithCheckbox(QWidget):
    """Виджет графика с возможностью переключения между точками и ступеньками"""

    def __init__(self, title, xlabel="Время, с", ylabel=""):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Создаем фигуру
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        # Создаем кастомный тулбар
        self.toolbar = CustomNavigationToolbar(self.canvas, self, self._on_mode_changed)

        # Создаем ось
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title(title, fontsize=14)
        self.ax.set_xlabel(xlabel, fontsize=12)
        self.ax.set_ylabel(ylabel, fontsize=12)
        self.ax.grid(True, alpha=0.3)

        # Добавляем виджеты
        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)


        self.setLayout(layout)

        # Хранилище данных
        self.current_x = None
        self.current_y = None
        self.current_label = None
        self.is_scatter_mode = True

    def _on_mode_changed(self, is_scatter):
        """Обработчик изменения режима"""
        self.is_scatter_mode = is_scatter
        if self.current_x is not None and self.current_y is not None:
            self.update_plot(self.current_x, self.current_y, self.current_label)

    def update_plot(self, x, y, label=None):
        """Обновляет график в зависимости от режима отображения"""
        self.current_x = x
        self.current_y = y
        self.current_label = label

        self.ax.clear()
        self.ax.set_title(self.ax.get_title())
        self.ax.set_xlabel(self.ax.get_xlabel())
        self.ax.set_ylabel(self.ax.get_ylabel())
        self.ax.grid(True, alpha=0.3)

        if self.is_scatter_mode:
            # Точечный график (отсчеты)
            self.ax.scatter(x, y, color='red', s=40, marker='o', label=label, zorder=5)
        else:
            # Ступенчатый график (импульсы)
            self.ax.step(x, y, where='post', color='red', linewidth=1.5, label=label)

        if label:
            self.ax.legend(loc='best', fontsize=10)

        self.canvas.draw()

class SignalModeWidget(QWidget):
    """Виджет для выбора режима сигнала"""
    paramsChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Режим сигнала")
        group_layout = QVBoxLayout()

        self.signal_mode = QComboBox()
        self.signal_mode.addItems(["2ФМ сигнал", "Немодулированная несущая"])
        self.signal_mode.setStyleSheet("""
            QComboBox {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                border: 2px solid #aaa;
                border-radius: 8px;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
        """)

        # Пояснение
        info_label = QLabel(
            "ℹ️ 2ФМ сигнал: биполярная ПСП модулирует несущую\n"
            "Немодулированная несущая: только несущая частота (без модуляции)"
        )
        info_label.setStyleSheet("font-size: 11px; color: #666; margin-top: 5px;")
        info_label.setWordWrap(True)

        group_layout.addWidget(QLabel("Тип сигнала:"))
        group_layout.addWidget(self.signal_mode)
        group_layout.addWidget(info_label)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

        self.signal_mode.currentIndexChanged.connect(self.paramsChanged.emit)

    def is_modulated(self):
        """Возвращает True если выбран 2ФМ сигнал"""
        return self.signal_mode.currentIndex() == 0

    def get_mode(self):
        """Возвращает режим работы"""
        return 'bpsk' if self.signal_mode.currentIndex() == 0 else 'carrier'


class RangesTableWidget(QWidget):
    """Виджет с таблицей диапазонов параметров (автоматическое считывание)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        layout = QVBoxLayout()

        # Заголовок
        title = QLabel("Допустимые диапазоны параметров (текущие)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Поле поиска
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Поиск:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите параметр для поиска...")
        self.search_edit.textChanged.connect(self.filter_table)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Кнопка обновления
        refresh_btn = QPushButton("🔄 Обновить диапазоны")
        refresh_btn.clicked.connect(self.refresh_ranges)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)

        button_layout = QHBoxLayout()
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Создаем таблицу
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Параметр", "Минимум", "Максимум", "Текущее", "Единицы"])

        # ЗАПРЕЩАЕМ РЕДАКТИРОВАНИЕ - таблица только для просмотра
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Запрещаем выделение ячеек (опционально)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Настройка таблицы
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #dee2e6;
            }
            QTableWidget::item {
                padding: 10px;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                font-size: 14px;
            }
        """)

        # Настраиваем размеры
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 350)  # Параметр (увеличен)
        self.table.setColumnWidth(1, 100)  # Минимум
        self.table.setColumnWidth(2, 100)  # Максимум
        self.table.setColumnWidth(3, 100)  # Текущее
        self.table.setColumnWidth(4, 120)  # Единицы

        # Устанавливаем высоту строк
        self.table.verticalHeader().setDefaultSectionSize(40)

        layout.addWidget(self.table)

        # Добавляем информационную метку
        info_label = QLabel(
            "ℹ️ Примечание: Таблица только для просмотра. Для изменения параметров используйте соответствующие вкладки.\n"
            "Данные автоматически считываются из текущих настроек."
        )
        info_label.setStyleSheet("font-size: 11px; color: #666; margin-top: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.setLayout(layout)

        # Инициализируем таблицу
        self.refresh_ranges()

    def collect_all_ranges(self):
        """Собирает диапазоны из всех виджетов"""
        ranges = []

        # Получаем главное окно
        main_window = None
        parent = self.parent()
        while parent:
            if isinstance(parent, MainWindow):
                main_window = parent
                break
            parent = parent.parent()

        if not main_window:
            return ranges

        # 1. Системные параметры
        sys_params = main_window.global_params.system_params
        ranges.extend([
            ("Скорость передачи", sys_params.bits_per_second.minimum(),
             sys_params.bits_per_second.maximum(), sys_params.bits_per_second.value(), "бит/с"),
            ("Частота несущей", sys_params.Fc.minimum(),
             sys_params.Fc.maximum(), sys_params.Fc.value(), "Гц"),
            ("Длина реализации", sys_params.T.minimum(),
             sys_params.T.maximum(), sys_params.T.value(), "с"),
            ("Частота дискретизации", sys_params.Fs.minimum(),
             sys_params.Fs.maximum(), sys_params.Fs.value(), "Гц"),
        ])

        # 2. Параметры фильтра
        filter_params = main_window.global_params.filter_params
        ranges.extend([
            ("Полоса пропускания (нижняя)", filter_params.filter_band.Wp_low.minimum(),
             filter_params.filter_band.Wp_low.maximum(), filter_params.filter_band.Wp_low.value(), "Гц"),
            ("Полоса пропускания (верхняя)", filter_params.filter_band.Wp_high.minimum(),
             filter_params.filter_band.Wp_high.maximum(), filter_params.filter_band.Wp_high.value(), "Гц"),
            ("Полоса заграждения (нижняя)", filter_params.filter_band.Ws_low.minimum(),
             filter_params.filter_band.Ws_low.maximum(), filter_params.filter_band.Ws_low.value(), "Гц"),
            ("Полоса заграждения (верхняя)", filter_params.filter_band.Ws_high.minimum(),
             filter_params.filter_band.Ws_high.maximum(), filter_params.filter_band.Ws_high.value(), "Гц"),
            ("Пульсации в полосе пропускания", filter_params.filter_params.gpass.minimum(),
             filter_params.filter_params.gpass.maximum(), filter_params.filter_params.gpass.value(), "дБ"),
            ("Затухание в полосе заграждения", filter_params.filter_params.gstop.minimum(),
             filter_params.filter_params.gstop.maximum(), filter_params.filter_params.gstop.value(), "дБ"),
            ("Порядок фильтра", filter_params.filter_settings.filter_order.minimum(),
             filter_params.filter_settings.filter_order.maximum(),
             filter_params.filter_settings.filter_order.value(), ""),
        ])

        # 3. Параметры СВН
        pll_params = main_window.global_params.pll_params
        ranges.extend([
            ("Коэф. усиления ФНЧ в СВН", pll_params.Gp.minimum(),
             pll_params.Gp.maximum(), pll_params.Gp.value(), ""),
            ("Постоянная времени ФНЧ в СВН", pll_params.T_lf.minimum(),
             pll_params.T_lf.maximum(), pll_params.T_lf.value(), "с"),
            ("Крутизна ГУН", pll_params.Sr.minimum(),
             pll_params.Sr.maximum(), pll_params.Sr.value(), "Гц/В"),
            ("Фазовая задержка", pll_params.delay_deg.minimum(),
             pll_params.delay_deg.maximum(), pll_params.delay_deg.value(), "град."),
        ])

        # 4. Параметры шума
        channel_params = main_window.global_params.channel_params
        ranges.extend([
            ("Eb/N0", channel_params.ebn0.minimum(),
             channel_params.ebn0.maximum(), channel_params.ebn0.value(), "дБ"),
        ])

        # 5. Параметры части 3
        if hasattr(main_window, 'dphi'):
            ranges.extend([
                ("Фазовый сдвиг Δφ (ч.3)", main_window.dphi.minimum(),
                 main_window.dphi.maximum(), main_window.dphi.value(), "град."),
            ])

        # 6. Параметры части 4
        if hasattr(main_window, 'freq_offset'):
            ranges.extend([
                ("Частотная расстройка Δf (ч.4)", main_window.freq_offset.minimum(),
                 main_window.freq_offset.maximum(), main_window.freq_offset.value(), "Гц"),
            ])

        # 7. Параметры переходного процесса
        if hasattr(main_window, 'transition'):
            ranges.extend([
                ("Переходный процесс (ч.3)", main_window.transition.minimum(),
                 main_window.transition.maximum(), main_window.transition.value(), "с"),
            ])

        if hasattr(main_window, 'transition4'):
            ranges.extend([
                ("Переходный процесс (ч.4)", main_window.transition4.minimum(),
                 main_window.transition4.maximum(), main_window.transition4.value(), "с"),
            ])

        # 8. Параметры части 5
        if hasattr(main_window, 'phase_min'):
            ranges.extend([
                ("Фаза от (ч.5)", main_window.phase_min.minimum(),
                 main_window.phase_min.maximum(), main_window.phase_min.value(), "град."),
                ("Фаза до (ч.5)", main_window.phase_max.minimum(),
                 main_window.phase_max.maximum(), main_window.phase_max.value(), "град."),
                ("Шаг фазы (ч.5)", main_window.phase_step.minimum(),
                 main_window.phase_step.maximum(), main_window.phase_step.value(), "град."),
            ])

        return ranges

    def refresh_ranges(self):
        """Обновляет таблицу с текущими диапазонами"""
        ranges = self.collect_all_ranges()

        self.table.setRowCount(len(ranges))

        # Создаем шрифт для всех ячеек (увеличенный)
        cell_font = QtGui.QFont()
        cell_font.setPointSize(14)  # Увеличенный размер шрифта
        cell_font.setFamily("Segoe UI")  # Современный шрифт

        # Шрифт для параметров (жирный)
        param_font = QtGui.QFont()
        param_font.setPointSize(12)
        param_font.setFamily("Segoe UI")
        param_font.setBold(True)

        for row, (param_name, min_val, max_val, current_val, unit) in enumerate(ranges):
            # Параметр (жирный шрифт)
            param_item = QTableWidgetItem(param_name)
            param_item.setFont(param_font)
            self.table.setItem(row, 0, param_item)

            # Минимум
            min_item = QTableWidgetItem(self._format_value(min_val))
            min_item.setFont(cell_font)
            min_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, min_item)

            # Максимум
            max_item = QTableWidgetItem(self._format_value(max_val))
            max_item.setFont(cell_font)
            max_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, max_item)

            # Текущее значение
            current_item = QTableWidgetItem(self._format_value(current_val))
            current_item.setFont(cell_font)
            current_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Выделяем текущее значение цветом
            current_item.setBackground(QtGui.QColor(224, 247, 250))  # Светло-голубой
            self.table.setItem(row, 3, current_item)

            # Единицы
            unit_item = QTableWidgetItem(unit)
            unit_item.setFont(cell_font)
            unit_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 4, unit_item)

        # Сортируем по первому столбцу
        self.table.sortItems(0)

    def _format_value(self, value):
        """Форматирует значение для отображения"""
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            else:
                return f"{value:.3f}".rstrip('0').rstrip('.')
        return str(value)

    def filter_table(self, text):
        """Фильтрует таблицу по тексту поиска"""
        for row in range(self.table.rowCount()):
            param_item = self.table.item(row, 0)
            if param_item:
                show_row = text.lower() in param_item.text().lower()
                self.table.setRowHidden(row, not show_row)

class OverlayGraphDialog(QDialog):
    """Диалог для выбора графиков для наложения"""

    def __init__(self, graph_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Совмещение графиков")
        self.resize(500, 600)
        self.graph_items = graph_items

        layout = QVBoxLayout(self)

        instruction = QLabel("Выберите графики для наложения (2 и более):")
        instruction.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold))
        layout.addWidget(instruction)

        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        self.checkboxes = []
        for name, data_func in graph_items:
            cb = QCheckBox(name)
            cb.data_func = data_func
            scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)

        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        btn_layout = QHBoxLayout()

        btn_deselect_all = QPushButton("Снять все")
        btn_deselect_all.clicked.connect(self._deselect_all)

        btn_plot = QPushButton("Построить наложение")
        btn_plot.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        btn_plot.clicked.connect(self.accept)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_deselect_all)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_plot)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _deselect_all(self):
        for cb in self.checkboxes:
            cb.setChecked(False)

    def get_selected_graphs(self):
        selected = []
        for cb in self.checkboxes:
            if cb.isChecked():
                data = cb.data_func()
                if data is not None:
                    selected.append(data)
        return selected
# ==== НОВЫЕ КЛАССЫ ДЛЯ ПАРАМЕТРОВ ====

class ChannelParamsWidget(QWidget):
    """Виджет для параметров канала (шум)"""
    paramsChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Канал")
        grid = QGridLayout()

        # Создаем чекбокс
        self.noise = QCheckBox()


        self.ebn0 = QDoubleSpinBox()
        self.ebn0.setRange(-10, 10)
        self.ebn0.setValue(30)
        self.ebn0.setDecimals(1)
        self.ebn0.setSuffix(" дБ")
        self.ebn0.setToolTip("Отношение сигнал/шум на бит (Eb/N0)")

        # Строка с надписью "Добавить шум" и чекбоксом справа
        grid.addWidget(QLabel("Добавить шум:"), 0, 0)  # Текст
        grid.addWidget(self.noise, 0, 1)  # Чекбокс справа от текста

        # Создаем дробь с горизонтальной чертой и двоеточием посередине
        fraction_label = QLabel()
        fraction_label.setTextFormat(QtCore.Qt.RichText)
        fraction_label.setText("""
        <table border="0" cellpadding="0" cellspacing="0">
            <tr>
                <td align="center" style="vertical-align: middle;">E<sub>b</sub></td>
                <td rowspan="3" style="vertical-align: middle; padding-left: 2px;">:</td>
            </tr>
            <tr>
                <td align="center"><hr style="margin:0; padding:0; height:2px; background-color:black;"></td>
            </tr>
            <tr>
                <td align="center">N<sub>0</sub></td>
            </tr>
        </table>
        """)
        grid.addWidget(fraction_label, 1, 0)
        grid.addWidget(self.ebn0, 1, 1)

        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)
        self.noise.stateChanged.connect(self.paramsChanged.emit)
        self.ebn0.valueChanged.connect(self.paramsChanged.emit)

    def on_noise_mode_changed(self, index):
        """Переключение между режимами задания шума"""
        self.ebn0.setEnabled(True)

    def get_noise_params(self):
        """Возвращает параметры шума"""
        if not self.noise.isChecked():
            return {'add_noise': False, 'mode': None, 'value': None}

        mode = 'ebn0'
        value = self.ebn0.value()
        return {'add_noise': True, 'mode': mode, 'value': value}


class SystemParamsWidget(QWidget):
    """Виджет для системных параметров"""
    paramsChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Системные параметры")
        grid = QGridLayout()

        self.Fs = QDoubleSpinBox()
        self.Fs.setRange(1000, 100000)
        self.Fs.setValue(20000)
        self.Fs.setDecimals(0)
        # self.Fs.setSuffix(" Гц")

        self.Fc = QDoubleSpinBox()
        self.Fc.setRange(100, 5000)
        self.Fc.setValue(1000)
        self.Fc.setDecimals(0)
        # self.Fc.setSuffix(" Гц")

        self.bits_per_second = QDoubleSpinBox()
        self.bits_per_second.setRange(1, 1000)
        self.bits_per_second.setValue(50)
        self.bits_per_second.setDecimals(0)
        # self.bits_per_second.setSuffix(" бит/с")

        self.T = QDoubleSpinBox()
        self.T.setRange(0.1, 10000)
        self.T.setValue(10)
        self.T.setDecimals(0)
        # self.T.setSuffix(" с")

        grid.addWidget(QLabel("Скорость передачи, бит/с:"), 0, 0)
        grid.addWidget(self.bits_per_second, 0, 1)
        grid.addWidget(QLabel("Частота несущей, Гц:"), 2, 0)
        grid.addWidget(self.Fc, 2, 1)
        grid.addWidget(QLabel("Длина реализации, c:"), 3, 0)
        grid.addWidget(self.T, 3, 1)
        grid.addWidget(QLabel("Частота дискретизации, Гц:"), 4, 0)
        grid.addWidget(self.Fs, 4, 1)

        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

        # В конце __init__ метода SystemParamsWidget добавьте:
        self.Fs.valueChanged.connect(self.paramsChanged.emit)
        self.Fc.valueChanged.connect(self.paramsChanged.emit)
        self.bits_per_second.valueChanged.connect(self.paramsChanged.emit)
        self.T.valueChanged.connect(self.paramsChanged.emit)


class FilterBandWidget(QWidget):
    """Виджет для полос фильтра"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        band_group = QGroupBox("Полоса пропускания/заграждения (Гц)")
        band_layout = QGridLayout()

        self.Wp_low = QDoubleSpinBox()
        self.Wp_low.setRange(0, 10000)
        self.Wp_low.setValue(900)
        # self.Wp_low.setSuffix(" Гц")
        self.Wp_low.setDecimals(0)

        self.Wp_high = QDoubleSpinBox()
        self.Wp_high.setRange(0, 10000)
        self.Wp_high.setValue(1100)
        # self.Wp_high.setSuffix(" Гц")
        self.Wp_high.setDecimals(0)

        self.Ws_low = QDoubleSpinBox()
        self.Ws_low.setRange(0, 10000)
        self.Ws_low.setValue(800)
        # self.Ws_low.setSuffix(" Гц")
        self.Ws_low.setDecimals(0)

        self.Ws_high = QDoubleSpinBox()
        self.Ws_high.setRange(0, 10000)
        self.Ws_high.setValue(1200)
        # self.Ws_high.setSuffix(" Гц")
        self.Ws_high.setDecimals(0)

        band_layout.addWidget(QLabel("Полоса пропускания (нижняя), Гц:"), 0, 0)
        band_layout.addWidget(self.Wp_low, 0, 1)
        band_layout.addWidget(QLabel("Полоса пропускания (верхняя), Гц:"), 1, 0)
        band_layout.addWidget(self.Wp_high, 1, 1)
        band_layout.addWidget(QLabel("Полоса заграждения (нижняя), Гц:"), 2, 0)
        band_layout.addWidget(self.Ws_low, 2, 1)
        band_layout.addWidget(QLabel("Полоса заграждения (верхняя), Гц:"), 3, 0)
        band_layout.addWidget(self.Ws_high, 3, 1)

        band_group.setLayout(band_layout)
        layout.addWidget(band_group)
        layout.addStretch()
        self.setLayout(layout)


class FilterParamsWidget(QWidget):
    """Виджет для параметров фильтра (пульсации и затухание)"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        params_group = QGroupBox("Характеристики фильтра")
        params_layout = QGridLayout()

        self.gpass = QDoubleSpinBox()
        self.gpass.setRange(0.1, 10)
        self.gpass.setValue(1)
        self.gpass.setSingleStep(0.1)
        # self.gpass.setSuffix(" дБ")
        self.gpass.setDecimals(0)

        self.gstop = QDoubleSpinBox()
        self.gstop.setRange(10, 100)
        self.gstop.setValue(40)
        self.gstop.setSingleStep(5)
        # self.gstop.setSuffix(" дБ")
        self.gstop.setDecimals(0)

        params_layout.addWidget(QLabel("Пульсации в полосе пропускания, дБ:"), 0, 0)
        params_layout.addWidget(self.gpass, 0, 1)
        params_layout.addWidget(QLabel("Затухание в полосе заграждения, дБ:"), 1, 0)
        params_layout.addWidget(self.gstop, 1, 1)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        layout.addStretch()
        self.setLayout(layout)


class FilterSettingsWidget(QWidget):
    """Виджет для настроек фильтра (тип и порядок)"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        filter_settings_group = QGroupBox("Настройки фильтра")
        filter_settings_layout = QVBoxLayout()

        self.filter_type = QComboBox()
        self.filter_type.addItems(["ellip", "butter", "cheby1", "cheby2", "bessel"])

        self.order_mode = QComboBox()
        self.order_mode.addItems(["Ручной (задать порядок)", "Автоматический (по требованиям)"])  # Ручной по умолчанию
        self.order_mode.currentIndexChanged.connect(self.on_order_mode_changed)

        self.filter_order = QSpinBox()
        self.filter_order.setRange(1, 20)
        self.filter_order.setValue(4)
        self.filter_order.setEnabled(True)  # При ручном режиме включен

        filter_settings_layout.addWidget(QLabel("Тип фильтра:"))
        filter_settings_layout.addWidget(self.filter_type)
        filter_settings_layout.addWidget(QLabel("Режим определения порядка:"))
        filter_settings_layout.addWidget(self.order_mode)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Порядок фильтра:"))
        order_row.addWidget(self.filter_order)
        order_row.addStretch()
        filter_settings_layout.addLayout(order_row)
        filter_settings_layout.addStretch()

        filter_settings_group.setLayout(filter_settings_layout)
        layout.addWidget(filter_settings_group)
        layout.addStretch()
        self.setLayout(layout)

    def on_order_mode_changed(self, index):
        is_manual = (index == 0)  # 0 - ручной, 1 - автоматический
        self.filter_order.setEnabled(is_manual)


class FilterCombinedWidget(QWidget):
    """Объединенный виджет для всех параметров фильтра"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # Полосы фильтра
        self.filter_band = FilterBandWidget()
        layout.addWidget(self.filter_band)

        # Характеристики фильтра
        self.filter_params = FilterParamsWidget()
        layout.addWidget(self.filter_params)

        # Настройки фильтра
        self.filter_settings = FilterSettingsWidget()
        layout.addWidget(self.filter_settings)

        layout.addStretch()
        self.setLayout(layout)

        # Подключаем сигнал изменения режима для блокировки полей
        self.filter_settings.order_mode.currentIndexChanged.connect(self.on_order_mode_changed)
        # Инициализируем состояние
        self.on_order_mode_changed(self.filter_settings.order_mode.currentIndex())

    def on_order_mode_changed(self, index):
        """При изменении режима блокируем/разблокируем характеристики фильтра"""
        is_manual = (index == 0)  # 0 - ручной, 1 - автоматический

        # При автоматическом режиме блокируем пульсации и затухание
        self.filter_params.gpass.setEnabled(is_manual)
        self.filter_params.gstop.setEnabled(is_manual)

    def get_filter_params(self):
        return {
            'type': self.filter_settings.filter_type.currentText(),
            'order_mode': self.filter_settings.order_mode.currentIndex(),
            'order': self.filter_settings.filter_order.value(),
            'Wp_low': self.filter_band.Wp_low.value(),
            'Wp_high': self.filter_band.Wp_high.value(),
            'Ws_low': self.filter_band.Ws_low.value(),
            'Ws_high': self.filter_band.Ws_high.value(),
            'gpass': self.filter_params.gpass.value(),
            'gstop': self.filter_params.gstop.value()
        }

    def set_filter_params_enabled(self, enabled):
        """Включить/выключить параметры фильтра в зависимости от ручного режима"""
        is_manual = (self.filter_settings.order_mode.currentIndex() == 0)
        self.filter_params.gpass.setEnabled(is_manual and enabled)
        self.filter_params.gstop.setEnabled(is_manual and enabled)


class PLLParamsWidget(QWidget):
    """Виджет для параметров PLL (ФАПЧ)"""
    paramsChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        group = QGroupBox("Параметры СВН")
        grid = QGridLayout()

        self.Gp = QDoubleSpinBox()
        self.Gp.setRange(0.1, 10)
        self.Gp.setValue(1)
        self.Gp.setSingleStep(0.1)
        self.Gp.setDecimals(0)

        self.Sr = QDoubleSpinBox()
        self.Sr.setRange(1, 100)
        self.Sr.setValue(10)
        self.Sr.setSingleStep(1)
        self.Sr.setDecimals(0)
        # self.Sr.setSuffix(" Гц/В")

        self.T_lf = QDoubleSpinBox()
        self.T_lf.setRange(0.001, 1)
        self.T_lf.setValue(0.01)
        self.T_lf.setSingleStep(0.001)
        self.T_lf.setDecimals(2)
        # self.T_lf.setSuffix(" с")

        self.delay_deg = QDoubleSpinBox()
        self.delay_deg.setRange(0, 180)
        self.delay_deg.setValue(42)
        self.delay_deg.setDecimals(0)
        # self.delay_deg.setSuffix(" °")

        grid.addWidget(QLabel("Коэф. усиления ФНЧ в СВН:"), 0, 0)
        grid.addWidget(self.Gp, 0, 1)
        grid.addWidget(QLabel("Постоянная времени ФНЧ в СВН, c:"), 1, 0)
        grid.addWidget(self.T_lf, 1, 1)
        grid.addWidget(QLabel("Крутизна ГУН, Гц/В:"), 2, 0)
        grid.addWidget(self.Sr, 2, 1)
        grid.addWidget(QLabel("Фазовая задержка, град.:"), 3, 0)
        grid.addWidget(self.delay_deg, 3, 1)

        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

        self.Gp.valueChanged.connect(self.paramsChanged.emit)
        self.Sr.valueChanged.connect(self.paramsChanged.emit)
        self.T_lf.valueChanged.connect(self.paramsChanged.emit)
        self.delay_deg.valueChanged.connect(self.paramsChanged.emit)


class Worker(QThread):
    finished = Signal(dict)

    def __init__(self, T, Fs, Fc, bits_per_second,
                 filter_type, order_mode, filter_order,
                 Wp_low, Wp_high, Ws_low, Ws_high,
                 gpass, gstop, Gp, Sr, T_lf, delay_deg,
                 noise_params, carrier_only):
        super().__init__()
        self.T = T
        self.Fs = Fs
        self.Fc = Fc
        self.bits_per_second = bits_per_second
        self.filter_type = filter_type
        self.order_mode = order_mode
        self.filter_order = filter_order
        self.Wp_low = Wp_low
        self.Wp_high = Wp_high
        self.Ws_low = Ws_low
        self.Ws_high = Ws_high
        self.gpass = gpass
        self.gstop = gstop
        self.Gp = Gp
        self.Sr = Sr
        self.T_lf = T_lf
        self.delay_deg = delay_deg
        self.noise_params = noise_params
        self.carrier_only = carrier_only

    def run(self):
        Ts = 1 / self.Fs
        t = np.arange(0, self.T, Ts)

        num_bits = int(self.T * self.bits_per_second)

        # === ПСП ===
        bits = np.random.randint(0, 2, num_bits)
        bits = np.where(bits == 0, -1, 1)
        psp = np.repeat(bits, int(self.Fs / self.bits_per_second))[:len(t)]

        # === BPSK ===
        if self.carrier_only:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t)
        else:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t + (psp + 1) / 2 * np.pi)

        # === ШУМ ===
        if self.noise_params['add_noise']:
            P = np.mean(signal_bpsk ** 2)

            if self.noise_params['mode'] == 'ebn0':
                SNR = self.noise_params['value'] + 10 * np.log10(self.bits_per_second / (self.Fs / 2))
            else:
                SNR = self.noise_params['value']

            noise_power = P / (10 ** (SNR / 10))
            noise = np.sqrt(noise_power) * np.random.randn(len(t))
            noisy = signal_bpsk + noise
        else:
            noisy = signal_bpsk

        # === ФИЛЬТР ===
        Wp_norm = [self.Wp_low / (self.Fs / 2), self.Wp_high / (self.Fs / 2)]
        Ws_norm = [self.Ws_low / (self.Fs / 2), self.Ws_high / (self.Fs / 2)]

        if self.order_mode == 1:
            N = self.filter_order
            Wn = Wp_norm

            if self.filter_type == "ellip":
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')
        else:
            if self.filter_type == "ellip":
                N, Wn = signal.ellipord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                N, Wn = signal.cheby1ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                N, Wn = signal.cheby2ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')

        filtered = signal.lfilter(b, a, noisy)

        # === PLL ===
        F_vco = self.Fc
        delay = np.deg2rad(self.delay_deg) / np.pi

        VCO_cos = np.cos(2 * np.pi * F_vco * t - delay)
        VCO_sin = np.sin(2 * np.pi * F_vco * t - delay)

        phase_diskr = np.zeros(len(t))
        uf = np.zeros(len(t) + 1)
        est_phase_VCO = np.zeros(len(t) + 2)
        lpf_cos = np.zeros(len(t) + 1)
        lpf_sin = np.zeros(len(t) + 1)

        d_lf = Ts / self.T_lf
        freq_VCO = np.zeros(len(t) + 1)

        for i in range(len(t) - 1):
            mul_cos = filtered[i] * VCO_cos[i]
            mul_sin = filtered[i] * VCO_sin[i]

            lpf_cos[i + 1] = mul_cos * d_lf + lpf_cos[i] * (1 - d_lf)
            lpf_sin[i + 1] = mul_sin * d_lf + lpf_sin[i] * (1 - d_lf)

            phase_diskr[i] = lpf_cos[i] * lpf_sin[i]

            if i > 0:
                uf[i + 1] = uf[i] + self.Gp * phase_diskr[i] - (self.Gp - Ts) * phase_diskr[i - 1]
            else:
                uf[i + 1] = uf[i] + self.Gp * phase_diskr[i]

            freq_VCO[i + 1] = self.Sr * uf[i + 1]
            est_phase_VCO[i + 2] = est_phase_VCO[i + 1] + Ts * freq_VCO[i + 1]

            arg = F_vco * t[i + 1] + est_phase_VCO[i + 1] + delay
            VCO_cos[i + 1] = np.cos(2 * np.pi * arg)
            VCO_sin[i + 1] = np.sin(2 * np.pi * arg)

        demodulated_signal = lpf_cos[:-1] - lpf_sin[:-1]

        # ========== УПРОЩЕННЫЙ ПОДХОД (работает гарантированно) ==========
        samples_per_bit = int(self.Fs / self.bits_per_second)

        # 1. Сначала timing recovery на исходном сигнале
        nbits_total = len(demodulated_signal) // samples_per_bit

        best_offset = 0
        best_metric = -np.inf
        for offset in range(samples_per_bit):
            metric = 0
            for k in range(nbits_total):
                idx = offset + k * samples_per_bit
                if idx < len(demodulated_signal):
                    metric += abs(demodulated_signal[idx])
            if metric > best_metric:
                best_metric = metric
                best_offset = offset

        # 2. Декодирование с найденным offset
        recovered_raw = np.zeros(nbits_total)
        for k in range(nbits_total):
            idx = best_offset + k * samples_per_bit
            if idx < len(demodulated_signal):
                recovered_raw[k] = 1 if demodulated_signal[idx] > 0 else -1

        # 3. Выравнивание через корреляцию (ОСТАВИТЬ - это ВАЖНО!)
        psp_bits_full = bits[:nbits_total]
        corr = np.correlate(recovered_raw, psp_bits_full, mode='full')
        shift = np.argmax(np.abs(corr)) - len(psp_bits_full) + 1

        if shift > 0:
            recovered = recovered_raw[shift:]
            psp_bits = psp_bits_full[:len(recovered)]
        elif shift < 0:
            recovered = recovered_raw[:shift]
            psp_bits = psp_bits_full[-shift:]
        else:
            recovered = recovered_raw
            psp_bits = psp_bits_full

        # 4. Расчет BER (БЕЗ автокомпенсации инверсии)
        if len(recovered) > 0 and len(psp_bits) > 0:
            min_len = min(len(recovered), len(psp_bits))
            recovered = recovered[:min_len]
            psp_bits = psp_bits[:min_len]
            errors = np.sum(recovered != psp_bits)
            ber = errors / min_len
        else:
            errors = 0
            ber = 1.0

        # Время для восстановленной ПСП
        t_rec = np.arange(len(psp_bits)) / self.bits_per_second

        # === Спектры ===
        f1, pxx1 = signal.periodogram(noisy, self.Fs)
        f2, pxx2 = signal.periodogram(filtered, self.Fs)

        self.finished.emit({
            "t": t,
            "psp": psp,
            "bpsk": signal_bpsk,
            "noisy": noisy,
            "filtered": filtered,
            "f1": f1,
            "pxx1": pxx1,
            "f2": f2,
            "pxx2": pxx2,
            "t_rec": t_rec,
            "rec": recovered,
            "psp_bits": psp_bits,
            "errors": errors,
            "ber": ber
        })

class WorkerPart2(QThread):
    finished = Signal(dict)

    def __init__(self, T, Fs, Fc, bits_per_second, noise_params,
                 filter_type, order_mode, filter_order,
                 Wp_low, Wp_high, Ws_low, Ws_high,
                 gpass, gstop, Gp, Sr, T_lf, delay_deg, carrier_only):
        super().__init__()
        self.T = T
        self.Fs = Fs
        self.Fc = Fc
        self.bits_per_second = bits_per_second
        self.noise_params = noise_params
        self.filter_type = filter_type
        self.order_mode = order_mode
        self.filter_order = filter_order
        self.Wp_low = Wp_low
        self.Wp_high = Wp_high
        self.Ws_low = Ws_low
        self.Ws_high = Ws_high
        self.gpass = gpass
        self.gstop = gstop
        self.Gp = Gp
        self.Sr = Sr
        self.T_lf = T_lf
        self.delay_deg = delay_deg
        self.carrier_only = carrier_only

    def run(self):
        Ts = 1 / self.Fs
        t = np.arange(0, self.T, Ts)

        num_bits = int(self.T * self.bits_per_second)

        bits = np.random.randint(0, 2, num_bits)
        bits = np.where(bits == 0, -1, 1)
        psp = np.repeat(bits, int(self.Fs / self.bits_per_second))[:len(t)]

        # Напишите:
        if self.carrier_only:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t)  # Чистая несущая
        else:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t + (psp + 1) / 2 * np.pi)

        if self.noise_params['add_noise']:
            P = np.mean(signal_bpsk ** 2)

            if self.noise_params['mode'] == 'ebn0':
                SNR = self.noise_params['value'] + 10 * np.log10(self.bits_per_second / (self.Fs / 2))
            else:
                SNR = self.noise_params['value']

            noise_power = P / (10 ** (SNR / 10))
            noise = np.sqrt(noise_power) * np.random.randn(len(t))
            noisy = signal_bpsk + noise
        else:
            noisy = signal_bpsk

        # === ФИЛЬТР (используем параметры из глобальных) ===
        Wp_norm = [self.Wp_low / (self.Fs / 2), self.Wp_high / (self.Fs / 2)]
        Ws_norm = [self.Ws_low / (self.Fs / 2), self.Ws_high / (self.Fs / 2)]

        if self.order_mode == 1:
            N = self.filter_order
            Wn = Wp_norm

            if self.filter_type == "ellip":
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')
        else:
            if self.filter_type == "ellip":
                N, Wn = signal.ellipord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                N, Wn = signal.cheby1ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                N, Wn = signal.cheby2ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')

        filtered = signal.lfilter(b, a, noisy)

        # === PLL ===
        Gp, Sr, T_lf = self.Gp, self.Sr, self.T_lf
        F_vco, delay = self.Fc, np.deg2rad(self.delay_deg) / np.pi

        VCO_cos = np.cos(2 * np.pi * F_vco * t - delay)
        VCO_sin = np.sin(2 * np.pi * F_vco * t - delay)

        mul_cos = np.zeros(len(t))
        mul_sin = np.zeros(len(t))
        lpf_cos = np.zeros(len(t) + 1)
        lpf_sin = np.zeros(len(t) + 1)
        phase = np.zeros(len(t))
        uf = np.zeros(len(t) + 1)
        est = np.zeros(len(t) + 2)

        d_lf = Ts / T_lf
        freq = np.zeros(len(t) + 1)

        for i in range(len(t) - 1):
            mul_cos[i] = filtered[i] * VCO_cos[i]
            mul_sin[i] = filtered[i] * VCO_sin[i]

            lpf_cos[i + 1] = mul_cos[i] * d_lf + lpf_cos[i] * (1 - d_lf)
            lpf_sin[i + 1] = mul_sin[i] * d_lf + lpf_sin[i] * (1 - d_lf)

            phase[i] = lpf_cos[i] * lpf_sin[i]

            if i > 0:
                uf[i + 1] = uf[i] + Gp * phase[i] - (Gp - Ts) * phase[i - 1]
            else:
                uf[i + 1] = uf[i] + Gp * phase[i]

            freq[i + 1] = Sr * uf[i + 1]
            est[i + 2] = est[i + 1] + Ts * freq[i + 1]

            arg = F_vco * t[i + 1] + est[i + 1] + delay
            VCO_cos[i + 1] = np.cos(2 * np.pi * arg)
            VCO_sin[i + 1] = np.sin(2 * np.pi * arg)

        f_mul_cos, pxx_mul_cos = signal.periodogram(mul_cos, self.Fs)
        f_mul_sin, pxx_mul_sin = signal.periodogram(mul_sin, self.Fs)
        f_lpf_cos, pxx_lpf_cos = signal.periodogram(lpf_cos[:-1], self.Fs)
        f_lpf_sin, pxx_lpf_sin = signal.periodogram(lpf_sin[:-1], self.Fs)

        # === ДЕМОДУЛЯЦИЯ ===
        demod_signal = lpf_cos[:-1] - lpf_sin[:-1]

        # ========== НОВЫЙ БЛОК - ТАКОЙ ЖЕ КАК В ЧАСТИ 1 ==========
        samples_per_bit = int(self.Fs / self.bits_per_second)

        # 1. Timing recovery (поиск оптимального offset)
        nbits_total = len(demod_signal) // samples_per_bit

        best_offset = 0
        best_metric = -np.inf
        for offset in range(samples_per_bit):
            metric = 0
            for k in range(nbits_total):
                idx = offset + k * samples_per_bit
                if idx < len(demod_signal):
                    metric += abs(demod_signal[idx])
            if metric > best_metric:
                best_metric = metric
                best_offset = offset

        # 2. Декодирование с найденным offset
        recovered_raw = np.zeros(nbits_total)
        for k in range(nbits_total):
            idx = best_offset + k * samples_per_bit
            if idx < len(demod_signal):
                recovered_raw[k] = 1 if demod_signal[idx] > 0 else -1

        # 3. Выравнивание через корреляцию (компенсация задержки)
        psp_bits_full = bits[:nbits_total]
        corr = np.correlate(recovered_raw, psp_bits_full, mode='full')
        shift = np.argmax(np.abs(corr)) - len(psp_bits_full) + 1

        # Компенсируем сдвиг
        if shift > 0:
            recovered = recovered_raw[shift:]
            psp_bits = psp_bits_full[:len(recovered)]
        elif shift < 0:
            shift_abs = -shift
            recovered = recovered_raw[:-shift_abs] if shift_abs > 0 else recovered_raw
            psp_bits = psp_bits_full[shift_abs:]
        else:
            recovered = recovered_raw
            psp_bits = psp_bits_full

        # 4. Расчет BER
        if len(recovered) > 0 and len(psp_bits) > 0:
            min_len = min(len(recovered), len(psp_bits))
            recovered = recovered[:min_len]
            psp_bits = psp_bits[:min_len]
            errors = np.sum(recovered != psp_bits)
            ber = errors / min_len if min_len > 0 else 1.0
        else:
            errors = 0
            ber = 1.0

        # Время для восстановленной ПСП
        t_rec = np.arange(len(psp_bits)) / self.bits_per_second
        # ========================================================

        self.finished.emit({
            "t": t,
            "psp": psp,
            "phase": phase,
            "mul_cos": mul_cos,
            "mul_sin": mul_sin,
            "lpf_cos": lpf_cos[:-1],
            "lpf_sin": lpf_sin[:-1],
            "f_mul_cos": f_mul_cos,
            "pxx_mul_cos": pxx_mul_cos,
            "f_mul_sin": f_mul_sin,
            "pxx_mul_sin": pxx_mul_sin,
            "f_lpf_cos": f_lpf_cos,
            "pxx_lpf_cos": pxx_lpf_cos,
            "f_lpf_sin": f_lpf_sin,
            "pxx_lpf_sin": pxx_lpf_sin,
            "t_rec": t_rec,
            "rec": recovered,
            "psp_bits": psp_bits,
            "errors": errors,
            "ber": ber
        })


def cospi(x):
    return np.cos(np.pi * x)


def sinpi(x):
    return np.sin(np.pi * x)


class WorkerPart3(QThread):
    finished = Signal(dict)
    psd_ready = Signal(dict)

    def __init__(self, T, Fs, Fc, bits_per_second,
                 filter_type, order_mode, filter_order,
                 Wp_low, Wp_high, Ws_low, Ws_high,
                 gpass, gstop, Gp, Sr, T_lf, delay_deg,
                 noise_params, dphi, carrier_only):
        super().__init__()
        self.T = T
        self.Fs = Fs
        self.Fc = Fc
        self.bits_per_second = bits_per_second
        self.filter_type = filter_type
        self.order_mode = order_mode
        self.filter_order = filter_order
        self.Wp_low = Wp_low
        self.Wp_high = Wp_high
        self.Ws_low = Ws_low
        self.Ws_high = Ws_high
        self.gpass = gpass
        self.gstop = gstop
        self.Gp = Gp
        self.Sr = Sr
        self.T_lf = T_lf
        self.delay_deg = delay_deg
        self.noise_params = noise_params
        self.dphi = dphi
        self.last_VCO_out = None
        self.last_Fs = None
        self.carrier_only = carrier_only

    def run(self):
        Ts = 1 / self.Fs
        t = np.arange(0, self.T, Ts)

        num_bits = int(self.T * self.bits_per_second)

        # === ПСП ===
        bits = np.random.randint(0, 2, num_bits)
        bits = np.where(bits == 0, -1, 1)
        psp = np.repeat(bits, int(self.Fs / self.bits_per_second))[:len(t)]

        # === BPSK С ФАЗОВОЙ РАССТРОЙКОЙ ===
        dphi_rad = self.dphi / 180

        if self.carrier_only:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t)
        else:
            # ВАЖНО: используем cospi и добавляем dphi_rad
            signal_bpsk = cospi(2 * self.Fc * t + (psp + 1) / 2 + dphi_rad)

        # === ШУМ ===
        if self.noise_params['add_noise']:
            P = np.mean(signal_bpsk ** 2)

            if self.noise_params['mode'] == 'ebn0':
                SNR = self.noise_params['value'] + 10 * np.log10(self.bits_per_second / (self.Fs / 2))
            else:
                SNR = self.noise_params['value']

            noise_power = P / (10 ** (SNR / 10))
            noise = np.sqrt(noise_power) * np.random.randn(len(t))
            noisy = signal_bpsk + noise
        else:
            noisy = signal_bpsk

        # === ФИЛЬТР ===
        Wp_norm = [self.Wp_low / (self.Fs / 2), self.Wp_high / (self.Fs / 2)]
        Ws_norm = [self.Ws_low / (self.Fs / 2), self.Ws_high / (self.Fs / 2)]

        if self.order_mode == 1:
            N = self.filter_order
            Wn = Wp_norm

            if self.filter_type == "ellip":
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')
        else:
            if self.filter_type == "ellip":
                N, Wn = signal.ellipord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                N, Wn = signal.cheby1ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                N, Wn = signal.cheby2ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')

        filtered = signal.lfilter(b, a, noisy)

        # === PLL ===
        Gp, Sr, T_lf = self.Gp, self.Sr, self.T_lf
        F_vco = self.Fc
        delay = np.deg2rad(self.delay_deg) / np.pi

        VCO_cos = cospi(2 * F_vco * t - delay)
        VCO_sin = sinpi(2 * F_vco * t - delay)

        mul_cos = np.zeros(len(t))
        mul_sin = np.zeros(len(t))
        lpf_cos = np.zeros(len(t) + 1)
        lpf_sin = np.zeros(len(t) + 1)
        phase_diskr = np.zeros(len(t))
        uf = np.zeros(len(t) + 1)
        est_phase = np.zeros(len(t) + 2)
        freq_VCO = np.zeros(len(t) + 1)

        d_lf = Ts / T_lf

        for i in range(len(t) - 1):
            mul_cos[i] = filtered[i] * VCO_cos[i]
            mul_sin[i] = filtered[i] * VCO_sin[i]

            lpf_cos[i + 1] = mul_cos[i] * d_lf + lpf_cos[i] * (1 - d_lf)
            lpf_sin[i + 1] = mul_sin[i] * d_lf + lpf_sin[i] * (1 - d_lf)

            phase_diskr[i] = lpf_cos[i] * lpf_sin[i]

            if i > 0:
                uf[i + 1] = uf[i] + Gp * phase_diskr[i] - (Gp - Ts) * phase_diskr[i - 1]
            else:
                uf[i + 1] = uf[i] + Gp * phase_diskr[i]

            freq_VCO[i + 1] = Sr * uf[i + 1]
            est_phase[i + 2] = est_phase[i + 1] + Ts * freq_VCO[i + 1]

            arg_phVCO = F_vco * t[i + 1] + est_phase[i + 1] + delay
            VCO_cos[i + 1] = cospi(2 * arg_phVCO)
            VCO_sin[i + 1] = sinpi(2 * arg_phVCO)

        # === Шум ГУН ===
        phase_noise_out = np.cumsum(2e-3 * np.random.randn(len(t)))
        VCO_out = np.cos(2 * np.pi * self.Fc * t + phase_noise_out)
        VCO_out += 1e-4 * np.random.randn(len(t))

        self.last_VCO_out = VCO_out
        self.last_Fs = self.Fs

        # === ДЕМОДУЛЯЦИЯ ===
        demod_signal = lpf_cos[:-1] - lpf_sin[:-1]

        samples_per_bit = int(self.Fs / self.bits_per_second)

        # 1. Timing recovery
        nbits_total = len(demod_signal) // samples_per_bit

        best_offset = 0
        best_metric = -np.inf
        for offset in range(samples_per_bit):
            metric = 0
            for k in range(nbits_total):
                idx = offset + k * samples_per_bit
                if idx < len(demod_signal):
                    metric += abs(demod_signal[idx])
            if metric > best_metric:
                best_metric = metric
                best_offset = offset

        # 2. Декодирование
        recovered_raw = np.zeros(nbits_total)
        for k in range(nbits_total):
            idx = best_offset + k * samples_per_bit
            if idx < len(demod_signal):
                recovered_raw[k] = 1 if demod_signal[idx] > 0 else -1

        # 3. Выравнивание через корреляцию
        psp_bits_full = bits[:nbits_total]
        corr = np.correlate(recovered_raw, psp_bits_full, mode='full')
        shift = np.argmax(np.abs(corr)) - len(psp_bits_full) + 1

        if shift > 0:
            recovered = recovered_raw[shift:]
            psp_bits = psp_bits_full[:len(recovered)]
        elif shift < 0:
            shift_abs = -shift
            recovered = recovered_raw[:-shift_abs] if shift_abs > 0 else recovered_raw
            psp_bits = psp_bits_full[shift_abs:]
        else:
            recovered = recovered_raw
            psp_bits = psp_bits_full

        # ========== УБРАЛ АВТОКОМПЕНСАЦИЮ ИНВЕРСИИ ==========
        # 4. Расчет BER (БЕЗ проверки на инверсию)
        if len(recovered) > 0 and len(psp_bits) > 0:
            min_len = min(len(recovered), len(psp_bits))
            recovered = recovered[:min_len]
            psp_bits = psp_bits[:min_len]
            errors = np.sum(recovered != psp_bits)
            ber = errors / min_len if min_len > 0 else 1.0
        else:
            errors = 0
            ber = 1.0

        # Время для восстановленной ПСП
        t_rec = np.arange(len(psp_bits)) / self.bits_per_second

        self.finished.emit({
            "t": t,
            "errors": errors,
            "ber": ber,
            "psp": psp,
            "phase": phase_diskr,
            "lpf_cos": lpf_cos[:-1],
            "lpf_sin": lpf_sin[:-1],
            "t_rec": t_rec,
            "rec": recovered,
            "psp_bits": psp_bits
        })


class PSDWorker(QThread):
    finished = Signal(dict)

    def __init__(self, signal, fs, transition):
        super().__init__()
        self.signal = signal
        self.fs = fs
        self.transition = transition

    def compute_psd(self, signal, fs, transition):
        from scipy.signal import periodogram

        transition_samples = int(transition * fs)
        if transition_samples >= len(signal) - 1000:
            transition_samples = 0

        signal_trim = signal[transition_samples:]

        if len(signal_trim) < 1024:
            return np.array([0]), np.array([-200])

        f, Pxx = periodogram(
            signal_trim,
            fs=fs,
            window='boxcar',
            nfft=len(signal_trim),
            detrend=False,
            scaling='density'
        )

        return f, 10 * np.log10(Pxx + 1e-20)

    def run(self):
        f, pxx = self.compute_psd(self.signal, self.fs, self.transition)
        self.finished.emit({"f_vco": f, "pxx_vco": pxx})


class WorkerPart4(QThread):
    finished = Signal(dict)

    def __init__(self, T, Fs, Fc, bits_per_second,
                 filter_type, order_mode, filter_order,
                 Wp_low, Wp_high, Ws_low, Ws_high,
                 gpass, gstop, Gp, Sr, T_lf, delay_deg,
                 noise_params, freq_offset, carrier_only):
        super().__init__()
        self.T = T
        self.Fs = Fs
        self.Fc = Fc
        self.bits_per_second = bits_per_second
        self.filter_type = filter_type
        self.order_mode = order_mode
        self.filter_order = filter_order
        self.Wp_low = Wp_low
        self.Wp_high = Wp_high
        self.Ws_low = Ws_low
        self.Ws_high = Ws_high
        self.gpass = gpass
        self.gstop = gstop
        self.Gp = Gp
        self.Sr = Sr
        self.T_lf = T_lf
        self.delay_deg = delay_deg
        self.noise_params = noise_params
        self.freq_offset = freq_offset
        self.last_VCO_out = None
        self.last_Fs = None
        self.carrier_only = carrier_only

    def run(self):
        Ts = 1 / self.Fs
        t = np.arange(0, self.T, Ts)

        num_bits = int(self.T * self.bits_per_second)

        # ПСП
        bits = np.random.randint(0, 2, num_bits)
        bits = np.where(bits == 0, -1, 1)
        psp = np.repeat(bits, int(self.Fs / self.bits_per_second))[:len(t)]

        # ========== ИСПРАВЛЕНО: BPSK с частотной расстройкой ==========
        if self.carrier_only:
            signal_bpsk = np.cos(2 * np.pi * self.Fc * t)
        else:
            signal_bpsk = cospi(2 * (self.Fc + self.freq_offset) * t + (psp + 1) / 2)

        # шум
        if self.noise_params['add_noise']:
            P = np.mean(signal_bpsk ** 2)

            if self.noise_params['mode'] == 'ebn0':
                SNR = self.noise_params['value'] + 10 * np.log10(self.bits_per_second / (self.Fs / 2))
            else:
                SNR = self.noise_params['value']

            noise_power = P / (10 ** (SNR / 10))
            noise = np.sqrt(noise_power) * np.random.randn(len(t))
            noisy = signal_bpsk + noise
        else:
            noisy = signal_bpsk

        # фильтр (используем параметры из глобальных)
        Wp_norm = [self.Wp_low / (self.Fs / 2), self.Wp_high / (self.Fs / 2)]
        Ws_norm = [self.Ws_low / (self.Fs / 2), self.Ws_high / (self.Fs / 2)]

        if self.order_mode == 1:
            N = self.filter_order
            Wn = Wp_norm

            if self.filter_type == "ellip":
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')
        else:
            if self.filter_type == "ellip":
                N, Wn = signal.ellipord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.ellip(N, self.gpass, self.gstop, Wn, btype='band')
            elif self.filter_type == "butter":
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.butter(N, Wn, btype='band')
            elif self.filter_type == "cheby1":
                N, Wn = signal.cheby1ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby1(N, self.gpass, Wn, btype='band')
            elif self.filter_type == "cheby2":
                N, Wn = signal.cheby2ord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.cheby2(N, self.gstop, Wn, btype='band')
            else:
                N, Wn = signal.buttord(Wp_norm, Ws_norm, self.gpass, self.gstop)
                b, a = signal.bessel(N, Wn, btype='band', norm='phase')

        filtered = signal.lfilter(b, a, noisy)

        # PLL (используем параметры из глобальных)
        Gp, Sr, T_lf = self.Gp, self.Sr, self.T_lf
        F_vco = self.Fc
        delay = np.deg2rad(self.delay_deg) / np.pi

        VCO_cos = cospi(2 * F_vco * t - delay)
        VCO_sin = sinpi(2 * F_vco * t - delay)

        mul_cos = np.zeros(len(t))
        mul_sin = np.zeros(len(t))
        lpf_cos = np.zeros(len(t) + 1)
        lpf_sin = np.zeros(len(t) + 1)
        phase = np.zeros(len(t))
        uf = np.zeros(len(t) + 1)
        est = np.zeros(len(t) + 2)
        freq = np.zeros(len(t) + 1)

        d_lf = Ts / T_lf

        for i in range(len(t) - 1):
            mul_cos[i] = filtered[i] * VCO_cos[i]
            mul_sin[i] = filtered[i] * VCO_sin[i]

            lpf_cos[i + 1] = mul_cos[i] * d_lf + lpf_cos[i] * (1 - d_lf)
            lpf_sin[i + 1] = mul_sin[i] * d_lf + lpf_sin[i] * (1 - d_lf)

            phase[i] = lpf_cos[i] * lpf_sin[i]

            if i > 0:
                uf[i + 1] = uf[i] + Gp * phase[i] - (Gp - Ts) * phase[i - 1]
            else:
                uf[i + 1] = uf[i] + Gp * phase[i]

            freq[i + 1] = Sr * uf[i + 1]
            est[i + 2] = est[i + 1] + Ts * freq[i + 1]

            arg = F_vco * t[i + 1] + est[i + 1] + delay
            VCO_cos[i + 1] = cospi(2 * arg)
            VCO_sin[i + 1] = sinpi(2 * arg)

        # === Шум ГУН ===
        phase_noise_out = np.cumsum(2e-3 * np.random.randn(len(t)))
        VCO_out = np.cos(2 * np.pi * self.Fc * t + phase_noise_out)
        VCO_out += 1e-4 * np.random.randn(len(t))

        # Сохраняем для последующего расчёта СПМ
        self.last_VCO_out = VCO_out
        self.last_Fs = self.Fs

        # ========== ПРАВИЛЬНАЯ ДЕМОДУЛЯЦИЯ (как в части 3) ==========
        demod_signal = lpf_cos[:-1] - lpf_sin[:-1]

        samples_per_bit = int(self.Fs / self.bits_per_second)

        # 1. Timing recovery (поиск оптимального offset)
        nbits_total = len(demod_signal) // samples_per_bit

        best_offset = 0
        best_metric = -np.inf
        for offset in range(samples_per_bit):
            metric = 0
            for k in range(nbits_total):
                idx = offset + k * samples_per_bit
                if idx < len(demod_signal):
                    metric += abs(demod_signal[idx])
            if metric > best_metric:
                best_metric = metric
                best_offset = offset

        # 2. Декодирование с найденным offset
        recovered_raw = np.zeros(nbits_total)
        for k in range(nbits_total):
            idx = best_offset + k * samples_per_bit
            if idx < len(demod_signal):
                recovered_raw[k] = 1 if demod_signal[idx] > 0 else -1

        # 3. Выравнивание через корреляцию (компенсация задержки)
        psp_bits_full = bits[:nbits_total]
        corr = np.correlate(recovered_raw, psp_bits_full, mode='full')
        shift = np.argmax(np.abs(corr)) - len(psp_bits_full) + 1

        # Компенсируем сдвиг
        if shift > 0:
            recovered = recovered_raw[shift:]
            psp_bits = psp_bits_full[:len(recovered)]
        elif shift < 0:
            shift_abs = -shift
            recovered = recovered_raw[:-shift_abs] if shift_abs > 0 else recovered_raw
            psp_bits = psp_bits_full[shift_abs:]
        else:
            recovered = recovered_raw
            psp_bits = psp_bits_full

        # 4. Прямое сравнение БЕЗ компенсации инверсии (как в реальной системе)
        if len(recovered) > 0 and len(psp_bits) > 0:
            min_len = min(len(recovered), len(psp_bits))
            rec_check = recovered[:min_len]
            psp_check = psp_bits[:min_len]

            # Реальная система: просто сравниваем, что получили
            errors = np.sum(rec_check != psp_check)
            ber = errors / min_len if min_len > 0 else 1.0
        else:
            errors = 0
            ber = 1.0

        # Время для восстановленной ПСП
        t_rec = np.arange(len(psp_bits)) / self.bits_per_second

        # Отправляем основные сигналы
        self.finished.emit({
            "t": t,
            "psp": psp,
            "phase": phase,
            "lpf_cos": lpf_cos[:-1],
            "lpf_sin": lpf_sin[:-1],
            "t_rec": t_rec,
            "rec": recovered,
            "psp_bits": psp_bits,
            "errors": errors,
            "ber": ber
        })


class WorkerPart5(QThread):
    finished = Signal(dict)

    def __init__(self, phase_min, phase_max, phase_step):
        super().__init__()
        self.phase_min = phase_min
        self.phase_max = phase_max
        self.phase_step = phase_step

    def run(self):
        # Параметры (фиксированные как в MATLAB коде)
        T = 2
        Fs = 20000
        Ts = 1 / Fs
        t = np.arange(0, T, Ts)

        Fc = 1000
        Ac = 1
        bits_per_second = 50
        phase_shift = -6.53  # Сдвиг фазы в градусах

        # Информационный поток
        num_bits = int(T * bits_per_second)
        psp_bits = np.random.randint(0, 2, num_bits)
        psp_bits = np.where(psp_bits == 0, -1, 1)
        psp_signal = np.repeat(psp_bits, int(Fs / bits_per_second))[:len(t)]

        # Фазовая модуляция
        Signal_BPSK = Ac * np.cos(2 * np.pi * Fc * t + np.pi * (psp_signal + 1) / 2)

        # Фильтр - ИСПРАВЛЕНО: используем деление через numpy
        Wp_band = np.array([900, 1100]) / (Fs / 2)
        Ws_band = np.array([800, 1200]) / (Fs / 2)
        Rp_band = 1
        Rs_band = 40

        N_band, Wn_band = signal.ellipord(Wp_band, Ws_band, Rp_band, Rs_band)
        b_band, a_band = signal.ellip(N_band, Rp_band, Rs_band, Wn_band, btype='band')
        Signal_BPSK_filtered = signal.lfilter(b_band, a_band, Signal_BPSK)

        # Генерация дискриминационной характеристики
        phase_diff_degrees = np.arange(self.phase_min, self.phase_max + self.phase_step, self.phase_step)
        phase_diff_radians = np.deg2rad(phase_diff_degrees) + np.deg2rad(phase_shift)
        output_fd_all = np.zeros(len(phase_diff_degrees))

        for k, phase_diff in enumerate(phase_diff_radians):
            VCO_cos = Ac * np.cos(2 * np.pi * Fc * t + phase_diff)
            VCO_sin = Ac * np.sin(2 * np.pi * Fc * t + phase_diff)

            mul_cos = Signal_BPSK_filtered * VCO_cos
            mul_sin = Signal_BPSK_filtered * VCO_sin

            # Используем ФНЧ вместо полосового для демодуляции
            # Создаем ФНЧ с частотой среза 100 Гц
            Wp_low = 100 / (Fs / 2)
            Ws_low = 150 / (Fs / 2)
            N_low, Wn_low = signal.ellipord(Wp_low, Ws_low, 1, 40)
            b_low, a_low = signal.ellip(N_low, 1, 40, Wn_low, btype='low')

            lpf_cos = signal.lfilter(b_low, a_low, mul_cos)
            lpf_sin = signal.lfilter(b_low, a_low, mul_sin)

            output_fd_all[k] = np.mean(lpf_cos * lpf_sin)

        # Нормализация
        if max(abs(output_fd_all)) > 0:  # Защита от деления на ноль
            output_fd_all = output_fd_all / max(abs(output_fd_all))

        self.finished.emit({
            "phase_diff": phase_diff_degrees,
            "output": output_fd_all
        })


class PlotTab(QWidget):
    def __init__(self, title, xlabel="Время, с", ylabel="", subplots=1):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        # Устанавливаем политику размера, чтобы canvas растягивался
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.toolbar = NavigationToolbar(self.canvas, self)
        # Устанавливаем фиксированную высоту тулбара
        self.toolbar.setFixedHeight(35)

        # Добавляем виджеты - canvas будет растягиваться, toolbar имеет фиксированную высоту
        layout.addWidget(self.canvas, stretch=1)  # stretch=1 - будет занимать всё свободное место
        layout.addWidget(self.toolbar)
        self.setLayout(layout)

        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.subplots = subplots

        # создаем одну или несколько осей
        if self.subplots == 1:
            self.ax = self.figure.add_subplot(111)
        else:
            self.ax = self.figure.subplots(self.subplots, 1, sharex=True)
        self._setup_axes()

    def scatter_plot(self, x, y, ax_index=0, color='red', markersize=6, label=None):
        """Метод для построения точечных графиков (отсчетов)"""
        if self.subplots == 1:
            self.ax.clear()
            self.ax.scatter(x, y, color=color, s=markersize, label=label, zorder=5)
            self._restore_axis_settings(self.ax, 0)
            if label:
                self.ax.legend(loc='best', fontsize=12)
        else:
            axi = self.ax[ax_index]
            axi.clear()
            axi.scatter(x, y, color=color, s=markersize, label=label, zorder=5)
            self._restore_axis_settings(axi, ax_index)
            if label:
                axi.legend(loc='best', fontsize=10)
        self.canvas.draw()

    def _setup_axes(self):
        if self.subplots == 1:
            self.ax.set_title(self.title, fontsize=14)
            self.ax.set_xlabel(self.xlabel, fontsize=12)
            self.ax.set_ylabel(self.ylabel, fontsize=12)
            self.ax.grid(True, alpha=0.3)
        else:
            for i, axi in enumerate(self.ax):
                axi.set_ylabel(self.ylabel if i == 0 else "")
                axi.grid(True, alpha=0.3)
            self.ax[-1].set_xlabel(self.xlabel, fontsize=12)
            if self.title:
                self.figure.suptitle(self.title, fontsize=14)
        self.canvas.draw()

    def _restore_axis_settings(self, axi, ax_index):
        """Восстанавливает настройки оси (сетку, подписи)"""
        axi.grid(True, alpha=0.3)
        if self.subplots == 1:
            axi.set_xlabel(self.xlabel, fontsize=12)
            axi.set_ylabel(self.ylabel, fontsize=12)
            if self.title:
                axi.set_title(self.title, fontsize=14)
        else:
            if ax_index == 0:
                axi.set_ylabel(self.ylabel, fontsize=12)
            if ax_index == self.subplots - 1:
                axi.set_xlabel(self.xlabel, fontsize=12)

    def step_plot(self, x, y, ax_index=0, color='red', linewidth=1.5, label=None):
        if self.subplots == 1:
            self.ax.clear()
            self.ax.step(x, y, where='post', color=color, linewidth=linewidth, label=label)
            self._restore_axis_settings(self.ax, 0)
            if label:
                self.ax.legend(loc='best', fontsize=12)
        else:
            axi = self.ax[ax_index]
            axi.clear()
            axi.step(x, y, where='post', color=color, linewidth=linewidth, label=label)
            self._restore_axis_settings(axi, ax_index)
            if label:
                axi.legend(loc='best', fontsize=10)
        self.canvas.draw()

    def plot(self, x, y, ax_index=0, color='blue', linewidth=1.5, label=None):
        if self.subplots == 1:
            self.ax.clear()
            self.ax.plot(x, y, color=color, linewidth=linewidth, label=label)
            self._restore_axis_settings(self.ax, 0)
            if label:
                self.ax.legend(loc='best', fontsize=12)
        else:
            axi = self.ax[ax_index]
            axi.clear()
            axi.plot(x, y, color=color, linewidth=linewidth, label=label)
            self._restore_axis_settings(axi, ax_index)
            if label:
                axi.legend(loc='best', fontsize=10)
        self.canvas.draw()

class GlobalParamsWidget(QWidget):
    """Глобальный виджет для общих параметров всех частей"""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # Создаем вкладки внутри глобальных параметров
        self.params_tabs = QTabWidget()

        # Системные параметры
        self.system_params = SystemParamsWidget()
        self.params_tabs.addTab(self.system_params, "Системные")


        # Параметры канала
        self.channel_params = ChannelParamsWidget()
        self.params_tabs.addTab(self.channel_params, "Канал")

        # Параметры фильтра (объединенные в один виджет)
        self.filter_params = FilterCombinedWidget()
        # self.params_tabs.addTab(self.filter_params, "Параметры фильтра")

        # Параметры ФАПЧ
        self.pll_params = PLLParamsWidget()
        self.params_tabs.addTab(self.pll_params, "СВН")

        # ДОБАВИТЬ НОВЫЙ ВИДЖЕТ - Режим несущей
        self.carrier_widget = QWidget()
        carrier_layout = QVBoxLayout()
        self.carrier_only = QCheckBox("Только несущая (без модуляции)")
        self.carrier_only.setToolTip("При включении передается чистая несущая, ПСП игнорируется")
        self.carrier_only.setStyleSheet("QCheckBox { font-size: 14px; font-weight: bold; color: #2196F3; }")
        carrier_layout.addWidget(self.carrier_only)
        carrier_layout.addStretch()
        self.carrier_widget.setLayout(carrier_layout)
        self.params_tabs.addTab(self.carrier_widget, "Режим несущей")

        # НОВАЯ ВКЛАДКА - Диапазоны параметров
        self.ranges_table = RangesTableWidget(self)  # Передаем self как parent
        self.params_tabs.addTab(self.ranges_table, "📊 Диапазоны параметров")

        layout.addWidget(self.params_tabs)
        self.setLayout(layout)

        self.system_params.paramsChanged.connect(self.on_params_changed)
        self.channel_params.paramsChanged.connect(self.on_params_changed)
        self.pll_params.paramsChanged.connect(self.on_params_changed)

    def is_carrier_only(self):
        """Возвращает True если выбран режим только несущей"""
        return self.carrier_only.isChecked()

    def on_params_changed(self):
        """Автоматически обновляет таблицу при изменении параметров"""
        if hasattr(self, 'ranges_table'):
            self.ranges_table.refresh_ranges()

    def get_system_params(self):
        return {
            'T': self.system_params.T.value(),
            'Fs': int(self.system_params.Fs.value()),
            'Fc': self.system_params.Fc.value(),
            'bits_per_second': self.system_params.bits_per_second.value()
        }

    def get_noise_params(self):
        return self.channel_params.get_noise_params()

    def get_filter_params(self):
        return self.filter_params.get_filter_params()

    def get_pll_params(self):
        return {
            'Gp': self.pll_params.Gp.value(),
            'Sr': self.pll_params.Sr.value(),
            'T_lf': self.pll_params.T_lf.value(),
            'delay_deg': self.pll_params.delay_deg.value()
        }


# ==== GUI ====
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторная работа №5 (СВН)")

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        self.main_tabs = QTabWidget()

        # ==================== СХЕМА ====================
        scheme_widget = QWidget()
        scheme_layout = QVBoxLayout()
        self.scene_view = QtWidgets.QGraphicsView()
        scheme_layout.addWidget(self.scene_view)
        scheme_widget.setLayout(scheme_layout)
        self._draw_new_scheme()
        self.main_tabs.addTab(scheme_widget, "Схема")

        # ==================== ГЛОБАЛЬНЫЕ ПАРАМЕТРЫ ====================
        self.global_params = GlobalParamsWidget()
        self.main_tabs.addTab(self.global_params, "Параметры")

        # ==================== ЧАСТЬ 1 ====================
        part1_widget = QWidget()
        part1_layout = QVBoxLayout()

        # Только графики, параметры берутся из глобальных
        graphs_widget = QWidget()
        graphs_layout = QVBoxLayout()

        self.graphs_tabs = QTabWidget()

        self.tab_psp = PlotTab("ПСП", "Время, с", "")
        self.tab_bpsk = PlotTab("2ФМ сигнал", "Время, с", "")
        self.tab_noisy = PlotTab("Процесс на выходе канала", "Время, с", "")
        self.tab_spec1 = PlotTab("СПМ процесса на выходе канала", "Частота, Гц", "")
        self.tab_filtered = PlotTab("Процесс на выходе ПФ", "Время, с", "")
        self.tab_spec2 = PlotTab("СПМ процесса на выходе ПФ", "Частота, Гц", "")
        self.tab_out = PlotTabWithCheckbox("ПСП на выходе демодулятора", "Время, с", "")
        self.tab_compare = PlotTab("Сравнение ПСП", "Время, с", "", subplots=2)

        self.graphs_tabs.addTab(self.tab_psp, "ПСП")
        self.graphs_tabs.addTab(self.tab_bpsk, "2ФМ сигнал")
        self.graphs_tabs.addTab(self.tab_noisy, "Процесс на выходе канала")
        self.graphs_tabs.addTab(self.tab_spec1, "СПМ процесса на выходе канала")
        self.graphs_tabs.addTab(self.tab_filtered, "Процесс на выходе ПФ")
        self.graphs_tabs.addTab(self.tab_spec2, "СПМ процесса на выходе ПФ")
        self.graphs_tabs.addTab(self.tab_out, "ПСП на выходе демодулятора")
        # self.graphs_tabs.addTab(self.tab_compare, "Сравнение входной и выходной ПСП (часть 1)")

        graphs_layout.addWidget(self.graphs_tabs)
        graphs_widget.setLayout(graphs_layout)

        # Создаем виджет для кнопок в одной строке (как в части 2)
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка запуска расчёта
        self.btn_part1 = QPushButton("Запуск расчёта")
        self.btn_part1.setMinimumHeight(40)
        self.btn_part1.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_part1.clicked.connect(self.start_part1)

        # Кнопка наложения графиков
        self.btn_overlay1 = QPushButton("📊 Наложить графики")
        self.btn_overlay1.setMinimumHeight(40)
        self.btn_overlay1.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #FF9800; color: white;")
        self.btn_overlay1.clicked.connect(lambda: self._show_overlay_dialog(1, self._get_part1_graphs()))

        # В разделе части 1, после кнопки btn_overlay1, добавьте:


        # Добавляем кнопки в горизонтальный layout
        button_layout.addWidget(self.btn_part1)
        button_layout.addWidget(self.btn_overlay1)
        button_widget.setLayout(button_layout)

        # Информация об ошибках
        self.label_errors = QLabel("Ошибки: 0 | BER: 0")
        self.label_errors.setStyleSheet("font-size: 14px; font-weight: bold; color: blue;")
        self.label_errors.setAlignment(Qt.AlignCenter)

        # Собираем основную компоновку части 1
        part1_layout.addWidget(graphs_widget)
        part1_layout.addWidget(button_widget)
        # part1_layout.addWidget(self.label_errors)
        part1_widget.setLayout(part1_layout)

        self.main_tabs.addTab(part1_widget, "Часть 1 (Анализ демодулятора)")

        # ==================== ЧАСТЬ 2 ====================
        part2_widget = QWidget()
        part2_layout = QVBoxLayout()

        # Графики части 2
        graphs2 = QWidget()
        graphs2_layout = QVBoxLayout()

        self.tabs2 = QTabWidget()

        # НОВАЯ ВКЛАДКА - ПСП (в начало)
        self.tab_psp2 = PlotTab("ПСП (часть 2)", "Время, с", "")
        self.tabs2.addTab(self.tab_psp2, "ПСП")



        self.tab_phase = PlotTab("Реализация на выходе ФД")
        self.tab_mul_cos = PlotTab("Реализация на выходе перемножителя квадратурного канала")
        self.tab_mul_sin = PlotTab("Реализация на выходе перемножителя синфазного канала")
        self.tab_lpf_cos = PlotTab("Реализация на выходе ФНЧ квадратурного канала")
        self.tab_lpf_sin = PlotTab("Реализация на выходе ФНЧ синфазного канала")

        self.tab_spec_mul = PlotTab("", subplots=2)
        self.tab_spec_lpf = PlotTab("", subplots=2)
        # self.tab_compare2 = PlotTab(
        #     title="Сравнение входной и выходной ПСП (часть 2)",
        #     xlabel="Время, с",
        #     ylabel="",
        #     subplots=2
        # )
        # self.tab_compare2 = PlotTab(
        #     title="Сравнение входной и выходной ПСП (часть 2)",
        #     xlabel="Время (с)",
        #     ylabel="Амплитуда",
        #     subplots=2
        # )
        # НОВАЯ ВКЛАДКА - ПСП на выходе демодулятора (точки)
        self.tab_demod_out2 = PlotTabWithCheckbox("ПСП на выходе демодулятора", "Время, с", "")
        self.tabs2.addTab(self.tab_mul_sin, "Выход перемножителя (Синф.)")
        self.tabs2.addTab(self.tab_mul_cos, "Выход перемножителя (Кв.)")
        self.tabs2.addTab(self.tab_spec_mul, "СПМ процесса на выходе перемножителей")
        self.tabs2.addTab(self.tab_lpf_sin, "Выход ФНЧ (Синф.)")
        self.tabs2.addTab(self.tab_lpf_cos, "Выход ФНЧ (Кв.)")
        self.tabs2.addTab(self.tab_spec_lpf, "СПМ процесса на выходе ФНЧ")
        self.tabs2.addTab(self.tab_phase, "Реализация на выходе ФД")
        # ПОСЛЕДНЯЯ вкладка - ПСП на выходе демодулятора
        self.tabs2.addTab(self.tab_demod_out2, "ПСП на выходе демодулятора")
        # self.tabs2.addTab(self.tab_compare2, "Сравнение входной и выходной ПСП")

        graphs2_layout.addWidget(self.tabs2)
        graphs2.setLayout(graphs2_layout)

        # Создаем виджет для двух кнопок в одной строке
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка запуска расчёта
        self.btn_part2 = QPushButton("Запуск расчёта")
        self.btn_part2.setMinimumHeight(40)
        self.btn_part2.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_part2.clicked.connect(self.start_part2)

        # Кнопка "Построить два на одном"
        self.btn_dual_plot = QPushButton("Построить два на одном")
        self.btn_dual_plot.setMinimumHeight(40)
        self.btn_dual_plot.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2196F3; color: white;")
        self.btn_dual_plot.clicked.connect(self.open_dual_plot_dialog)  # Изначально неактивна, пока нет данных

        self.btn_overlay2 = QPushButton("📊 Наложить графики")
        self.btn_overlay2.setMinimumHeight(40)
        self.btn_overlay2.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #FF9800; color: white;")
        self.btn_overlay2.clicked.connect(lambda: self._show_overlay_dialog(2, self._get_part2_graphs()))
        # self.btn_overlay2.setEnabled(False)

        button_layout.addWidget(self.btn_part2)
        button_layout.addWidget(self.btn_dual_plot)
        button_layout.addWidget(self.btn_overlay2)
        button_widget.setLayout(button_layout)

        # Информация об ошибках
        self.label_errors2 = QLabel("Ошибки: 0 | BER: 0")
        self.label_errors2.setStyleSheet("font-size: 14px; font-weight: bold; color: blue;")
        self.label_errors2.setAlignment(Qt.AlignCenter)

        part2_layout.addWidget(graphs2)
        part2_layout.addWidget(button_widget)
        # part2_layout.addWidget(self.label_errors2)
        part2_widget.setLayout(part2_layout)

        self.main_tabs.addTab(part2_widget, "Часть 2 (Анализ СВН)")

        # ==================== ЧАСТЬ 3 (исправленная) ====================
        part3_widget = QWidget()
        part3_layout = QVBoxLayout()

        # Создаем контейнер с прокруткой для графиков
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(400)

        # --- графики ---
        graphs3 = QWidget()
        g3_layout = QVBoxLayout()

        self.tabs3 = QTabWidget()

        # НОВЫЕ ВКЛАДКИ ДЛЯ ЧАСТИ 3
        self.tab_psp3 = PlotTab("ПСП (входная)", "Время, с", "")
        self.tabs3.addTab(self.tab_psp3, "ПСП входная")

        self.tab_demod_out3 = PlotTabWithCheckbox("ПСП на выходе демодулятора", "Время, с", "")


        # Вкладка с двумя графиками ФНЧ (один под другим)
        self.tab_lpf_combined = PlotTab(
            title="Реализация на выходе ФНЧ",
            xlabel="Время, с",
            ylabel="",
            subplots=2
        )

        # Отдельные вкладки для остальных графиков
        self.tab_phase3 = PlotTab("Реализация на выходе ФД")
        self.tab_vco_spec = PlotTab("СПМ на выходе ГУН (без переходного процесса)")

        self.tabs3.addTab(self.tab_lpf_combined, "Выход ФНЧ (Синф. и Кв.)")
        self.tabs3.addTab(self.tab_phase3, "Реализация на выходе ФД")
        self.tabs3.addTab(self.tab_demod_out3, "ПСП на выходе демодулятора")
        self.tabs3.addTab(self.tab_vco_spec, "СПМ на выходе ГУН (без переходного процесса)")


        g3_layout.addWidget(self.tabs3)
        graphs3.setLayout(g3_layout)
        scroll_area.setWidget(graphs3)

        # Панель управления (фиксированной высоты)
        control3_widget = QWidget()
        control3_widget.setFixedHeight(50)
        control3_layout = QHBoxLayout()

        # Панель управления (фиксированной высоты)
        control3_widget = QWidget()
        control3_widget.setFixedHeight(80)  # Увеличиваем высоту
        control3_layout = QHBoxLayout()

        self.dphi = QDoubleSpinBox()
        self.dphi.setRange(-360, 360)  # Расширен диапазон
        self.dphi.setValue(0)
        self.dphi.setFixedWidth(100)
        self.dphi.setSingleStep(1)  # Шаг 1 градус
        self.dphi.setDecimals(0)

        self.btn3 = QPushButton("Запуск расчёта")
        self.btn3.setFixedWidth(170)  # Такой же как у btn_psd
        self.btn3.clicked.connect(self.start_part3)

        self.transition = QDoubleSpinBox()
        self.transition.setRange(0, 10000)
        self.transition.setValue(0.5)
        self.transition.setSingleStep(0.5)
        self.transition.setFixedWidth(100)
        self.transition.setDecimals(1)

        self.btn_psd = QPushButton("Построить СПМ")
        self.btn_psd.setFixedWidth(170)
        self.btn_psd.clicked.connect(self.compute_psd_only)
        self.btn_psd.setEnabled(False)

        # НОВЫЙ ВИДЖЕТ ДЛЯ ОТОБРАЖЕНИЯ BER
        self.label_ber3 = QLabel("Ошибки: -- | BER: --")
        self.label_ber3.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: blue; background-color: #f0f0f0; padding: 5px; border-radius: 5px;")
        self.label_ber3.setFixedWidth(250)

        control3_layout.addWidget(QLabel("Δφ, град.:"))
        control3_layout.addWidget(self.dphi)
        control3_layout.addSpacing(20)
        control3_layout.addWidget(self.btn3)
        control3_layout.addStretch()
        control3_layout.addWidget(QLabel("Переходный процесс, c:"))
        control3_layout.addWidget(self.transition)
        control3_layout.addSpacing(10)
        control3_layout.addWidget(self.btn_psd)
        control3_layout.addSpacing(250)
        # control3_layout.addWidget(self.label_ber3)  # ДОБАВИТЬ

        control3_widget.setLayout(control3_layout)

        # Кнопка наложения графиков - такой же размер как у btn_psd
        self.btn_overlay3 = QPushButton("📊 Наложить графики")
        self.btn_overlay3.setFixedWidth(180)  # Такой же как у btn_psd
        self.btn_overlay3.setMinimumHeight(30)  # Такой же как у btn_psd
        self.btn_overlay3.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #FF9800; color: white; border-radius: 6px;")
        self.btn_overlay3.clicked.connect(lambda: self._show_overlay_dialog(3, self._get_part3_graphs()))
        control3_layout.addWidget(self.btn_overlay3)


        part3_layout.addWidget(scroll_area, stretch=1)
        part3_layout.addWidget(control3_widget)
        part3_widget.setLayout(part3_layout)

        self.main_tabs.addTab(part3_widget, "Часть 3 (Анализ СВН при Δφ ≠ 0)")

        # ==================== ЧАСТЬ 4 (исправленная) ====================
        part4_widget = QWidget()
        part4_layout = QVBoxLayout()

        # Контейнер с прокруткой
        scroll_area4 = QScrollArea()
        scroll_area4.setWidgetResizable(True)
        scroll_area4.setMinimumHeight(400)

        # --- графики ---
        graphs4 = QWidget()
        g4_layout = QVBoxLayout()

        self.tabs4 = QTabWidget()

        # НОВЫЕ ВКЛАДКИ ДЛЯ ЧАСТИ 4
        self.tab_psp4 = PlotTab("ПСП (входная)", "Время, с", "")
        self.tabs4.addTab(self.tab_psp4, "ПСП входная")

        self.tab_demod_out4 = PlotTabWithCheckbox("ПСП на выходе демодулятора", "Время, с", "")


        # Вкладка с двумя графиками ФНЧ (один под другим)
        self.tab4_lpf_combined = PlotTab(
            title="Реализация на выходе ФНЧ",
            xlabel="Время, с",
            ylabel="",
            subplots=2
        )

        # Отдельные вкладки для остальных графиков
        self.tab4_phase = PlotTab("Реализация на выходе ФД")
        self.tab4_spec = PlotTab("СПМ на выходе ГУН (без переходного процесса)")

        self.tabs4.addTab(self.tab4_lpf_combined, "Выход ФНЧ (Синф. и Кв.)")
        self.tabs4.addTab(self.tab4_phase, "Реализация на выходе ФД")
        self.tabs4.addTab(self.tab_demod_out4, "ПСП на выходе демодулятора")
        self.tabs4.addTab(self.tab4_spec, "СПМ на выходе ГУН (без переходного процесса)")


        g4_layout.addWidget(self.tabs4)
        graphs4.setLayout(g4_layout)
        scroll_area4.setWidget(graphs4)

        # Панель управления
        control4_widget = QWidget()
        control4_widget.setFixedHeight(80)
        control4_layout = QHBoxLayout()

        self.freq_offset = QDoubleSpinBox()
        self.freq_offset.setRange(-500, 500)
        self.freq_offset.setValue(0)
        self.freq_offset.setFixedWidth(100)
        self.freq_offset.setDecimals(0)

        self.btn4 = QPushButton("Запуск расчёта")
        self.btn4.setFixedWidth(170)  # Такой же как у btn_psd4
        self.btn4.clicked.connect(self.start_part4)

        self.transition4 = QDoubleSpinBox()
        self.transition4.setRange(0, 10000)
        self.transition4.setValue(0.5)
        self.transition4.setSingleStep(0.5)
        self.transition4.setFixedWidth(100)
        self.transition4.setDecimals(1)

        self.btn_psd4 = QPushButton("Построить СПМ")
        self.btn_psd4.setFixedWidth(170)
        self.btn_psd4.clicked.connect(self.compute_psd_only4)
        self.btn_psd4.setEnabled(False)

        # НОВЫЙ ВИДЖЕТ ДЛЯ ОТОБРАЖЕНИЯ BER
        self.label_ber4 = QLabel("Ошибки: -- | BER: --")
        self.label_ber4.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: blue; background-color: #f0f0f0; padding: 5px; border-radius: 5px;")
        self.label_ber4.setFixedWidth(250)

        control4_layout.addWidget(QLabel("Δf, Гц:"))
        control4_layout.addWidget(self.freq_offset)
        control4_layout.addSpacing(20)
        control4_layout.addWidget(self.btn4)
        control4_layout.addStretch()
        control4_layout.addWidget(QLabel("Переходный процесс, c:"))
        control4_layout.addWidget(self.transition4)
        control4_layout.addSpacing(10)
        control4_layout.addWidget(self.btn_psd4)
        # control4_layout.addWidget(self.label_ber4)  # ДОБАВЛЕНО
        control4_widget.setLayout(control4_layout)
        control4_layout.addSpacing(280)

        # Кнопка наложения графиков - такой же размер как у btn_psd4
        self.btn_overlay4 = QPushButton("📊 Наложить графики")
        self.btn_overlay4.setFixedWidth(180)  # Такой же как у btn_psd4
        self.btn_overlay4.setMinimumHeight(30)  # Такой же как у btn_psd4
        self.btn_overlay4.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #FF9800; color: white; border-radius: 6px;")
        self.btn_overlay4.clicked.connect(lambda: self._show_overlay_dialog(4, self._get_part4_graphs()))

        control4_layout.addWidget(self.btn_overlay4)

        # Кнопка сканирования частоты
        self.btn_scan_freq = QPushButton("🔬 Сканировать BER по частоте")
        self.btn_scan_freq.setFixedWidth(220)
        self.btn_scan_freq.setMinimumHeight(30)
        self.btn_scan_freq.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #9C27B0; color: white; border-radius: 6px;")
        self.btn_scan_freq.clicked.connect(self.run_ber_vs_freq_scan)

        # Кнопка многократных измерений
        self.btn_multirun_freq = QPushButton("📊 Многократные измерения")
        self.btn_multirun_freq.setFixedWidth(220)
        self.btn_multirun_freq.setMinimumHeight(30)
        self.btn_multirun_freq.setStyleSheet(
            "font-size: 14px; font-weight: bold; background-color: #009688; color: white; border-radius: 6px;")
        self.btn_multirun_freq.clicked.connect(lambda: self.run_multiple_freq_measurements(10, 25))

        # Добавляем в control4_layout (перед btn_overlay4)
        # control4_layout.addWidget(self.btn_scan_freq)
        # control4_layout.addWidget(self.btn_multirun_freq)

        part4_layout.addWidget(scroll_area4, stretch=1)
        part4_layout.addWidget(control4_widget)
        part4_widget.setLayout(part4_layout)

        self.main_tabs.addTab(part4_widget, "Часть 4 (Анализ СВН при Δf ≠ 0)")

        # ==================== ЧАСТЬ 5 (исправленная) ====================
        part5_widget = QWidget()
        part5_layout = QVBoxLayout()

        # Создаем фигуру для графика
        self.figure5 = Figure(figsize=(10, 6))
        self.canvas5 = FigureCanvas(self.figure5)
        self.ax5 = self.figure5.add_subplot(111)
        self.ax5.set_title("Дискриминационная характеристика", fontsize=14)
        self.ax5.set_xlabel("Рассогласование по фазе, град.", fontsize=12)
        self.ax5.set_ylabel("Выход дискриминатора", fontsize=12)
        self.ax5.grid(True, alpha=0.3)

        # Тулбар для графика
        self.toolbar5 = NavigationToolbar(self.canvas5, self)

        # Панель параметров (горизонтальная)
        params_widget = QWidget()
        params_widget.setFixedHeight(60)
        params_layout = QHBoxLayout()
        params_layout.setContentsMargins(10, 5, 10, 5)
        params_layout.setSpacing(15)

        # Параметр "От"
        self.phase_min = QDoubleSpinBox()
        self.phase_min.setValue(-540)
        self.phase_min.setRange(-1080, 1080)
        self.phase_min.setDecimals(0)
        self.phase_min.setFixedWidth(100)
        self.phase_min.setStyleSheet("font-size: 12px; font-weight: bold;")

        # Параметр "До"
        self.phase_max = QDoubleSpinBox()
        self.phase_max.setValue(540)
        self.phase_max.setRange(-1080, 1080)
        self.phase_max.setDecimals(0)
        self.phase_max.setFixedWidth(100)
        self.phase_max.setStyleSheet("font-size: 12px; font-weight: bold;")

        # Параметр "Шаг"
        self.phase_step = QDoubleSpinBox()
        self.phase_step.setValue(10)
        self.phase_step.setRange(0.1, 180)
        self.phase_step.setDecimals(0)
        self.phase_step.setFixedWidth(100)
        self.phase_step.setStyleSheet("font-size: 12px; font-weight: bold;")

        # Кнопка построения
        self.btn5 = QPushButton("Построить ДХ")
        self.btn5.setFixedHeight(30)
        self.btn5.setFixedWidth(120)
        self.btn5.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn5.clicked.connect(self.start_part5)

        # Добавляем виджеты на панель параметров
        params_layout.addWidget(QLabel("От (град.):"))
        params_layout.addWidget(self.phase_min)
        params_layout.addSpacing(10)
        params_layout.addWidget(QLabel("До (град.):"))
        params_layout.addWidget(self.phase_max)
        params_layout.addSpacing(10)
        params_layout.addWidget(QLabel("Шаг (град.):"))
        params_layout.addWidget(self.phase_step)
        params_layout.addSpacing(20)
        params_layout.addWidget(self.btn5)
        params_layout.addStretch()

        params_widget.setLayout(params_layout)

        # Собираем основную компоновку
        part5_layout.addWidget(self.canvas5, stretch=1)
        part5_layout.addWidget(self.toolbar5)
        part5_layout.addWidget(params_widget)

        part5_widget.setLayout(part5_layout)
        self.main_tabs.addTab(part5_widget, "Часть 5 (Дискриминационная характеристика)")

        main_layout.addWidget(self.main_tabs)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)


    def _get_part1_graphs(self):
        return [
            ("ПСП", lambda: ("ПСП", self.last_part1_data["t"], self.last_part1_data["psp"], "line", "Время, с", "")),
            ("2ФМ сигнал",
             lambda: ("2ФМ сигнал", self.last_part1_data["t"], self.last_part1_data["bpsk"], "line", "Время, с", "")),
            ("Процесс на выходе канала",
             lambda: ("Процесс на выходе канала", self.last_part1_data["t"], self.last_part1_data["noisy"], "line",
                      "Время, с", "")),
            ("СПМ на выходе канала", lambda: ("СПМ на выходе канала", self.last_part1_data["f1"], 10 * np.log10(
                np.where(self.last_part1_data["pxx1"] <= 0, 1e-12, self.last_part1_data["pxx1"])), "line",
                                              "Частота, Гц", "дБ")),
            ("Процесс на выходе ПФ",
             lambda: ("Процесс на выходе ПФ", self.last_part1_data["t"], self.last_part1_data["filtered"], "line",
                      "Время, с", "")),
            ("СПМ на выходе ПФ", lambda: ("СПМ на выходе ПФ", self.last_part1_data["f2"], 10 * np.log10(
                np.where(self.last_part1_data["pxx2"] <= 0, 1e-12, self.last_part1_data["pxx2"])), "line",
                                          "Частота, Гц", "дБ")),
            ("ПСП на выходе демодулятора",
             lambda: ("ПСП на выходе демодулятора", self.last_part1_data["t_rec"], self.last_part1_data["rec"],
                      "scatter",
                      "Время, с", "")),
            # ("Исходная ПСП (отсчеты)",
            #  lambda: ("Исходная ПСП", self.last_part1_data["t_rec"], self.last_part1_data["psp_bits"], "scatter",
            #           "Время, с", "")),
        ]

    def _get_part2_graphs(self):
        return [
            ("ПСП",
             lambda: ("ПСП", self.last_part2_data["t"], self.last_part2_data["psp"], "line", "Время, с", "")),
            ("Реализация на выходе ФД",
             lambda: ("Реализация на выходе ФД", self.last_part2_data["t"], self.last_part2_data["phase"], "line",
                      "Время, с", "")),
            ("Выход перемножителя (Синф.)",
             lambda: ("Выход перемножителя (Синф.)", self.last_part2_data["t"], self.last_part2_data["mul_sin"], "line",
                      "Время, с", "")),
            ("Выход перемножителя (Кв.)",
             lambda: ("Выход перемножителя (Кв.)", self.last_part2_data["t"], self.last_part2_data["mul_cos"], "line",
                      "Время, с", "")),
            ("Выход ФНЧ (Синф.)",
             lambda: ("Выход ФНЧ (Синф.)", self.last_part2_data["t"], self.last_part2_data["lpf_sin"], "line",
                      "Время, с", "")),
            ("Выход ФНЧ (Кв.)",
             lambda: ("Выход ФНЧ (Кв.)", self.last_part2_data["t"], self.last_part2_data["lpf_cos"], "line", "Время, с",
                      "")),
            ("СПМ перемножителя (Синф.)",
             lambda: ("СПМ перемножителя (Синф.)", self.last_part2_data["f_mul_sin"],
                      10 * np.log10(np.where(self.last_part2_data["pxx_mul_sin"] <= 0, 1e-12,
                                             self.last_part2_data["pxx_mul_sin"])),
                      "line", "Частота, Гц", "дБ")),
            ("СПМ перемножителя (Кв.)",
             lambda: ("СПМ перемножителя (Кв.)", self.last_part2_data["f_mul_cos"],
                      10 * np.log10(np.where(self.last_part2_data["pxx_mul_cos"] <= 0, 1e-12,
                                             self.last_part2_data["pxx_mul_cos"])),
                      "line", "Частота, Гц", "дБ")),
            ("СПМ ФНЧ (Синф.)",
             lambda: ("СПМ ФНЧ (Синф.)", self.last_part2_data["f_lpf_sin"],
                      10 * np.log10(np.where(self.last_part2_data["pxx_lpf_sin"] <= 0, 1e-12,
                                             self.last_part2_data["pxx_lpf_sin"])),
                      "line", "Частота, Гц", "дБ")),
            ("СПМ ФНЧ (Кв.)",
             lambda: ("СПМ ФНЧ (Кв.)", self.last_part2_data["f_lpf_cos"],
                      10 * np.log10(np.where(self.last_part2_data["pxx_lpf_cos"] <= 0, 1e-12,
                                             self.last_part2_data["pxx_lpf_cos"])),
                      "line", "Частота, Гц", "дБ")),
            # ("Входная ПСП (часть 2)",
            #  lambda: ("Входная ПСП", self.last_part2_data["t_rec"], self.last_part2_data["psp_bits"], "step",
            #           "Время, с", "")),
            ("ПСП на выходе демодулятора",
             lambda: ("ПСП на выходе демодулятора", self.last_part2_data["t_rec"], self.last_part2_data["rec"], "scatter",
                      "Время, с", "")),
        ]

    def _get_part3_graphs(self):
        return [
            ("ПСП",
             lambda: ("ПСП", self.last_part3_data["t"], self.last_part3_data["psp"], "line", "Время, с", "")),

            # ("ПСП на выходе демодулятора (импульсы)",
            #  lambda: ("ПСП выходная", self.last_part3_data["t_rec"], self.last_part3_data["rec"], "step", "Время, с",
            #           "")),
            ("Выход ФНЧ (Синф.)",
             lambda: ("Выход ФНЧ (Синф.)", self.last_part3_data["t"], self.last_part3_data["lpf_sin"], "line",
                      "Время, с", "")),
            ("Выход ФНЧ (Кв.)",
             lambda: ("Выход ФНЧ (Кв.)", self.last_part3_data["t"], self.last_part3_data["lpf_cos"], "line", "Время, с",
                      "")),
            ("Реализация на выходе ФД",
             lambda: ("Реализация на выходе ФД", self.last_part3_data["t"], self.last_part3_data["phase"], "line",
                      "Время, с", "")),
            ("ПСП на выходе демодулятора",
             lambda: ("ПСП на выходе демодулятора", self.last_part3_data["t_rec"], self.last_part3_data["rec"], "scatter", "Время, с",
                      "")),
        ]

    def _get_part4_graphs(self):
        return [
            ("ПСП",
             lambda: ("ПСП", self.last_part4_data["t"], self.last_part4_data["psp"], "line", "Время, с", "")),

            # ("ПСП на выходе демодулятора (импульсы)",
            #  lambda: ("ПСП выходная", self.last_part4_data["t_rec"], self.last_part4_data["rec"], "step", "Время, с",
            #           "")),
            ("Выход ФНЧ (Синф.)",
             lambda: ("Выход ФНЧ (Синф.)", self.last_part4_data["t"], self.last_part4_data["lpf_sin"], "line",
                      "Время, с", "")),
            ("Выход ФНЧ (Кв.)",
             lambda: ("Выход ФНЧ (Кв.)", self.last_part4_data["t"], self.last_part4_data["lpf_cos"], "line", "Время, с",
                      "")),
            ("Реализация на выходе ФД",
             lambda: ("Реализация на выходе ФД", self.last_part4_data["t"], self.last_part4_data["phase"], "line",
                      "Время, с", "")),
            ("ПСП на выходе демодулятора",
             lambda: ("ПСП на выходе демодулятора", self.last_part4_data["t_rec"], self.last_part4_data["rec"], "scatter", "Время, с",
                      "")),
        ]

    def _show_overlay_dialog(self, part_name, graph_items):
        """Показывает диалог выбора графиков для наложения"""
        # Проверяем наличие данных
        if part_name == 1:
            if not hasattr(self, 'last_part1_data'):
                QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт в части 1!")
                return
        elif part_name == 2:
            if not hasattr(self, 'last_part2_data'):
                QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт в части 2!")
                return
        elif part_name == 3:
            if not hasattr(self, 'last_part3_data'):
                QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт в части 3!")
                return
        elif part_name == 4:
            if not hasattr(self, 'last_part4_data'):
                QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт в части 4!")
                return

        dialog = OverlayGraphDialog(graph_items, self)
        if dialog.exec():
            selected = dialog.get_selected_graphs()
            if len(selected) < 2:
                QMessageBox.warning(self, "Ошибка", "Выберите минимум 2 графика для наложения!")
                return
            self._plot_overlay(selected)

    def _plot_overlay(self, graphs_data):
        """Строит наложение выбранных графиков с отдельным окном легенды"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Наложение графиков")
        dialog.resize(1200, 700)  # Увеличил размер для легенды справа

        dialog.setWindowFlags(
            Qt.Dialog |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowSystemMenuHint
        )

        # Используем QHBoxLayout для размещения графика и легенды рядом
        main_layout = QHBoxLayout(dialog)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(5)

        # ==================== ЛЕВАЯ ЧАСТЬ - ГРАФИК ====================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)

        # Создаем фигуру и канвас
        fig = Figure(figsize=(10, 8))
        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Панель управления
        control_panel = QWidget()
        control_panel.setFixedHeight(40)
        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(5, 2, 5, 2)
        control_layout.setSpacing(8)

        # Кнопка для показа/скрытия панели легенды
        self.show_legend_btn_overlay = QPushButton("📋 Показать легенду")  # Текст изменён
        self.show_legend_btn_overlay.setFixedHeight(30)
        self.show_legend_btn_overlay.setMinimumWidth(100)
        self.show_legend_btn_overlay.setCheckable(True)
        self.show_legend_btn_overlay.setChecked(False)  # <--- ИЗМЕНЕНО: теперь не отмечена
        self.show_legend_btn_overlay.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:checked {
                    background-color: #f44336;
                }
            """)

        control_layout.addWidget(self.show_legend_btn_overlay)
        control_layout.addStretch()
        control_panel.setLayout(control_layout)

        # Контейнер для графика
        left_layout.addWidget(canvas, stretch=1)
        left_layout.addWidget(control_panel)

        # Тулбар
        toolbar = NavigationToolbar(canvas, dialog)
        toolbar.setFixedHeight(35)
        left_layout.addWidget(toolbar)

        # ==================== ПРАВАЯ ЧАСТЬ - ЛЕГЕНДА ====================
        right_widget = QWidget()
        right_widget.setFixedWidth(300)
        right_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-left: 1px solid #ccc;
            }
        """)
        right_widget.hide()  # <--- ДОБАВИТЬ ЭТУ СТРОКУ - легенда изначально скрыта

        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        # Заголовок легенды
        legend_title = QLabel("📊 Легенда графиков")
        legend_title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #333;
            padding: 5px;
            background-color: #e9ecef;
            border-radius: 4px;
        """)
        legend_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(legend_title)

        # Scroll area для элементов легенды
        legend_scroll = QScrollArea()
        legend_scroll.setWidgetResizable(True)
        legend_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        legend_container = QWidget()
        self.legend_items_layout = QVBoxLayout(legend_container)
        self.legend_items_layout.setSpacing(8)
        self.legend_items_layout.setContentsMargins(5, 5, 5, 5)
        self.legend_items_layout.addStretch()

        legend_scroll.setWidget(legend_container)
        right_layout.addWidget(legend_scroll)

        # Добавляем левую и правую части в основной layout
        main_layout.addWidget(left_widget, stretch=3)
        main_layout.addWidget(right_widget, stretch=0)

        # Создаем ОДНУ ось
        ax = fig.add_subplot(111)
        fig.subplots_adjust(left=0.07, right=0.96, top=0.93, bottom=0.08)

        # Сохраняем данные
        self.current_overlay_graphs = graphs_data
        self.current_overlay_canvas = canvas
        self.current_overlay_ax = ax
        self.current_overlay_is_scatter = True

        # Цвета
        BLUE_COLOR = '#1f77b4'
        RED_COLOR = '#d62728'
        OTHER_COLORS = ['#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        markers = ['o', 's', '^', 'v', 'D', '*', 'x', '+', 'd', 'p']

        # Проверяем, есть ли выходная ПСП для переключения режима
        has_psp_output = any("ПСП на выходе" in name or "Восстановленная ПСП" in name or "ПСП выходная" in name
                             for name, _, _, _, _, _ in graphs_data)

        def update_legend_panel(legend_data):
            """Обновляет панель легенды"""
            # Очищаем существующие элементы (кроме stretch)
            while self.legend_items_layout.count() > 1:
                item = self.legend_items_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Добавляем новые элементы
            for name, color, plot_type in legend_data:
                item_widget = QWidget()
                item_widget.setStyleSheet("border: none; background-color: transparent;")

                item_layout = QHBoxLayout()
                item_layout.setContentsMargins(5, 5, 5, 5)
                item_layout.setSpacing(10)

                # Цветной индикатор
                indicator = QLabel()
                indicator.setFixedSize(24, 24)
                indicator.setStyleSheet("border: none; background-color: transparent;")

                # Создаем пиксельную карту для индикатора
                pixmap = QtGui.QPixmap(24, 24)
                pixmap.fill(Qt.transparent)
                painter = QtGui.QPainter(pixmap)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)

                if plot_type == 'scatter':
                    painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(color)))
                    painter.drawEllipse(8, 8, 8, 8)
                elif plot_type == 'step':
                    painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawLine(4, 12, 20, 12)
                else:
                    painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawLine(4, 12, 20, 12)

                painter.end()
                indicator.setPixmap(pixmap)

                # Название
                name_label = QLabel(name)
                name_label.setWordWrap(True)
                name_label.setStyleSheet("""
                    color: #333;
                    border: none;
                    background-color: transparent;
                    font-size: 12px;
                """)

                item_layout.addWidget(indicator)
                item_layout.addWidget(name_label, stretch=1)
                item_widget.setLayout(item_layout)

                # Добавляем в основной layout перед stretch
                self.legend_items_layout.insertWidget(self.legend_items_layout.count() - 1, item_widget)

        def draw_overlay():
            ax.clear()
            ax.set_xlabel("Время, с", fontsize=12)
            ax.set_ylabel("", fontsize=12)
            ax.set_title("Наложение графиков", fontsize=14)
            ax.grid(True, alpha=0.3)

            legend_data = []

            # Разделяем графики
            psp_input_data = None
            psp_output_data = None
            other_graphs = []

            for name, x, y, plot_type, xlabel, ylabel in graphs_data:
                if "ПСП на выходе" in name or "Восстановленная ПСП" in name or "ПСП выходная" in name:
                    psp_output_data = (name, x, y, plot_type, xlabel, ylabel)
                elif "ПСП" in name or "входная" in name:
                    psp_input_data = (name, x, y, plot_type, xlabel, ylabel)
                else:
                    other_graphs.append((name, x, y, plot_type, xlabel, ylabel))

            plot_counter = 0

            # Рисуем входную ПСП
            if psp_input_data:
                name, x, y, plot_type, xlabel, ylabel = psp_input_data
                color = BLUE_COLOR
                ax.step(x, y, where='post', color=color, linewidth=2.0, alpha=0.8, label=name)
                clean_name = name.replace("ПСП", "").strip()
                if not clean_name:
                    clean_name = name
                legend_data.append((clean_name, color, 'step'))
                plot_counter += 1

            # Рисуем выходную ПСП
            if psp_output_data:
                name, x, y, plot_type, xlabel, ylabel = psp_output_data
                color = RED_COLOR
                if self.current_overlay_is_scatter:
                    ax.scatter(x, y, color=color, marker='o', s=40, alpha=0.8, zorder=5, edgecolors='none', label=name)
                    plot_type_legend = 'scatter'
                else:
                    ax.step(x, y, where='post', color=color, linewidth=2.0, alpha=0.8, label=name)
                    plot_type_legend = 'step'
                clean_name = name.replace("ПСП", "").strip()
                if not clean_name:
                    clean_name = name
                legend_data.append((clean_name, color, plot_type_legend))
                plot_counter += 1

            # Рисуем остальные графики
            for idx, (name, x, y, plot_type, xlabel, ylabel) in enumerate(other_graphs):
                if plot_counter == 0:
                    color = BLUE_COLOR
                elif plot_counter == 1:
                    color = RED_COLOR
                else:
                    color = OTHER_COLORS[(plot_counter - 2) % len(OTHER_COLORS)]

                if plot_type == 'step':
                    ax.step(x, y, where='post', color=color, linewidth=1.5, alpha=0.8, label=name)
                    plot_type_legend = 'step'
                elif plot_type == 'scatter':
                    marker = markers[idx % len(markers)]
                    ax.scatter(x, y, color=color, marker=marker, s=40, alpha=0.8, zorder=5, edgecolors='none',
                               label=name)
                    plot_type_legend = 'scatter'
                else:
                    ax.plot(x, y, color=color, linewidth=1.5, alpha=0.8, label=name)
                    plot_type_legend = 'line'

                clean_name = name.replace("ПСП", "").strip()
                if not clean_name:
                    clean_name = name
                legend_data.append((clean_name, color, plot_type_legend))
                plot_counter += 1

            fig.subplots_adjust(left=0.07, right=0.96, top=0.93, bottom=0.08)
            ax.relim()
            ax.autoscale_view()
            canvas.draw()

            # Обновляем панель легенды
            update_legend_panel(legend_data)

        def toggle_legend_panel():
            """Показывает/скрывает панель легенды"""
            if right_widget.isVisible():
                right_widget.hide()
                self.show_legend_btn_overlay.setText("📋 Показать легенду")
                self.show_legend_btn_overlay.setChecked(False)
            else:
                right_widget.show()
                self.show_legend_btn_overlay.setText("📋 Скрыть легенду")
                self.show_legend_btn_overlay.setChecked(True)

        # Подключаем кнопку
        self.show_legend_btn_overlay.clicked.connect(toggle_legend_panel)

        # Если есть выходная ПСП, добавляем кнопку переключения режима
        if has_psp_output:
            self.toggle_psp_btn_overlay = QPushButton("📊 Переключить выходную ПСП на импульсы")
            self.toggle_psp_btn_overlay.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)

            # Вставляем перед кнопкой легенды
            control_layout.insertWidget(0, self.toggle_psp_btn_overlay)

            def toggle_psp_mode():
                self.current_overlay_is_scatter = not self.current_overlay_is_scatter
                if self.current_overlay_is_scatter:
                    self.toggle_psp_btn_overlay.setText("📊 Переключить выходную ПСП на импульсы")
                else:
                    self.toggle_psp_btn_overlay.setText("📊 Переключить выходную ПСП на отсчёты")
                draw_overlay()

            self.toggle_psp_btn_overlay.clicked.connect(toggle_psp_mode)

        # Рисуем начальный график
        draw_overlay()

        dialog.exec()

    def _toggle_psp_mode(self, dialog, canvas, graphs_data):
        """Переключает режим отображения ПСП"""
        self.psp_mode_is_scatter = not self.psp_mode_is_scatter

        # Обновляем текст кнопки
        if self.psp_mode_is_scatter:
            self.toggle_psp_btn.setText("📊 Переключить ПСП на импульсы")
            # self.psp_mode_label.setText("ПСП отображается: Точками")
        else:
            self.toggle_psp_btn.setText("📊 Переключить ПСП на отсчёты")
            # self.psp_mode_label.setText("ПСП отображается: Импульсами")

        # Перерисовываем
        self._draw_overlay_with_psp_mode(graphs_data, canvas, self.psp_mode_is_scatter)

    def _draw_overlay_with_psp_mode(self, graphs_data, canvas, is_scatter):
        """Рисует наложение с учётом режима отображения ПСП"""
        ax = canvas.figure.add_subplot(111)
        ax.clear()

        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
        markers = ['o', 's', '^', 'v', 'D', '*', 'x', '+', 'd', 'p']

        for idx, (name, x, y, plot_type, xlabel, ylabel) in enumerate(graphs_data):
            color = colors[idx % len(colors)]

            if idx == 0:
                ax.set_xlabel(xlabel if xlabel else "X")
                ax.set_ylabel("")
                ax.set_title("Наложение графиков")

            # Для ПСП графиков используем выбранный режим
            if "ПСП" in name:
                if is_scatter:
                    marker = markers[idx % len(markers)]
                    ax.scatter(x, y, color=color, marker=marker, s=40, label=name, alpha=0.8, zorder=5)
                else:
                    ax.step(x, y, where='post', color=color, linewidth=1.5, label=name, alpha=0.8)
            else:
                # Для остальных графиков оставляем как есть
                if plot_type == 'step':
                    ax.step(x, y, where='post', color=color, linewidth=1.5, label=name, alpha=0.8)
                elif plot_type == 'scatter':
                    marker = markers[idx % len(markers)]
                    ax.scatter(x, y, color=color, marker=marker, s=40, label=name, alpha=0.8, zorder=5)
                else:  # 'line'
                    ax.plot(x, y, color=color, linewidth=1.5, label=name, alpha=0.8)

        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.relim()
        ax.autoscale_view()
        canvas.draw()

    def _draw_new_scheme(self):
        scene = QtWidgets.QGraphicsScene()
        scene.setSceneRect(0, 0, 1400, 500)

        # Устанавливаем прозрачный фон сцены
        scene.setBackgroundBrush(QtCore.Qt.transparent)

        self.scene_view.setScene(scene)

        # Настраиваем QGraphicsView на прозрачный фон
        self.scene_view.setStyleSheet("background: transparent; border: none;")
        self.scene_view.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # ===== ЗАГОЛОВОК =====
        title_font = QtGui.QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)

        title = scene.addText("Схема РСПИ с системой восстановленй несущей")
        title.setFont(title_font)
        title.setDefaultTextColor(QtCore.Qt.darkBlue)
        title.setPos(500, -140)

        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidth(3)

        font = QtGui.QFont()
        font.setPointSize(9)
        font.setBold(True)

        def add_block(x, y, w, h, text):
            brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
            pen_block = QtGui.QPen(QtCore.Qt.GlobalColor.black)
            pen_block.setWidth(3)
            scene.addRect(x, y, w, h, pen_block, brush)
            t = scene.addText(text)
            t.setFont(font)
            t.setHtml(text)

            # Увеличиваем шрифт для текста внутри блока
            block_font = QtGui.QFont()
            block_font.setPointSize(11)
            block_font.setBold(True)
            t.setFont(block_font)

            bbox = t.boundingRect()
            t.setPos(x + (w - bbox.width()) / 2, y + (h - bbox.height()) / 2)
            return (x, y, w, h)

        def add_arrow(x1, y1, x2, y2, text=None, dx=0, dy=0):
            scene.addLine(x1, y1, x2, y2, pen)

            angle = np.arctan2(y2 - y1, x2 - x1)
            L = 10

            p1 = QtCore.QPointF(x2, y2)
            p2 = QtCore.QPointF(x2 - L * np.cos(angle - np.pi / 6),
                                y2 - L * np.sin(angle - np.pi / 6))
            p3 = QtCore.QPointF(x2 - L * np.cos(angle + np.pi / 6),
                                y2 - L * np.sin(angle + np.pi / 6))

            scene.addPolygon(QtGui.QPolygonF([p1, p2, p3]), pen, QtGui.QBrush(QtCore.Qt.black))

        # ===== БЛОКИ =====
        mult = add_block(180, 200, 60, 60, "X")
        channel = add_block(260, 200, 120, 60, "Канал\nc АБГШ")
        bpf_x, bpf_y, bpf_w, bpf_h = 420, 200, 120, 60
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        pen_block = QtGui.QPen(QtCore.Qt.GlobalColor.black)
        pen_block.setWidth(3)
        scene.addRect(bpf_x, bpf_y, bpf_w, bpf_h, pen_block, brush)

        # Добавляем текст "Полосовой" и "фильтр" отдельно
        block_font = QtGui.QFont()
        block_font.setPointSize(11)
        block_font.setBold(True)

        # Первая строка
        text1 = scene.addSimpleText("Полосовой")
        text1.setFont(block_font)
        text1.setBrush(QtGui.QBrush(QtCore.Qt.black))
        bbox1 = text1.boundingRect()
        text1.setPos(bpf_x + (bpf_w - bbox1.width()) / 2, bpf_y + 12)

        # Вторая строка
        text2 = scene.addSimpleText("фильтр")
        text2.setFont(block_font)
        text2.setBrush(QtGui.QBrush(QtCore.Qt.black))
        bbox2 = text2.boundingRect()
        text2.setPos(bpf_x + (bpf_w - bbox2.width()) / 2, bpf_y + 35)

        # Сохраняем координаты для дальнейшего использования
        bpf = (bpf_x, bpf_y, bpf_w, bpf_h)

        p1 = add_block(640, 90, 60, 50, "П1")
        p2 = add_block(640, 330, 60, 50, "П2")

        lpf1 = add_block(800, 84, 120, 60, "ФНЧ1")
        lpf2 = add_block(800, 325, 120, 60, "ФНЧ2")

        # ===== СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ БЛОКА demod =====
        demod_x, demod_y, demod_w, demod_h = 800, 10, 120, 60
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        pen_block = QtGui.QPen(QtCore.Qt.GlobalColor.black)
        pen_block.setWidth(3)
        scene.addRect(demod_x, demod_y, demod_w, demod_h, pen_block, brush)

        # Текст для блока demod в три строки с центрированием
        demod_lines = ["Интегратор", "+", "РУ"]
        block_font = QtGui.QFont()
        block_font.setPointSize(11)
        block_font.setBold(True)

        # Вычисляем общую высоту текста
        line_heights = []
        text_items = []
        for line in demod_lines:
            t = scene.addSimpleText(line)
            t.setFont(block_font)
            t.setBrush(QtGui.QBrush(QtCore.Qt.black))
            bbox = t.boundingRect()
            line_heights.append(bbox.height())
            text_items.append(t)

        # Уменьшаем расстояние между строками до 2 пикселей
        total_height = sum(line_heights) + 4  # 4 пикселя отступов между строками (было 6)
        start_y = demod_y + (demod_h - total_height) / 2

        # Размещаем каждую строку с минимальным расстоянием
        current_y = start_y
        for i, t in enumerate(text_items):
            bbox = t.boundingRect()
            t.setPos(demod_x + (demod_w - bbox.width()) / 2, current_y)
            # Уменьшаем расстояние между строками до 1-2 пикселей
            current_y += line_heights[i] + 1  # 1 пиксель между строками (было 3)

        demod = (demod_x, demod_y, demod_w, demod_h)
        # ===== КОНЕЦ СПЕЦИАЛЬНОЙ ОБРАБОТКИ =====

        vco = add_block(610, 200, 120, 60, "ГУН")

        loop = add_block(800, 200, 120, 60, "ФНЧ в\n СВН")
        fp = add_block(1000, 200, 80, 60, "X")

        # ===== ЛЕВАЯ ЧАСТЬ - СТРЕЛКА ОТ D(t) К X =====
        line_start_y = mult[1] + mult[3] / 2
        line_start_x = mult[0] - 60
        scene.addLine(line_start_x, line_start_y, mult[0], line_start_y, pen)
        add_arrow(line_start_x, line_start_y, mult[0], line_start_y)

        d_text = scene.addText("D(t)")
        d_text.setFont(font)
        d_text.setHtml('<span style="font-size:12pt; font-weight:bold;">D(t)</span>')
        d_text.setPos(130, line_start_y - 30)

        # ===== ВЕРТИКАЛЬНАЯ СТРЕЛКА cos (сверху к X) =====
        arrow_start_x = mult[0] + 30
        arrow_start_y = mult[1] + mult[3] + 50
        arrow_end_x = arrow_start_x
        arrow_end_y = mult[1] + mult[3]

        scene.addLine(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y, pen)
        add_arrow(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y)

        cos_text = scene.addText("cos(ω₀t + φ)")
        cos_text.setFont(font)
        cos_text.setHtml('<span style="font-size:12pt; font-weight:bold;">cos(ω₀t + φ)</span>')
        cos_text.setPos(arrow_start_x - 50, arrow_start_y - 0)

        # ===== НОВАЯ ВЕРТИКАЛЬНАЯ СТРЕЛКА n(t) (снизу к каналу) =====
        arrow_start_x_noise = channel[0] + channel[2] / 2  # Центр блока Канал
        arrow_start_y_noise = channel[1] + channel[3] + 50  # Начало снизу от канала
        arrow_end_x_noise = arrow_start_x_noise
        arrow_end_y_noise = channel[1] + channel[3]  # Конец у нижней границы канала

        scene.addLine(arrow_start_x_noise, arrow_start_y_noise, arrow_end_x_noise, arrow_end_y_noise, pen)
        add_arrow(arrow_start_x_noise, arrow_start_y_noise, arrow_end_x_noise, arrow_end_y_noise)

        n_text = scene.addText("n(t)")
        n_text.setFont(font)
        n_text.setHtml('<span style="font-size:12pt; font-weight:bold;">n(t)</span>')
        n_text.setPos(arrow_start_x_noise + 5, arrow_start_y_noise - 30)

        # ===== СТРЕЛКИ МЕЖДУ БЛОКАМИ =====
        # От X к Каналу
        line_y = mult[1] + mult[3] / 2
        scene.addLine(mult[0] + mult[2], line_y, channel[0], line_y, pen)
        add_arrow(mult[0] + mult[2], line_y, channel[0], line_y)

        # От Канала к Полосовому фильтру с подписью y(t)
        line_y = channel[1] + channel[3] / 2
        scene.addLine(channel[0] + channel[2], line_y, bpf[0], line_y, pen)
        add_arrow(channel[0] + channel[2], line_y, bpf[0], line_y)

        # Подпись y(t) над стрелкой между каналом и полосовым фильтром
        mid_x_arrow = (channel[0] + channel[2] + bpf[0]) / 2
        mid_y_arrow = line_y - 35
        y_text = scene.addText("y(t)")
        y_text.setFont(font)
        y_text.setHtml('<span style="font-size:12pt; font-weight:bold;">y(t)</span>')
        y_text.setPos(mid_x_arrow - 15, mid_y_arrow)

        # ===== ВЫХОД r(t) =====
        node_x = bpf[0] + bpf[2]
        node_y = bpf[1] + bpf[3] / 2

        # ===== П-ОБРАЗНАЯ СТРЕЛКА ОТ ПОЛОСОВОГО ФИЛЬТРА К П1 И П2 =====
        branch_x = node_x + 50
        scene.addLine(node_x, node_y, branch_x, node_y, pen)

        scene.addLine(branch_x, node_y, branch_x, p1[1] + p1[3] / 2, pen)
        scene.addLine(branch_x, node_y, branch_x, p2[1] + p2[3] / 2, pen)

        scene.addLine(branch_x, p1[1] + p1[3] / 2, p1[0], p1[1] + p1[3] / 2, pen)
        scene.addLine(branch_x, p2[1] + p2[3] / 2, p2[0], p2[1] + p2[3] / 2, pen)

        add_arrow(branch_x, p1[1] + p1[3] / 2, p1[0], p1[1] + p1[3] / 2)
        add_arrow(branch_x, p2[1] + p2[3] / 2, p2[0], p2[1] + p2[3] / 2)

        r_text = scene.addText("r(t)")
        r_text.setFont(font)
        r_text.setHtml('<span style="font-size:12pt; font-weight:bold;">r(t)</span>')
        r_text.setPos(node_x + 8, node_y - 35)

        # ===== ВЕРХ =====
        arrow_start_x = p1[0] + p1[2]
        arrow_start_y = p1[1] + p1[3] / 2
        arrow_end_x = lpf1[0]
        arrow_end_y = lpf1[1] + lpf1[3] / 2
        scene.addLine(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y, pen)
        add_arrow(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y)

        t_up1 = scene.addText("u<sub>п1</sub>(t)")
        t_up1.setFont(font)
        t_up1.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>п1</sub>(t)</span>')
        t_up1.setPos((arrow_start_x + arrow_end_x) / 2 - 50, (arrow_start_y + arrow_end_y) / 2 - 35)

        # Г-образная стрелка к демодулятору
        mid_x = (arrow_start_x + arrow_end_x) / 2
        mid_y = (arrow_start_y + arrow_end_y) / 2
        scene.addLine(mid_x, mid_y, mid_x, demod[1] + demod[3] / 2, pen)
        scene.addLine(mid_x, demod[1] + demod[3] / 2, demod[0], demod[1] + demod[3] / 2, pen)
        add_arrow(mid_x, demod[1] + demod[3] / 2, demod[0], demod[1] + demod[3] / 2)

        # ===== СТРЕЛКА ИЗ ДЕМОДУЛЯТОРА С ПОДПИСЬЮ d̂(t) =====
        arrow_end_x = demod[0] + demod[2] + 100
        arrow_end_y = demod[1] + demod[3] / 2
        scene.addLine(demod[0] + demod[2], demod[1] + demod[3] / 2, arrow_end_x, arrow_end_y, pen)
        add_arrow(demod[0] + demod[2], demod[1] + demod[3] / 2, arrow_end_x, arrow_end_y)

        d_hat_text = scene.addText("D̂(t)")
        d_hat_text.setFont(font)
        d_hat_text.setHtml('<span style="font-size:12pt; font-weight:bold;">D̂(t)</span>')
        d_hat_text.setPos(arrow_end_x - 70, arrow_end_y - 30)

        # ===== НИЗ =====
        arrow_start_x = p2[0] + p2[2]
        arrow_start_y = p2[1] + p2[3] / 2
        arrow_end_x = lpf2[0]
        arrow_end_y = lpf2[1] + lpf2[3] / 2
        scene.addLine(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y, pen)
        add_arrow(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y)

        t_up2 = scene.addText("u<sub>п2</sub>(t)")
        t_up2.setFont(font)
        t_up2.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>п2</sub>(t)</span>')
        t_up2.setPos((arrow_start_x + arrow_end_x) / 2 - 50, (arrow_start_y + arrow_end_y) / 2 - 35)

        # ===== ГУН К П1 =====
        arrow_start_x = vco[0] + 60
        arrow_start_y = vco[1]
        arrow_end_x = p1[0] + 30
        arrow_end_y = p1[1] + p1[3]
        scene.addLine(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y, pen)
        add_arrow(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y)

        t_ug1 = scene.addText("u<sub>г1</sub>(t)")
        t_ug1.setFont(font)
        t_ug1.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>г1</sub>(t)</span>')
        t_ug1.setPos((arrow_start_x + arrow_end_x) / 2 - 45, (arrow_start_y + arrow_end_y) / 2 - 20)

        # ===== ГУН К П2 =====
        arrow_start_x = vco[0] + 60
        arrow_start_y = vco[1] + vco[3]
        arrow_end_x = p2[0] + 30
        arrow_end_y = p2[1]
        scene.addLine(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y, pen)
        add_arrow(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y)

        t_ug2 = scene.addText("u<sub>г2</sub>(t)")
        t_ug2.setFont(font)
        t_ug2.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>г2</sub>(t)</span>')
        t_ug2.setPos((arrow_start_x + arrow_end_x) / 2 - 45, (arrow_start_y + arrow_end_y) / 2 - 20)

        # ===== ПРАВАЯ ВЕТКА =====
        fp_top_mid_x = fp[0] + fp[2] / 2
        fp_top_mid_y = fp[1]
        scene.addLine(lpf1[0] + lpf1[2], lpf1[1] + lpf1[3] / 2, fp_top_mid_x, lpf1[1] + lpf1[3] / 2, pen)
        scene.addLine(fp_top_mid_x, lpf1[1] + lpf1[3] / 2, fp_top_mid_x, fp_top_mid_y, pen)
        add_arrow(fp_top_mid_x, lpf1[1] + lpf1[3] / 2, fp_top_mid_x, fp_top_mid_y)

        t_uf1 = scene.addText("u<sub>ф1</sub>(t)")
        t_uf1.setFont(font)
        t_uf1.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>ф1</sub>(t)</span>')
        t_uf1.setPos(lpf1[0] + lpf1[2] + 5, lpf1[1] + 25)

        # ===== НИЖНЯЯ ПЕТЛЯ =====
        fp_bottom_mid_x = fp[0] + fp[2] / 2
        fp_bottom_mid_y = fp[1] + fp[3]
        scene.addLine(lpf2[0] + lpf2[2], lpf2[1] + lpf2[3] / 2, fp_bottom_mid_x, lpf2[1] + lpf2[3] / 2, pen)
        scene.addLine(fp_bottom_mid_x, lpf2[1] + lpf2[3] / 2, fp_bottom_mid_x, fp_bottom_mid_y, pen)
        add_arrow(fp_bottom_mid_x, lpf2[1] + lpf2[3] / 2, fp_bottom_mid_x, fp_bottom_mid_y)

        t_uf2 = scene.addText("u<sub>ф2</sub>(t)")
        t_uf2.setFont(font)
        t_uf2.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>ф2</sub>(t)</span>')
        t_uf2.setPos(lpf2[0] + lpf2[2] + 5, lpf2[1] + 25)

        # ===== СТРЕЛКА ОТ X К ФИЛЬТРУ ОС =====
        fp_left_mid_x = fp[0]
        fp_left_mid_y = fp[1] + fp[3] / 2
        loop_right_mid_x = loop[0] + loop[2]
        loop_right_mid_y = loop[1] + loop[3] / 2

        scene.addLine(fp_left_mid_x, fp_left_mid_y, loop_right_mid_x, loop_right_mid_y, pen)
        add_arrow(fp_left_mid_x, fp_left_mid_y, loop_right_mid_x, loop_right_mid_y)

        t_ud = scene.addText("u<sub>д</sub>(t)")
        t_ud.setFont(font)
        t_ud.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>д</sub>(t)</span>')
        t_ud.setPos((fp_left_mid_x + loop_right_mid_x) / 2 - 15, (fp_left_mid_y + loop_right_mid_y) / 2 - 30)

        # ===== СТРЕЛКА ОТ ФИЛЬТРА ОС К ГУН =====
        loop_left_x = loop[0]
        loop_left_y = loop[1] + loop[3] / 2
        vco_right_x = vco[0] + vco[2]
        vco_right_y = vco[1] + vco[3] / 2

        scene.addLine(loop_left_x, loop_left_y, vco_right_x, vco_right_y, pen)
        add_arrow(loop_left_x, loop_left_y, vco_right_x, vco_right_y)

        t_uy = scene.addText("u<sub>y</sub>(t)")
        t_uy.setFont(font)
        t_uy.setHtml('<span style="font-size:12pt; font-weight:bold;">u<sub>y</sub>(t)</span>')
        t_uy.setPos((loop_left_x + vco_right_x) / 2 - 15, (loop_left_y + vco_right_y) / 2 - 30)

        self.scene = scene

    def start_part1(self):
        """Запуск части 1 с глобальными параметрами"""

        # Создаем прогресс-бар
        self.progress_dialog = QProgressDialog("Выполняется расчет части 1...", "Отмена", 0, 0, self)
        self.progress_dialog.setWindowTitle("Расчет")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)  # Убираем кнопку отмены
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Блокируем интерфейс
        self.set_controls_enabled(False)

        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        self.worker = Worker(
            T=sys_params['T'],
            Fs=sys_params['Fs'],
            Fc=sys_params['Fc'],
            bits_per_second=sys_params['bits_per_second'],
            filter_type=filter_params['type'],
            order_mode=filter_params['order_mode'],
            filter_order=filter_params['order'],
            Wp_low=filter_params['Wp_low'],
            Wp_high=filter_params['Wp_high'],
            Ws_low=filter_params['Ws_low'],
            Ws_high=filter_params['Ws_high'],
            gpass=filter_params['gpass'],
            gstop=filter_params['gstop'],
            Gp=pll_params['Gp'],
            Sr=pll_params['Sr'],
            T_lf=pll_params['T_lf'],
            delay_deg=pll_params['delay_deg'],
            noise_params=noise_params,
            carrier_only=self.global_params.is_carrier_only()
        )
        self.worker.finished.connect(self.update_plots_part1)
        self.worker.start()

    def update_plots_part1(self, data):

        self.last_part1_data = data
        self.btn_overlay1.setEnabled(True)

        self.tab_psp.plot(data["t"], data["psp"])
        self.tab_bpsk.plot(data["t"], data["bpsk"])
        self.tab_noisy.plot(data["t"], data["noisy"])
        self.tab_filtered.plot(data["t"], data["filtered"])

        pxx1 = np.where(data["pxx1"] <= 0, 1e-12, data["pxx1"])
        pxx2 = np.where(data["pxx2"] <= 0, 1e-12, data["pxx2"])

        self.tab_spec1.plot(data["f1"], 10 * np.log10(pxx1))
        self.tab_spec2.plot(data["f2"], 10 * np.log10(pxx2))

        # self.tab_out.step_plot(data["t_rec"], data["rec"])
        self.tab_out.update_plot(data["t_rec"], data["rec"], label="")
        self.tab_compare.step_plot(data["t_rec"], data["psp_bits"], ax_index=0, color='blue', label="Вход")
        self.tab_compare.step_plot(data["t_rec"], data["rec"], ax_index=1, color='red', label="Выход")

        self.label_errors.setText(f"Ошибки: {data['errors']} | BER: {data['ber']:.6f}")

        # Закрываем прогресс-бар
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        # Разблокируем интерфейс
        self.set_controls_enabled(True)


    def start_part2(self):
        """Запуск части 2 с глобальными параметрами"""

        # Создаем прогресс-бар
        self.progress_dialog = QProgressDialog("Выполняется расчет части 2...", "Отмена", 0, 0, self)
        self.progress_dialog.setWindowTitle("Расчет")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Блокируем интерфейс
        self.set_controls_enabled(False)

        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        self.worker2 = WorkerPart2(
            T=sys_params['T'],
            Fs=sys_params['Fs'],
            Fc=sys_params['Fc'],
            bits_per_second=sys_params['bits_per_second'],
            noise_params=noise_params,
            filter_type=filter_params['type'],
            order_mode=filter_params['order_mode'],
            filter_order=filter_params['order'],
            Wp_low=filter_params['Wp_low'],
            Wp_high=filter_params['Wp_high'],
            Ws_low=filter_params['Ws_low'],
            Ws_high=filter_params['Ws_high'],
            gpass=filter_params['gpass'],
            gstop=filter_params['gstop'],
            Gp=pll_params['Gp'],
            Sr=pll_params['Sr'],
            T_lf=pll_params['T_lf'],
            delay_deg=pll_params['delay_deg'],
            carrier_only=self.global_params.is_carrier_only()
        )
        self.worker2.finished.connect(self.update_part2)
        self.worker2.start()

    def open_dual_plot_dialog(self):
        """Открывает диалог выбора графиков для построения"""
        if not hasattr(self, 'last_part2_data') or self.last_part2_data is None:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт в части 2!")
            return

        # Список доступных графиков
        graph_names = [
            "Реализация на выходе ФД",
            "Выход перемножителя (Синф.)",
            "Выход перемножителя (Кв.)",
            "Выход ФНЧ (Синф.)",
            "Выход ФНЧ (Кв.)"
        ]

        # Соответствие названий ключам в данных
        graph_keys = {
            "Реализация на выходе ФД": "phase",
            "Выход перемножителя (Синф.)": "mul_sin",
            "Выход перемножителя (Кв.)": "mul_cos",
            "Выход ФНЧ (Синф.)": "lpf_sin",
            "Выход ФНЧ (Кв.)": "lpf_cos"
        }

        dialog = SelectGraphsDialog(graph_names, self)
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.get_selected_graphs()

            if len(selected) != 2:
                QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите ровно два графика!")
                return

            # Получаем данные для выбранных графиков
            data1 = self.last_part2_data[graph_keys[selected[0]]]
            data2 = self.last_part2_data[graph_keys[selected[1]]]
            t = self.last_part2_data["t"]

            # Создаем и показываем окно с двумя графиками
            self.dual_window = DualPlotWindow(
                selected[0], data1,
                selected[1], data2,
                t, self
            )
            self.dual_window.show()

    def update_part2(self, d):
        """Обновление графиков части 2 и сохранение данных"""
        # Сохраняем данные для последующего использования
        self.last_part2_data = d
        self.btn_overlay2.setEnabled(True)

        # График исходной ПСП (синий)
        self.tab_psp2.plot(d["t"], d["psp"], color='blue', linewidth=1.5, label="")



        # Остальные графики
        self.tab_phase.plot(d["t"], d["phase"])
        self.tab_mul_cos.plot(d["t"], d["mul_cos"])
        self.tab_mul_sin.plot(d["t"], d["mul_sin"])
        self.tab_lpf_cos.plot(d["t"], d["lpf_cos"])
        self.tab_lpf_sin.plot(d["t"], d["lpf_sin"])

        # === СПМ перемножителей ===
        self.tab_spec_mul.plot(d["f_mul_cos"], 10 * np.log10(d["pxx_mul_cos"]), ax_index=0)
        ax0 = self.tab_spec_mul.ax[0]
        ax0.set_title("СПМ на выходе перемножителя квадратурного канала")
        ax0.set_xlabel("Частота (Гц)")
        ax0.set_ylabel("")
        ax0.set_xlim(0, 3000)
        ax0.grid(True)

        self.tab_spec_mul.plot(d["f_mul_sin"], 10 * np.log10(d["pxx_mul_sin"]), ax_index=1)
        ax1 = self.tab_spec_mul.ax[1]
        ax1.set_title("СПМ на выходе перемножителя синфазного канала")
        ax1.set_xlabel("Частота (Гц)")
        ax1.set_ylabel("")
        ax1.set_xlim(0, 3000)
        ax1.grid(True)

        # === СПМ ФНЧ ===
        self.tab_spec_lpf.plot(d["f_lpf_cos"], 10 * np.log10(d["pxx_lpf_cos"]), ax_index=0)
        ax2 = self.tab_spec_lpf.ax[0]
        ax2.set_title("СПМ выход ФНЧ квадратурного канала")
        ax2.set_xlabel("Частота (Гц)")
        ax2.set_ylabel("")
        ax2.set_xlim(0, 3000)
        ax2.grid(True)

        self.tab_spec_lpf.plot(d["f_lpf_sin"], 10 * np.log10(d["pxx_lpf_sin"]), ax_index=1)
        ax3 = self.tab_spec_lpf.ax[1]
        ax3.set_title("СПМ выход ФНЧ синфазного канала")
        ax3.set_xlabel("Частота (Гц)")
        ax3.set_ylabel("")
        ax3.set_xlim(0, 3000)
        ax3.grid(True)

        # НОВЫЙ ГРАФИК - ПСП на выходе демодулятора (точки)
        self.tab_demod_out2.update_plot(d["t_rec"], d["rec"], label="")

        self.tab_spec_mul.canvas.draw()
        self.tab_spec_lpf.canvas.draw()

        # Закрываем прогресс-бар
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        # Разблокируем интерфейс
        self.set_controls_enabled(True)

        # # === СРАВНЕНИЕ ПСП (часть 2) - ТОЧКИ вместо ступенек ===
        # # Очищаем оси
        # self.tab_compare2.ax[0].clear()
        # self.tab_compare2.ax[1].clear()
        #
        # # Строим точечные графики (отсчеты)
        # self.tab_compare2.ax[0].scatter(d["t_rec"], d["psp_bits"],
        #                                 color='blue', s=30, label="Входная ПСП", zorder=5)
        # self.tab_compare2.ax[1].scatter(d["t_rec"], d["rec"],
        #                                 color='red', s=30, label="Восстановленная ПСП", zorder=5)
        #
        # # Настраиваем оси
        # self.tab_compare2.ax[0].set_ylabel("Амплитуда")
        # self.tab_compare2.ax[0].grid(True, alpha=0.3)
        # self.tab_compare2.ax[0].legend(loc='best', fontsize=10)
        #
        # self.tab_compare2.ax[1].set_xlabel("Время, с")
        # self.tab_compare2.ax[1].set_ylabel("Амплитуда")
        # self.tab_compare2.ax[1].grid(True, alpha=0.3)
        # self.tab_compare2.ax[1].legend(loc='best', fontsize=10)
        #
        # self.tab_compare2.canvas.draw()

        # === ОТОБРАЖЕНИЕ ОШИБОК И BER ===
        self.label_errors2.setText(f"Ошибки: {d['errors']} | BER: {d['ber']:.6f}")

    def start_part3(self):
        """Запуск части 3 с глобальными параметрами"""

        # Создаем прогресс-бар
        self.progress_dialog = QProgressDialog("Выполняется расчет части 3...", "Отмена", 0, 0, self)
        self.progress_dialog.setWindowTitle("Расчет")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Блокируем интерфейс
        self.set_controls_enabled(False)

        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        self.worker3 = WorkerPart3(
            T=sys_params['T'],
            Fs=sys_params['Fs'],
            Fc=sys_params['Fc'],
            bits_per_second=sys_params['bits_per_second'],
            filter_type=filter_params['type'],
            order_mode=filter_params['order_mode'],
            filter_order=filter_params['order'],
            Wp_low=filter_params['Wp_low'],
            Wp_high=filter_params['Wp_high'],
            Ws_low=filter_params['Ws_low'],
            Ws_high=filter_params['Ws_high'],
            gpass=filter_params['gpass'],
            gstop=filter_params['gstop'],
            Gp=pll_params['Gp'],
            Sr=pll_params['Sr'],
            T_lf=pll_params['T_lf'],
            delay_deg=pll_params['delay_deg'],
            noise_params=noise_params,
            dphi=self.dphi.value(),
            carrier_only=self.global_params.is_carrier_only()
        )
        self.worker3.finished.connect(self.update_part3)
        self.worker3.start()
        self.btn_psd.setEnabled(False)

    def update_part3(self, d):

        self.last_part3_data = d  # Сохраните данные
        # self.btn_overlay3.setEnabled(True)

        if hasattr(self.worker3, 'last_VCO_out'):
            self.last_vco_signal = self.worker3.last_VCO_out
            self.last_fs = self.worker3.last_Fs
            self.btn_psd.setEnabled(True)

        self.tab_psp3.plot(d["t"], d["psp"], color='blue', linewidth=1.5, label="")

        # Выходная ПСП (точки/отсчеты)
        self.tab_demod_out3.update_plot(d["t_rec"], d["rec"], label="")

        # Обновляем объединенный график ФНЧ (синфазный и квадратурный)
        # Верхний график (ax_index=0) - синфазный (sin)
        # Нижний график (ax_index=1) - квадратурный (cos)
        self.tab_lpf_combined.plot(d["t"], d["lpf_sin"], ax_index=0, color='red', label="Синфазный канал")
        self.tab_lpf_combined.plot(d["t"], d["lpf_cos"], ax_index=1, color='blue', label="Квадратурный канал")

        # Добавляем легенды для каждого подграфика
        self.tab_lpf_combined.ax[0].legend(loc='best', fontsize=10)
        self.tab_lpf_combined.ax[1].legend(loc='best', fontsize=10)

        # Обновляем отдельный график ФД
        self.tab_phase3.plot(d["t"], d["phase"])

        # ===== ДОБАВЬТЕ ЭТОТ БЛОК =====
        # Отображение ошибок и BER
        if "errors" in d and "ber" in d:
            self.label_ber3.setText(f"Ошибки: {d['errors']} | BER: {d['ber']:.6f}")
            if d['errors'] > 0:
                self.label_ber3.setStyleSheet(
                    "font-size: 14px; font-weight: bold; color: red; background-color: #ffe0e0; padding: 5px; border-radius: 5px;")
            else:
                self.label_ber3.setStyleSheet(
                    "font-size: 14px; font-weight: bold; color: green; background-color: #e0ffe0; padding: 5px; border-radius: 5px;")

        # Закрываем прогресс-бар
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        # Разблокируем интерфейс
        self.set_controls_enabled(True)

    def compute_psd_only(self):
        """Отдельный расчёт СПМ с текущим значением transition"""
        if self.last_vco_signal is None:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните основной расчёт")
            return

        # Создаем прогресс-бар
        self.psd_progress = QProgressDialog("Выполняется расчет СПМ...", "Отмена", 0, 0, self)
        self.psd_progress.setWindowTitle("Расчет спектра")
        self.psd_progress.setWindowModality(Qt.WindowModal)
        self.psd_progress.setCancelButton(None)  # Убираем кнопку отмены
        self.psd_progress.setMinimumDuration(0)
        self.psd_progress.show()

        # Блокируем кнопку построения СПМ
        self.btn_psd.setEnabled(False)
        self.btn_psd.setText("Расчёт СПМ...")

        self.psd_worker = PSDWorker(
            self.last_vco_signal,
            self.last_fs,
            self.transition.value()
        )
        self.psd_worker.finished.connect(self.update_psd)
        self.psd_worker.start()



    # def update_psd(self, d):
    #     self.tab_vco_spec.plot(d["f_vco"], d["pxx_vco"])
    #     self.btn_psd.setText("Построить СПМ")
    #     self.btn_psd.setEnabled(True)
    def update_psd(self, d):
        """Обновляет график СПМ с правильной размерностью по оси X"""
        # Очищаем текущую ось
        self.tab_vco_spec.ax.clear()

        # Строим график с частотой по оси X
        self.tab_vco_spec.ax.plot(d["f_vco"], d["pxx_vco"], color='blue', linewidth=1.5)

        # Настраиваем подписи осей
        self.tab_vco_spec.ax.set_xlabel("Частота, Гц", fontsize=12)
        self.tab_vco_spec.ax.set_ylabel("Спектральная плотность, дБ", fontsize=12)
        self.tab_vco_spec.ax.set_title("СПМ на выходе ГУН (без переходного процесса)", fontsize=14)
        self.tab_vco_spec.ax.grid(True, alpha=0.3)

        # Обновляем canvas
        self.tab_vco_spec.canvas.draw()

        # Закрываем прогресс-бар
        if hasattr(self, 'psd_progress'):
            self.psd_progress.close()

        # Восстанавливаем кнопку
        self.btn_psd.setText("Построить СПМ")
        self.btn_psd.setEnabled(True)

    def start_part4(self):
        """Запуск части 4 с глобальными параметрами"""
        # Создаем прогресс-бар
        self.progress_dialog = QProgressDialog("Выполняется расчет части 4...", "Отмена", 0, 0, self)
        self.progress_dialog.setWindowTitle("Расчет")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Блокируем интерфейс
        self.set_controls_enabled(False)

        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        self.worker4 = WorkerPart4(
            T=sys_params['T'],
            Fs=sys_params['Fs'],
            Fc=sys_params['Fc'],
            bits_per_second=sys_params['bits_per_second'],
            filter_type=filter_params['type'],
            order_mode=filter_params['order_mode'],
            filter_order=filter_params['order'],
            Wp_low=filter_params['Wp_low'],
            Wp_high=filter_params['Wp_high'],
            Ws_low=filter_params['Ws_low'],
            Ws_high=filter_params['Ws_high'],
            gpass=filter_params['gpass'],
            gstop=filter_params['gstop'],
            Gp=pll_params['Gp'],
            Sr=pll_params['Sr'],
            T_lf=pll_params['T_lf'],
            delay_deg=pll_params['delay_deg'],
            noise_params=noise_params,
            freq_offset=self.freq_offset.value(),
            carrier_only=self.global_params.is_carrier_only()
        )
        self.worker4.finished.connect(self.update_part4)
        self.worker4.start()
        self.btn_psd4.setEnabled(False)

    def run_ber_vs_freq_scan(self):
        """Автоматический прогон для разных значений частотной расстройки Δf с измерением BER"""

        # Создаем диалоговое окно с прогрессом
        progress_dialog = QProgressDialog("Выполняется сканирование частоты...", "Отмена", 0, 100, self)
        progress_dialog.setWindowTitle("Анализ BER от Δf")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)

        # Параметры сканирования (частота в Гц)
        # freq_values = np.arange(-100, 101, 20)  # от -100 до 100 Гц с шагом 20 Гц
        freq_values = np.arange(-100, 101, 25)  # от -100 до 100 Гц с шагом 25 Гц

        ber_results = []
        error_results = []

        # Получаем текущие параметры из глобальных настроек
        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        # Сохраняем текущее значение частотной расстройки
        original_freq = self.freq_offset.value()

        total = len(freq_values)

        for idx, freq_offset in enumerate(freq_values):
            # Обновляем прогресс
            progress_dialog.setValue(int((idx + 1) / total * 100))
            progress_dialog.setLabelText(f"Измерение BER для Δf = {freq_offset:+d} Гц...")

            if progress_dialog.wasCanceled():
                break

            # Устанавливаем значение частоты
            self.freq_offset.setValue(freq_offset)

            # Создаем и запускаем воркер
            worker = WorkerPart4(
                T=sys_params['T'],
                Fs=sys_params['Fs'],
                Fc=sys_params['Fc'],
                bits_per_second=sys_params['bits_per_second'],
                filter_type=filter_params['type'],
                order_mode=filter_params['order_mode'],
                filter_order=filter_params['order'],
                Wp_low=filter_params['Wp_low'],
                Wp_high=filter_params['Wp_high'],
                Ws_low=filter_params['Ws_low'],
                Ws_high=filter_params['Ws_high'],
                gpass=filter_params['gpass'],
                gstop=filter_params['gstop'],
                Gp=pll_params['Gp'],
                Sr=pll_params['Sr'],
                T_lf=pll_params['T_lf'],
                delay_deg=pll_params['delay_deg'],
                noise_params=noise_params,
                freq_offset=freq_offset,
                carrier_only=self.global_params.is_carrier_only()
            )

            # Используем событие для синхронного ожидания
            result_container = {}
            event = QtCore.QEventLoop()

            def on_finished(data):
                result_container['data'] = data
                event.quit()

            worker.finished.connect(on_finished)
            worker.start()
            event.exec()

            if 'data' in result_container:
                data = result_container['data']
                ber_results.append(data['ber'])
                error_results.append(data['errors'])
            else:
                ber_results.append(1.0)
                error_results.append(0)

            # Даем немного времени на обновление GUI
            QApplication.processEvents()

        # Восстанавливаем исходное значение частоты
        self.freq_offset.setValue(original_freq)
        progress_dialog.close()

        # Строим график результатов
        self.plot_ber_vs_freq(freq_values[:len(ber_results)], ber_results, error_results)

    def plot_ber_vs_freq(self, freq_values, ber_results, error_results):
        """Строит график зависимости BER от частотной расстройки"""

        dialog = QDialog(self)
        dialog.setWindowTitle("Зависимость BER от частотной расстройки Δf")
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        # Создаем фигуру с двумя подграфиками
        figure = Figure(figsize=(10, 8))
        canvas = FigureCanvas(figure)
        toolbar = NavigationToolbar(canvas, dialog)

        ax1 = figure.add_subplot(211)
        ax2 = figure.add_subplot(212)

        # График BER
        ax1.semilogy(freq_values, ber_results, 'bo-', linewidth=2, markersize=8, label='BER')
        ax1.set_xlabel("Частотная расстройка Δf, Гц")
        ax1.set_ylabel("Bit Error Rate (BER)")
        ax1.set_title("Зависимость BER от частотной расстройки")
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([1e-6, 1])
        ax1.legend()

        # Добавляем отметку для Δf = 0
        for i, (freq, ber) in enumerate(zip(freq_values, ber_results)):
            if freq == 0:
                ax1.annotate(f'Δf=0, BER={ber:.6f}', (freq, ber),
                             xytext=(freq + 10, ber * 10),
                             arrowprops=dict(arrowstyle='->', color='green'),
                             fontsize=9)

        # График количества ошибок
        bar_width = freq_values[1] - freq_values[0] if len(freq_values) > 1 else 10
        ax2.bar(freq_values, error_results, width=bar_width,
                color='red', alpha=0.7, label='Ошибки')
        ax2.set_xlabel("Частотная расстройка Δf, Гц")
        ax2.set_ylabel("Количество ошибок")
        ax2.set_title("Количество ошибочных бит")
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        figure.tight_layout()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        # Кнопка закрытия
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        # Добавляем информационную панель
        info_text = QTextEdit()
        info_text.setMaximumHeight(150)
        info_text.setReadOnly(True)

        info = "Результаты измерения BER:\n"
        info += "=" * 60 + "\n"
        info += f"{'Δf, Гц':<12} {'BER':<12} {'Ошибки':<10}\n"
        info += "-" * 60 + "\n"

        # ИСПРАВЛЕНО: используем np.argmin() вместо index()
        min_ber_idx = np.argmin(ber_results)
        min_ber = ber_results[min_ber_idx]
        min_ber_freq = freq_values[min_ber_idx]

        for freq, ber, errors in zip(freq_values, ber_results, error_results):
            if ber == 0:
                ber_str = "0 (идеально)"
            elif ber < 0.001:
                ber_str = f"{ber:.2e}"
            else:
                ber_str = f"{ber:.6f}"
            info += f"{freq:+d}{' ':<8} {ber_str:<12} {errors:<10}\n"

        # Добавляем анализ
        info += "\n" + "=" * 60 + "\n"
        info += "Анализ результатов:\n"
        info += f"✓ Минимальный BER ({min_ber:.6f}) при Δf = {min_ber_freq:+d} Гц\n"

        # Находим полосу захвата (где BER < 0.01)
        lock_range = []
        for freq, ber in zip(freq_values, ber_results):
            if ber < 0.01:
                lock_range.append(freq)

        if lock_range:
            info += f"✓ Полоса захвата СВН (BER < 0.01): от {min(lock_range):+d} до {max(lock_range):+d} Гц\n"

        # Находим максимальный BER
        max_ber_idx = np.argmax(ber_results)
        info += f"✗ Максимальный BER при Δf = {freq_values[max_ber_idx]:+d} Гц (BER = {ber_results[max_ber_idx]:.6f})\n"

        info_text.setText(info)
        layout.addWidget(info_text)

        dialog.exec()

    def run_multiple_freq_measurements(self, num_runs=10, freq_step=25):
        """Запускает несколько измерений для усреднения BER по частоте"""

        # Создаем диалог с параметрами
        dialog = QDialog(self)
        dialog.setWindowTitle("Многократные измерения BER по частоте")
        dialog.setModal(True)
        dialog.resize(400, 250)

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        num_runs_spin = QSpinBox()
        num_runs_spin.setRange(1, 50)
        num_runs_spin.setValue(num_runs)
        num_runs_spin.setSuffix(" запусков")

        freq_step_spin = QSpinBox()
        freq_step_spin.setRange(10, 100)
        freq_step_spin.setValue(freq_step)
        freq_step_spin.setSuffix(" Гц")
        freq_step_spin.setSingleStep(10)

        form_layout.addRow("Количество измерений для каждой частоты:", num_runs_spin)
        form_layout.addRow("Шаг по частоте:", freq_step_spin)

        layout.addLayout(form_layout)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() != QDialog.Accepted:
            return

        num_runs = num_runs_spin.value()
        freq_step = freq_step_spin.value()

        # Параметры сканирования
        freq_values = np.arange(-200, 201, 50)

        # Массивы для усредненных результатов
        avg_ber = np.zeros(len(freq_values))
        avg_errors = np.zeros(len(freq_values))

        # Прогресс бар
        progress = QProgressDialog(f"Выполняется {num_runs} измерений для каждой частоты...", "Отмена",
                                   0, len(freq_values) * num_runs, self)
        progress.setWindowTitle("Многократные измерения BER")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        # Получаем параметры
        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        original_freq = self.freq_offset.value()
        current_run = 0

        for f_idx, freq_offset in enumerate(freq_values):
            ber_sum = 0
            errors_sum = 0

            for run in range(num_runs):
                progress.setValue(current_run)
                progress.setLabelText(f"Δf = {freq_offset:+d} Гц, измерение {run + 1}/{num_runs}...")

                if progress.wasCanceled():
                    break

                # Создаем и запускаем воркер
                worker = WorkerPart4(
                    T=sys_params['T'],
                    Fs=sys_params['Fs'],
                    Fc=sys_params['Fc'],
                    bits_per_second=sys_params['bits_per_second'],
                    filter_type=filter_params['type'],
                    order_mode=filter_params['order_mode'],
                    filter_order=filter_params['order'],
                    Wp_low=filter_params['Wp_low'],
                    Wp_high=filter_params['Wp_high'],
                    Ws_low=filter_params['Ws_low'],
                    Ws_high=filter_params['Ws_high'],
                    gpass=filter_params['gpass'],
                    gstop=filter_params['gstop'],
                    Gp=pll_params['Gp'],
                    Sr=pll_params['Sr'],
                    T_lf=pll_params['T_lf'],
                    delay_deg=pll_params['delay_deg'],
                    noise_params=noise_params,
                    freq_offset=freq_offset
                )

                result_container = {}
                event = QtCore.QEventLoop()

                def on_finished(data):
                    result_container['data'] = data
                    event.quit()

                worker.finished.connect(on_finished)
                worker.start()
                event.exec()

                if 'data' in result_container:
                    data = result_container['data']
                    ber_sum += data['ber']
                    errors_sum += data['errors']

                current_run += 1
                QApplication.processEvents()

            if progress.wasCanceled():
                break

            avg_ber[f_idx] = ber_sum / num_runs
            avg_errors[f_idx] = errors_sum / num_runs

        progress.close()
        self.freq_offset.setValue(original_freq)

        # Строим график усредненных результатов
        self.plot_ber_vs_freq(freq_values[:len(avg_ber)], avg_ber, avg_errors)

    def update_part4(self, d):
        # Сохраняем данные для последующего использования
        self.last_part4_data = d

        if hasattr(self.worker4, 'last_VCO_out'):
            self.last_vco_signal4 = self.worker4.last_VCO_out
            self.last_fs4 = self.worker4.last_Fs
            self.btn_psd4.setEnabled(True)

        # НОВЫЕ ГРАФИКИ ПСП
        self.tab_psp4.plot(d["t"], d["psp"], color='blue', linewidth=1.5, label="")

        if "rec" in d and "t_rec" in d:
            self.tab_demod_out4.update_plot(d["t_rec"], d["rec"], label="")

        # Обновляем объединенный график ФНЧ
        self.tab4_lpf_combined.plot(d["t"], d["lpf_sin"], ax_index=0, color='red', label="Синфазный канал")
        self.tab4_lpf_combined.plot(d["t"], d["lpf_cos"], ax_index=1, color='blue', label="Квадратурный канал")

        self.tab4_lpf_combined.ax[0].legend(loc='best', fontsize=10)
        self.tab4_lpf_combined.ax[1].legend(loc='best', fontsize=10)

        # Обновляем отдельный график ФД
        self.tab4_phase.plot(d["t"], d["phase"])

        # Отображение ошибок и BER
        if "errors" in d and "ber" in d:
            self.label_ber4.setText(f"Ошибки: {d['errors']} | BER: {d['ber']:.6f}")
            if d['errors'] > 0:
                self.label_ber4.setStyleSheet(
                    "font-size: 14px; font-weight: bold; color: red; background-color: #ffe0e0; padding: 5px; border-radius: 5px;")
            else:
                self.label_ber4.setStyleSheet(
                    "font-size: 14px; font-weight: bold; color: green; background-color: #e0ffe0; padding: 5px; border-radius: 5px;")

        # Закрываем прогресс-бар
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
        # Разблокируем интерфейс
        self.set_controls_enabled(True)

    def compute_psd_only4(self):
        """Отдельный расчёт СПМ с учетом сдвига частоты"""
        if not hasattr(self, 'last_vco_signal4') or self.last_vco_signal4 is None:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните основной расчёт")
            return

        # Создаем прогресс-бар
        self.psd_progress4 = QProgressDialog("Выполняется расчет СПМ...", "Отмена", 0, 0, self)
        self.psd_progress4.setWindowTitle("Расчет спектра")
        self.psd_progress4.setWindowModality(Qt.WindowModal)
        self.psd_progress4.setCancelButton(None)  # Убираем кнопку отмены
        self.psd_progress4.setMinimumDuration(0)
        self.psd_progress4.show()

        # Блокируем кнопку построения СПМ
        self.btn_psd4.setEnabled(False)
        self.btn_psd4.setText("Расчёт СПМ...")

        # Получаем значение сдвига частоты
        freq_offset = self.freq_offset.value()

        # Создаем аналитический сигнал (как в 3 части)
        from scipy.signal import hilbert
        vco_analytic = hilbert(self.last_vco_signal4)

        # Сдвигаем по частоте (как в 3 части)
        t = np.arange(len(self.last_vco_signal4)) / self.last_fs4
        vco_shifted = np.real(vco_analytic * np.exp(1j * 2 * np.pi * freq_offset * t))

        # Рассчитываем СПМ как в 3 части
        transition_samples = int(self.transition4.value() * self.last_fs4)
        if transition_samples >= len(vco_shifted) - 1000:
            transition_samples = 0

        signal_trim = vco_shifted[transition_samples:]

        # Обновляем прогресс (50%)
        if hasattr(self, 'psd_progress4'):
            self.psd_progress4.setLabelText("Вычисление спектральной плотности мощности...")

        # Небольшая задержка для обновления GUI
        QApplication.processEvents()

        if len(signal_trim) >= 1024:
            f, Pxx = signal.periodogram(
                signal_trim,
                fs=self.last_fs4,
                window='boxcar',
                nfft=len(signal_trim),
                detrend=False,
                scaling='density'
            )
            Pxx_db = 10 * np.log10(Pxx + 1e-20)

            # Обновляем прогресс (90%)
            if hasattr(self, 'psd_progress4'):
                self.psd_progress4.setLabelText("Построение графика...")
            QApplication.processEvents()

            # Обновляем график как в 3 части
            self.tab4_spec.ax.clear()
            self.tab4_spec.ax.plot(f, Pxx_db, color='blue', linewidth=1.5)
            self.tab4_spec.ax.set_xlabel("Частота, Гц", fontsize=12)
            self.tab4_spec.ax.set_ylabel("Спектральная плотность, дБ", fontsize=12)
            self.tab4_spec.ax.set_title("СПМ на выходе ГУН (без переходного процесса)", fontsize=14)
            self.tab4_spec.ax.grid(True, alpha=0.3)
            self.tab4_spec.canvas.draw()

            # Закрываем прогресс-бар
            if hasattr(self, 'psd_progress4'):
                self.psd_progress4.close()

        self.btn_psd4.setText("Построить СПМ")
        self.btn_psd4.setEnabled(True)

    def update_psd4(self, d):
        self.tab4_spec.plot(d["f_vco"], d["pxx_vco"])
        self.btn_psd4.setText("Построить СПМ")
        self.btn_psd4.setEnabled(True)

    def start_part5(self):
        """Запускает расчет дискриминационной характеристики"""
        phase_min = self.phase_min.value()
        phase_max = self.phase_max.value()
        phase_step = self.phase_step.value()

        if phase_min >= phase_max:
            QMessageBox.warning(self, "Ошибка", "Минимальное значение должно быть меньше максимального!")
            return

        if phase_step <= 0:
            QMessageBox.warning(self, "Ошибка", "Шаг должен быть положительным!")
            return

        # Создаем прогресс-бар
        self.progress_dialog = QProgressDialog("Выполняется расчет дискриминационной характеристики...", "Отмена",
                                                 0, 0, self)
        self.progress_dialog.setWindowTitle("Расчет")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Блокируем интерфейс
        self.set_controls_enabled(False)
        self.worker5 = WorkerPart5(phase_min, phase_max, phase_step)
        self.worker5.finished.connect(self.update_part5)
        self.worker5.start()

    def update_part5(self, data):
        """Обновляет график дискриминационной характеристики"""
        self.ax5.clear()
        self.ax5.plot(data["phase_diff"], data["output"], color='blue', linewidth=1.5)
        self.ax5.set_title("Дискриминационная характеристика", fontsize=14)
        self.ax5.set_xlabel("Рассогласование по фазе, град.", fontsize=12)
        self.ax5.set_ylabel("Выход дискриминатора", fontsize=12)
        self.ax5.grid(True, alpha=0.3)
        self.canvas5.draw()

        # Закрываем прогресс-бар
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        # Разблокируем интерфейс
        self.set_controls_enabled(True)

    def set_controls_enabled(self, enabled):
        """Блокирует/разблокирует все кнопки запуска расчетов"""
        # Часть 1
        self.btn_part1.setEnabled(enabled)
        self.btn_overlay1.setEnabled(enabled and hasattr(self, 'last_part1_data'))

        # Часть 2
        self.btn_part2.setEnabled(enabled)
        self.btn_dual_plot.setEnabled(enabled and hasattr(self, 'last_part2_data'))
        self.btn_overlay2.setEnabled(enabled and hasattr(self, 'last_part2_data'))

        # Часть 3
        self.btn3.setEnabled(enabled)
        self.btn_psd.setEnabled(enabled and hasattr(self, 'last_vco_signal'))
        self.btn_overlay3.setEnabled(enabled and hasattr(self, 'last_part3_data'))
        self.dphi.setEnabled(enabled)

        # Часть 4
        self.btn4.setEnabled(enabled)
        self.btn_psd4.setEnabled(enabled and hasattr(self, 'last_vco_signal4'))
        self.btn_overlay4.setEnabled(enabled and hasattr(self, 'last_part4_data'))
        self.freq_offset.setEnabled(enabled)
        self.btn_scan_freq.setEnabled(enabled)
        self.btn_multirun_freq.setEnabled(enabled)

        # Часть 5
        self.btn5.setEnabled(enabled)
        self.phase_min.setEnabled(enabled)
        self.phase_max.setEnabled(enabled)
        self.phase_step.setEnabled(enabled)

        # Глобальные параметры - блокируем все вкладки
        self.global_params.params_tabs.setEnabled(enabled)

    def test_part1_phase_sensitivity(self):
        """Тестирует зависимость BER от фазового сдвига в части 1 (без СВН)"""

        # Создаем диалог с прогрессом
        progress_dialog = QProgressDialog("Тестирование чувствительности к фазе...", "Отмена", 0, 100, self)
        progress_dialog.setWindowTitle("Тест части 1")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)

        # Параметры тестирования
        phase_values = np.arange(0, 181, 15)  # от 0 до 180 с шагом 15°

        ber_results = []
        error_results = []

        # Получаем текущие параметры
        sys_params = self.global_params.get_system_params()
        noise_params = self.global_params.get_noise_params()
        filter_params = self.global_params.get_filter_params()
        pll_params = self.global_params.get_pll_params()

        # Сохраняем исходное значение delay_deg
        original_delay = pll_params['delay_deg']

        total = len(phase_values)

        for idx, phase_shift in enumerate(phase_values):
            progress_dialog.setValue(int((idx + 1) / total * 100))
            progress_dialog.setLabelText(f"Тест для фазового сдвига = {phase_shift}°...")

            if progress_dialog.wasCanceled():
                break

            # Создаем worker с новым значением delay_deg
            worker = Worker(
                T=sys_params['T'],
                Fs=sys_params['Fs'],
                Fc=sys_params['Fc'],
                bits_per_second=sys_params['bits_per_second'],
                filter_type=filter_params['type'],
                order_mode=filter_params['order_mode'],
                filter_order=filter_params['order'],
                Wp_low=filter_params['Wp_low'],
                Wp_high=filter_params['Wp_high'],
                Ws_low=filter_params['Ws_low'],
                Ws_high=filter_params['Ws_high'],
                gpass=filter_params['gpass'],
                gstop=filter_params['gstop'],
                Gp=pll_params['Gp'],
                Sr=pll_params['Sr'],
                T_lf=pll_params['T_lf'],
                delay_deg=phase_shift,  # ← изменяем фазу гетеродина
                noise_params=noise_params,
                carrier_only=self.global_params.is_carrier_only()
            )

            result_container = {}
            event = QtCore.QEventLoop()

            def on_finished(data):
                result_container['data'] = data
                event.quit()

            worker.finished.connect(on_finished)
            worker.start()
            event.exec()

            if 'data' in result_container:
                data = result_container['data']
                ber_results.append(data['ber'])
                error_results.append(data['errors'])
            else:
                ber_results.append(1.0)
                error_results.append(0)

            QApplication.processEvents()

        # Восстанавливаем исходное значение
        # Обновляем параметры в глобальном виджете
        self.global_params.pll_params.delay_deg.setValue(original_delay)

        progress_dialog.close()

        # Строим график результатов
        self.plot_part1_phase_test(phase_values[:len(ber_results)], ber_results, error_results)

    def plot_part1_phase_test(self, phase_values, ber_results, error_results):
        """Строит график зависимости BER от фазового сдвига (часть 1)"""

        dialog = QDialog(self)
        dialog.setWindowTitle("Часть 1: Зависимость BER от фазового сдвига (без СВН)")
        dialog.resize(900, 650)

        layout = QVBoxLayout(dialog)

        figure = Figure(figsize=(10, 8))
        canvas = FigureCanvas(figure)
        toolbar = NavigationToolbar(canvas, dialog)

        ax1 = figure.add_subplot(211)
        ax2 = figure.add_subplot(212)

        # График BER
        ax1.semilogy(phase_values, ber_results, 'ro-', linewidth=2, markersize=8, label='BER')
        ax1.set_xlabel("Фазовый сдвиг гетеродина Δθ, град.")
        ax1.set_ylabel("Bit Error Rate (BER)")
        ax1.set_title("Часть 1: Зависимость BER от фазы гетеродина (без СВН)", fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([1e-6, 1])
        ax1.legend()

        # Отмечаем особые точки
        for phase, ber in zip(phase_values, ber_results):
            if ber < 0.01 and ber > 0:
                ax1.annotate(f'{phase}°', (phase, ber),
                             xytext=(phase, ber * 10),
                             arrowprops=dict(arrowstyle='->', color='green'),
                             fontsize=8)
            elif ber > 0.4:
                ax1.annotate(f'{phase}°\nBER≈{ber:.3f}', (phase, ber),
                             xytext=(phase + 10, ber),
                             arrowprops=dict(arrowstyle='->', color='red'),
                             fontsize=8)

        # График ошибок
        ax2.bar(phase_values, error_results, width=12, color='red', alpha=0.7, label='Ошибки')
        ax2.set_xlabel("Фазовый сдвиг гетеродина Δθ, град.")
        ax2.set_ylabel("Количество ошибок")
        ax2.set_title("Количество ошибочных бит")
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        figure.tight_layout()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)

        # Информационная панель
        info_text = QTextEdit()
        info_text.setMaximumHeight(180)
        info_text.setReadOnly(True)

        info = "=" * 70 + "\n"
        info += "РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ЧАСТИ 1 (демодулятор БЕЗ СВН)\n"
        info += "=" * 70 + "\n\n"

        info += "Теоретическое ожидание:\n"
        info += "  • BER = cos²(Δθ) - зависимость от фазы\n"
        info += "  • При Δθ = 90° → сигнал пропадает (BER ≈ 0.5)\n"
        info += "  • При Δθ = 180° → инверсия битов (BER ≈ 0.5)\n\n"

        info += "Результаты измерений:\n"
        info += "-" * 70 + "\n"
        info += f"{'Δθ, град.':<12} {'BER':<12} {'Ошибки':<10} {'Статус':<20}\n"
        info += "-" * 70 + "\n"

        best_phase = None
        best_ber = 1.0

        for phase, ber, errors in zip(phase_values, ber_results, error_results):
            if ber == 0:
                status = "✅ ИДЕАЛЬНО"
                if best_ber > ber:
                    best_ber = ber
                    best_phase = phase
            elif ber < 0.01:
                status = "✅ Хорошо"
                if best_ber > ber:
                    best_ber = ber
                    best_phase = phase
            elif ber < 0.1:
                status = "⚠️ Удовлетворительно"
            elif ber < 0.4:
                status = "⚠️ Плохо"
            else:
                status = "❌ НЕ РАБОТАЕТ"

            ber_str = "0" if ber == 0 else f"{ber:.6f}"
            info += f"{phase:<12} {ber_str:<12} {errors:<10} {status:<20}\n"

        info += "-" * 70 + "\n\n"

        info += "АНАЛИЗ:\n"
        info += f"  • Оптимальная фаза: {best_phase}° (BER = {best_ber:.6f})\n"

        # Находим зоны неработоспособности
        dead_zones = []
        for phase, ber in zip(phase_values, ber_results):
            if ber > 0.4:
                dead_zones.append(phase)

        if dead_zones:
            info += f"  • Зоны неработоспособности (BER > 0.4): {dead_zones}°\n"
            if 90 in phase_values:
                idx_90 = np.where(phase_values == 90)[0][0]
                info += f"  • При Δθ = 90° сигнал пропадает! ({ber_results[idx_90]:.4f})\n"
            else:
                info += f"  • При Δθ = 90° сигнал должен пропадать (в измерениях нет)\n"

        info += "\nВЫВОД:\n"
        info += "  Демодулятор без СВН критически зависит от фазы гетеродина.\n"
        info += "  При фазовом рассогласовании 90° связь полностью пропадает.\n"
        info += "  При 180° происходит инверсия битов.\n"
        info += "  Это доказывает необходимость использования СВН в реальных системах.\n"

        info_text.setText(info)
        layout.addWidget(info_text)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(dialog.accept)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(btn_close)

        dialog.exec()

    def compare_with_theory(self):
        """Сравнивает экспериментальные результаты с теорией"""

        # Теоретическая зависимость BER от фазы
        phase_theory = np.arange(0, 181, 5)
        # Для BPSK: BER = 0.5 * erfc(sqrt(Eb/N0) * |cos(Δθ)|)
        # Упрощенно: BER ~ 0 при cos²(Δθ) > порога, иначе 0.5
        ber_theory = []

        for phase in phase_theory:
            # Нормированная амплитуда сигнала = |cos(phase_rad)|
            amplitude = abs(np.cos(np.deg2rad(phase)))
            if amplitude > 0.3:  # условный порог
                ber_theory.append(0)
            else:
                ber_theory.append(0.5)

        # Получаем экспериментальные данные из последнего теста
        if hasattr(self, '_last_phase_test_results'):
            exp_phases, exp_bers = self._last_phase_test_results

            # Строим график сравнения
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(phase_theory, ber_theory, 'b--', linewidth=2, label='Теория (упрощенно)')
            ax.plot(exp_phases, exp_bers, 'ro-', linewidth=2, markersize=8, label='Эксперимент')
            ax.set_xlabel("Фазовый сдвиг Δθ, град.")
            ax.set_ylabel("BER")
            ax.set_title("Сравнение теории и эксперимента (демодулятор без СВН)")
            ax.grid(True, alpha=0.3)
            ax.legend()
            ax.set_ylim([-0.05, 1.05])

            plt.show()



class SelectGraphsDialog(QDialog):
    """Диалоговое окно для выбора двух графиков для построения"""

    def __init__(self, graph_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите два графика для построения")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Инструкция
        label = QLabel("Выберите два графика для отображения:")
        label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(label)

        # Список графиков с чекбоксами
        self.checkboxes = []
        for name in graph_names:
            cb = QCheckBox(name)
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        # Кнопки
        button_layout = QHBoxLayout()

        self.btn_build = QPushButton("Построить")
        self.btn_build.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_build.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)

        button_layout.addWidget(self.btn_build)
        button_layout.addWidget(self.btn_cancel)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_selected_graphs(self):
        """Возвращает список выбранных названий графиков"""
        selected = []
        for cb in self.checkboxes:
            if cb.isChecked():
                selected.append(cb.text())
        return selected


class DualPlotWindow(QMainWindow):
    """Окно для отображения двух выбранных графиков"""

    def __init__(self, title1, data1, title2, data2, t, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Сравнение графиков: {title1} и {title2}")

        central_widget = QWidget()
        layout = QVBoxLayout()

        # Создаем фигуру с двумя подграфиками
        self.figure = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Создаем два подграфика один под другим
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212, sharex=self.ax1)

        # Строим графики
        self.ax1.plot(t, data1, color='blue', linewidth=1.5)
        self.ax1.set_title(title1, fontsize=12)
        # self.ax1.set_ylabel("Амплитуда", fontsize=10)
        self.ax1.grid(True, alpha=0.3)

        self.ax2.plot(t, data2, color='red', linewidth=1.5)
        self.ax2.set_title(title2, fontsize=12)
        self.ax2.set_xlabel("Время, с", fontsize=10)
        # self.ax2.set_ylabel("Амплитуда", fontsize=10)
        self.ax2.grid(True, alpha=0.3)

        self.figure.tight_layout()

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.resize(900, 700)


# ---------- Запуск приложения
# ---------- Запуск приложения
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # Принудительно устанавливаем светлую тему
    app.setStyle('Fusion')

    # Создаём палитру для светлой темы
    palette = QtGui.QPalette()

    # Цвета для светлой темы
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.black)
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(245, 245, 245))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.black)
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(240, 240, 240))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.black)
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(0, 120, 215))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.white)

    # Устанавливаем палитру
    app.setPalette(palette)

    # Дополнительные стили для улучшения внешнего вида
    app.setStyleSheet("""
        QToolTip {
            background-color: white;
            color: black;
            border: 1px solid gray;
        }

        /* Стили для вкладок - увеличенный шрифт и скругление */
        QTabWidget::pane {
            border: 1px solid #ccc;
            border-radius: 5px;
        }

        QTabBar::tab {
            font-size: 12px;
            font-weight: bold;
            padding: 4px 10px;
            margin: 2px;
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 8px;
        }

        QTabBar::tab:selected {
            background-color: #4CAF50;
            color: white;
            border: 1px solid #4CAF50;
        }

        QTabBar::tab:hover:!selected {
            background-color: #e0e0e0;
        }

        /* Группа параметров моделирования */
        QGroupBox {
            border: 2px solid gray;
            border-radius: 12px;
            margin-top: 15px;
            font-size: 16px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 12px 0 12px;
            font-size: 16px;
            font-weight: bold;
        }

        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 14px;
            font-weight: bold;
        }

        QPushButton:hover {
            background-color: #e0e0e0;
        }

        QPushButton:pressed {
            background-color: #d0d0d0;
        }

        /* Скругленные спинбоксы */
        QSpinBox, QDoubleSpinBox {
            background-color: white;
            border: 2px solid #aaa;
            border-radius: 8px;
            padding: 2px 6px;
            color: black;
            font-size: 15px;
            font-weight: bold;
            min-height: 12px;
            min-width: 40px;
        }

        /* Текст внутри спинбокса */
        QSpinBox::text, QDoubleSpinBox::text {
            font-size: 10px;
            font-weight: bold;
        }

        QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #4CAF50;
        }

        /* Скрываем кнопки-стрелки */
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            width: 0px;
            height: 0px;
            subcontrol-position: none;
        }

        QCheckBox {
            spacing: 8px;
            color: black;
            font-size: 14px;
            font-weight: bold;
        }

        QCheckBox::indicator {
            width: 20px;
            height: 20px;
            border: 2px solid #555555;
            border-radius: 5px;
            background-color: white;
        }

        QCheckBox::indicator:checked {
            background-color: #4CAF50;
            border: 2px solid #4CAF50;
        }

        QCheckBox::indicator:unchecked:hover {
            border: 2px solid #999999;
        }

        QCheckBox::indicator:checked:hover {
            background-color: #45a049;
            border: 2px solid #45a049;
        }

        /* Подписи к спинбоксам (QLabel) */
        QLabel {
            font-size: 14px;
            font-weight: bold;
            color: black;
        }

        QTableWidget {
            background-color: white;
            alternate-background-color: #f8f8f8;
            gridline-color: #ddd;

        }

        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 6px;
            border: 1px solid #ddd;
            font-size: 16px;
            font-weight: bold;
        }

        /* Стиль только для спинбокса "Длина реализации" */
        QSpinBox#wide_spinbox {
            min-width: 40px;
            padding: 2px 8px;
        }


    """)

    w = MainWindow()
    w.showMaximized()
    w.show()
    sys.exit(app.exec())

