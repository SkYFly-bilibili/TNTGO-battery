import tkinter as tk
from tkinter import ttk
import serial
import threading
import re
import time
import pystray
from PIL import Image, ImageDraw, ImageFont
import os
import json
import winreg
import sys


class BatteryMonitorApp:
    def __init__(self):
        # 配置文件路径
        self.config_file = os.path.join(os.path.expanduser("~"), "battery_monitor_config.json")

        # 默认设置
        self.serial_port = None
        self.running = False
        self.current_battery = "--"
        self.port = "COM3"  # 默认串口
        self.baudrate = 115200  # 默认波特率
        self.battery_acquired = False  # 标记是否已获取到电量
        self.query_interval = 30  # 成功获取电量后的查询间隔（秒）
        self.icon_style = "battery"  # 默认图标样式: "battery" 或 "number"
        self.icon_size = 96  # 图标尺寸，更大的图标
        self.log_buffer = ""  # 初始化日志缓冲区
        self.number_font_size = 0.7  # 纯数字图标的字体大小比例，默认0.7
        self.battery_size = 0.8  # 电池图标的大小比例，默认0.8 (80%)
        self.auto_start = False  # 开机自启动，默认关闭

        # 加载配置
        self.load_config()

        # 创建初始托盘图标
        self.create_tray_icon()

        # 应用启动后自动开始监控
        self.start_reading()

    def create_tray_icon(self):
        # 创建初始图标
        icon_image = self.create_icon_by_style(self.current_battery)

        # 创建系统托盘图标
        self.icon = pystray.Icon("battery_monitor", icon_image, f"电池电量: {self.current_battery}%")

        # 创建菜单
        self.icon.menu = self.create_menu()

    def create_menu(self):
        """创建菜单，返回一个菜单对象而不是方法"""
        # 创建图标样式子菜单
        style_submenu = pystray.Menu(
            pystray.MenuItem('电池图标', lambda _: self.change_icon_style("battery"),
                             checked=lambda _: self.icon_style == "battery"),
            pystray.MenuItem('纯数字图标', lambda _: self.change_icon_style("number"),
                             checked=lambda _: self.icon_style == "number")
        )

        # 为每个大小创建一个独立的处理函数 - 纯数字图标字体大小
        def make_font_size_handler(size_value):
            def handler(_):
                self.change_number_font_size(size_value)

            return handler

        # 创建纯数字图标字体大小子菜单
        font_size_items = []
        for size in [round(0.5 + i * 0.05, 2) for i in range(11)]:  # 0.5到1.0，每0.05一个梯度
            size_str = str(size)
            font_size_items.append(pystray.MenuItem(
                size_str,
                make_font_size_handler(size),  # 使用闭包创建处理函数
                checked=lambda _, s=size: abs(self.number_font_size - s) < 0.01
            ))
        number_font_submenu = pystray.Menu(*font_size_items)

        # 为每个大小创建一个独立的处理函数 - 电池图标大小
        def make_battery_size_handler(size_value):
            def handler(_):
                self.change_battery_size(size_value)

            return handler

        # 创建电池图标大小子菜单
        battery_size_items = []
        for size in [round(0.5 + i * 0.05, 2) for i in range(11)]:  # 0.5到1.0，每0.05一个梯度
            size_str = str(size)
            battery_size_items.append(pystray.MenuItem(
                size_str,
                make_battery_size_handler(size),  # 使用闭包创建处理函数
                checked=lambda _, s=size: abs(self.battery_size - s) < 0.01
            ))
        battery_size_submenu = pystray.Menu(*battery_size_items)

        # 创建设置子菜单
        settings_submenu = pystray.Menu(
            pystray.MenuItem('设置面板', lambda _: self.show_settings_panel()),
            pystray.MenuItem('串口号', self.submenu_port()),
            pystray.MenuItem('波特率', self.submenu_baudrate()),
            pystray.MenuItem('查询间隔', self.submenu_interval()),
            pystray.MenuItem('数字大小', number_font_submenu),
            pystray.MenuItem('电池大小', battery_size_submenu),
            pystray.MenuItem('开机自启', lambda _: self.toggle_auto_start(),
                             checked=lambda _: self.auto_start)
        )

        # 电池电量显示始终使用最新状态
        battery_status = f'电池电量: {self.current_battery}%'

        # 创建并返回完整菜单
        return pystray.Menu(
            # 改为一个点击后不执行任何操作的函数，但保持enabled=True
            pystray.MenuItem(battery_status, lambda _: None),
            pystray.MenuItem('图标样式', style_submenu),
            pystray.MenuItem('设置', settings_submenu),
            pystray.MenuItem('重新连接', lambda _: self.reconnect()),
            pystray.Menu.SEPARATOR,  # 使用正确的分隔线
            pystray.MenuItem('退出', lambda _: self.exit_app())
        )

    def toggle_auto_start(self):
        """切换开机自启动状态"""
        self.auto_start = not self.auto_start
        self.set_auto_start(self.auto_start)
        status = "开启" if self.auto_start else "关闭"
        self.display_data(f"开机自启已{status}\n")
        self.save_config()
        self.update_menu()

    def set_auto_start(self, enable):
        """设置或移除开机自启动注册表项"""
        # 获取当前程序的完整路径
        app_path = sys.executable
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            app_path = sys.executable
        else:
            # 如果是Python脚本
            app_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

        # 定义注册表键名
        key_name = "BatteryMonitor"

        try:
            # 打开启动项注册表键
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )

            if enable:
                # 添加到启动项
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, app_path)
                self.display_data(f"已添加开机自启注册表项: {app_path}\n")
            else:
                # 从启动项移除
                try:
                    winreg.DeleteValue(key, key_name)
                    self.display_data("已移除开机自启注册表项\n")
                except FileNotFoundError:
                    # 键不存在，无需操作
                    pass
                except Exception as e:
                    self.display_data(f"移除开机自启注册表项失败: {str(e)}\n")

            winreg.CloseKey(key)

        except Exception as e:
            self.display_data(f"设置开机自启失败: {str(e)}\n")

    def save_config(self):
        """保存配置到文件"""
        config = {
            'port': self.port,
            'baudrate': self.baudrate,
            'query_interval': self.query_interval,
            'icon_style': self.icon_style,
            'number_font_size': self.number_font_size,
            'battery_size': self.battery_size,
            'auto_start': self.auto_start
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            self.display_data(f"配置已保存到 {self.config_file}\n")
            return True
        except Exception as e:
            self.display_data(f"保存配置文件失败: {str(e)}\n")
            return False

    def load_config(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)

                # 更新配置
                if 'port' in config: self.port = config['port']
                if 'baudrate' in config: self.baudrate = config['baudrate']
                if 'query_interval' in config: self.query_interval = config['query_interval']
                if 'icon_style' in config: self.icon_style = config['icon_style']
                if 'number_font_size' in config: self.number_font_size = config['number_font_size']
                if 'battery_size' in config: self.battery_size = config['battery_size']
                if 'auto_start' in config:
                    self.auto_start = config['auto_start']
                    # 确保注册表状态与配置一致
                    self.set_auto_start(self.auto_start)

                self.display_data(f"已从 {self.config_file} 加载配置\n")
                return True
            else:
                self.display_data("配置文件不存在，使用默认设置\n")
                return False
        except Exception as e:
            self.display_data(f"加载配置文件失败: {str(e)}，使用默认设置\n")
            return False

    def update_menu(self):
        """更新菜单以反映当前状态"""
        self.icon.menu = self.create_menu()

    def submenu_port(self):
        # 创建串口选择子菜单
        ports = [f'COM{i}' for i in range(1, 11)]
        items = []

        # 为每个端口创建一个独立的处理函数
        def make_port_handler(port_value):
            def handler(_):
                self.change_port(port_value)

            return handler

        for port in ports:
            items.append(pystray.MenuItem(
                port,
                make_port_handler(port),
                checked=lambda _, p=port: self.port == p
            ))
        return pystray.Menu(*items)

    def submenu_baudrate(self):
        # 创建波特率选择子菜单
        baudrates = [9600, 19200, 38400, 57600, 115200]
        items = []

        # 为每个波特率创建一个独立的处理函数
        def make_baud_handler(baud_value):
            def handler(_):
                self.change_baudrate(baud_value)

            return handler

        for baud in baudrates:
            items.append(pystray.MenuItem(
                str(baud),
                make_baud_handler(baud),
                checked=lambda _, b=baud: self.baudrate == b
            ))
        return pystray.Menu(*items)

    def submenu_interval(self):
        # 创建查询间隔选择子菜单
        intervals = [5, 10, 30, 60, 120, 300]
        items = []

        # 为每个间隔创建一个独立的处理函数
        def make_interval_handler(interval_value):
            def handler(_):
                self.change_interval(interval_value)

            return handler

        for interval in intervals:
            items.append(pystray.MenuItem(
                f'{interval}秒',
                make_interval_handler(interval),
                checked=lambda _, i=interval: self.query_interval == i
            ))
        return pystray.Menu(*items)

    def change_port(self, new_port):
        """更改串口设置"""
        if new_port != self.port:
            self.port = new_port
            self.display_data(f"串口已更改为: {self.port}\n")
            # 保存配置
            self.save_config()
            # 需要重新连接
            self.reconnect()

    def change_baudrate(self, new_baudrate):
        """更改波特率设置"""
        if new_baudrate != self.baudrate:
            self.baudrate = new_baudrate
            self.display_data(f"波特率已更改为: {self.baudrate}\n")
            # 保存配置
            self.save_config()
            # 需要重新连接
            self.reconnect()

    def change_interval(self, new_interval):
        """更改查询间隔设置"""
        if new_interval != self.query_interval:
            self.query_interval = new_interval
            self.display_data(f"查询间隔已更改为: {self.query_interval}秒\n")
            # 保存配置
            self.save_config()

    def change_number_font_size(self, size):
        """更改纯数字图标的字体大小"""
        # 在方法开始时记录日志，帮助调试
        self.display_data(f"尝试更改数字字体大小到: {size} (当前: {self.number_font_size})\n")

        if abs(self.number_font_size - size) > 0.01:  # 避免浮点数比较的精度问题
            self.number_font_size = size
            self.display_data(f"纯数字图标字体大小已更改为: {size}\n")

            # 保存配置
            self.save_config()

            # 如果当前使用的是纯数字图标，则立即更新图标
            if self.icon_style == "number":
                new_icon = self.create_icon_by_style(self.current_battery)
                self.icon.icon = new_icon
                self.display_data("已更新图标\n")

            # 更新菜单
            self.update_menu()

    def change_battery_size(self, size):
        """更改电池图标的大小"""
        # 在方法开始时记录日志，帮助调试
        self.display_data(f"尝试更改电池图标大小到: {size} (当前: {self.battery_size})\n")

        if abs(self.battery_size - size) > 0.01:  # 避免浮点数比较的精度问题
            self.battery_size = size
            self.display_data(f"电池图标大小已更改为: {size}\n")

            # 保存配置
            self.save_config()

            # 如果当前使用的是电池图标，则立即更新图标
            if self.icon_style == "battery":
                new_icon = self.create_icon_by_style(self.current_battery)
                self.icon.icon = new_icon
                self.display_data("已更新图标\n")

            # 更新菜单
            self.update_menu()

    def reconnect(self):
        """重新连接串口"""
        self.stop_reading()
        time.sleep(1)  # 短暂等待确保串口关闭
        self.battery_acquired = False  # 重置电量获取状态
        self.start_reading()

    def change_icon_style(self, style):
        """切换图标样式"""
        if self.icon_style != style:
            self.icon_style = style
            self.display_data(f"已切换到{style}图标样式\n")

            # 保存配置
            self.save_config()

            # 更新图标
            new_icon = self.create_icon_by_style(self.current_battery)
            self.icon.icon = new_icon

            # 更新菜单
            self.update_menu()

    def create_icon_by_style(self, percentage):
        """根据当前样式创建图标"""
        if self.icon_style == "battery":
            return self.create_battery_icon(percentage)
        else:
            return self.create_number_icon(percentage)

    def create_battery_icon(self, percentage):
        """创建电池样式图标 - 无数字版本，大小可调"""
        width = self.icon_size
        height = self.icon_size
        image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 根据电池大小比例调整电池尺寸
        bat_width = int(width * self.battery_size)
        bat_height = int(height * self.battery_size * 0.6)  # 保持电池的长宽比
        bat_x = (width - bat_width) // 2
        bat_y = (height - bat_height) // 2

        # 电池正极
        pole_width = int(width * self.battery_size * 0.125)  # 保持电池正极与电池的比例
        pole_height = int(bat_height * 0.4)
        pole_x = bat_x + bat_width
        pole_y = bat_y + (bat_height - pole_height) // 2

        # 绘制电池外框 - 根据电池大小调整线宽
        outline_width = max(1, int(self.battery_size * 3))
        draw.rectangle([bat_x, bat_y, bat_x + bat_width, bat_y + bat_height],
                       outline=(0, 0, 0, 255), width=outline_width)

        # 绘制电池正极
        draw.rectangle([pole_x, pole_y, pole_x + pole_width, pole_y + pole_height], fill=(0, 0, 0, 255))

        # 根据电量确定填充颜色
        if percentage == "--":
            fill_color = (128, 128, 128, 255)  # 灰色
            # 不填充电量，只显示灰色边框
        else:
            percentage_int = int(percentage)
            if percentage_int > 70:
                fill_color = (0, 255, 0, 255)  # 绿色
            elif percentage_int > 30:
                fill_color = (255, 165, 0, 255)  # 橙色
            else:
                fill_color = (255, 0, 0, 255)  # 红色

            # 绘制电量填充，考虑边框宽度
            padding = outline_width + 1
            max_fill_width = bat_width - padding * 2
            fill_width = int(max_fill_width * percentage_int / 100)

            if fill_width > 0:
                draw.rectangle([bat_x + padding,
                                bat_y + padding,
                                bat_x + padding + fill_width,
                                bat_y + bat_height - padding],
                               fill=fill_color)

        return image

    def create_number_icon(self, percentage):
        """创建纯数字样式图标 - 无百分号版本，字体大小可调"""
        width = self.icon_size
        height = self.icon_size
        image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 根据电量确定填充颜色
        if percentage == "--":
            text_color = (100, 100, 100, 255)  # 灰色
            battery_text = "--"
        else:
            percentage_int = int(percentage)
            if percentage_int > 70:
                text_color = (0, 200, 0, 255)  # 绿色
            elif percentage_int > 30:
                text_color = (255, 165, 0, 255)  # 橙色
            else:
                text_color = (255, 0, 0, 255)  # 红色

            battery_text = f"{percentage}"

        try:
            # 使用可调整的字体大小
            font = ImageFont.truetype("arial.ttf", int(width * self.number_font_size))
        except IOError:
            font = ImageFont.load_default()

        # 在中间显示大数字
        text_x = width // 2
        text_y = height // 2

        # 先绘制白色背景使数字更清晰
        outline_width = 2
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
            draw.text((text_x + dx * outline_width, text_y + dy * outline_width),
                      battery_text, font=font, fill=(255, 255, 255, 180), anchor="mm")

        # 绘制主要文本
        draw.text((text_x, text_y), battery_text, font=font, fill=text_color, anchor="mm")

        return image

    def show_settings_panel(self):
        # 检查是否已经有窗口打开
        if hasattr(self, 'root') and self.root.winfo_exists():
            # 如果窗口已经存在但被最小化或隐藏了，恢复它
            self.root.deiconify()
            self.root.lift()
            return

        # 创建设置窗口
        self.root = tk.Tk()
        self.root.title("电量监控设置")

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建设置框架
        settings_frame = ttk.LabelFrame(main_frame, text="连接设置", padding="5")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # 串口选择
        port_frame = ttk.Frame(settings_frame)
        port_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(port_frame, text="串口号:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(port_frame, values=[f'COM{i}' for i in range(1, 21)], width=15)
        self.port_combo.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        self.port_combo.set(self.port)

        # 波特率选择
        baud_frame = ttk.Frame(settings_frame)
        baud_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(baud_frame, text="波特率:").pack(side=tk.LEFT)
        self.baudrate_combo = ttk.Combobox(baud_frame, values=[9600, 19200, 38400, 57600, 115200], width=15)
        self.baudrate_combo.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        self.baudrate_combo.set(self.baudrate)

        # 查询间隔选择
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(interval_frame, text="查询间隔(秒):").pack(side=tk.LEFT)
        self.interval_combo = ttk.Combobox(interval_frame, values=[5, 10, 30, 60, 120, 300], width=15)
        self.interval_combo.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        self.interval_combo.set(self.query_interval)

        # 图标样式选择
        style_frame = ttk.Frame(settings_frame)
        style_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(style_frame, text="图标样式:").pack(side=tk.LEFT)
        self.style_var = tk.StringVar(value=self.icon_style)
        ttk.Radiobutton(style_frame, text="电池图标", variable=self.style_var, value="battery").pack(side=tk.LEFT,
                                                                                                     padx=5)
        ttk.Radiobutton(style_frame, text="纯数字", variable=self.style_var, value="number").pack(side=tk.LEFT, padx=5)

        # 开机自启动选项
        autostart_frame = ttk.Frame(settings_frame)
        autostart_frame.pack(fill=tk.X, padx=5, pady=5)
        self.autostart_var = tk.BooleanVar(value=self.auto_start)
        autostart_check = ttk.Checkbutton(autostart_frame, text="开机自动启动", variable=self.autostart_var)
        autostart_check.pack(side=tk.LEFT, padx=5)

        # 图标大小设置框架
        icon_size_frame = ttk.LabelFrame(main_frame, text="图标大小设置", padding="5")
        icon_size_frame.pack(fill=tk.X, padx=5, pady=5)

        # 添加电池图标大小设置
        battery_size_frame = ttk.Frame(icon_size_frame)
        battery_size_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(battery_size_frame, text="电池大小:").pack(side=tk.LEFT)
        font_size_values = [round(0.5 + i * 0.05, 2) for i in range(11)]  # 0.5到1.0，每0.05一个梯度
        self.battery_size_combo = ttk.Combobox(battery_size_frame, values=font_size_values, width=15)
        self.battery_size_combo.set(self.battery_size)
        self.battery_size_combo.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)

        # 添加纯数字图标字体大小设置
        font_size_frame = ttk.Frame(icon_size_frame)
        font_size_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(font_size_frame, text="数字大小:").pack(side=tk.LEFT)
        self.font_size_combo = ttk.Combobox(font_size_frame, values=font_size_values, width=15)
        self.font_size_combo.set(self.number_font_size)
        self.font_size_combo.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)

        # 控制按钮框架
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        if not self.running:
            start_state = tk.NORMAL
            stop_state = tk.DISABLED
        else:
            start_state = tk.DISABLED
            stop_state = tk.NORMAL

        self.start_button = ttk.Button(control_frame, text="开始", command=self.start_reading, state=start_state)
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text="停止", command=self.stop_reading, state=stop_state)
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        self.apply_button = ttk.Button(control_frame, text="应用设置", command=self.apply_settings)
        self.apply_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        # 电量显示
        status_frame = ttk.LabelFrame(main_frame, text="电量状态", padding="5")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self.battery_label = ttk.Label(status_frame, text=f"当前电量: {self.current_battery}%", font=("Helvetica", 16))
        self.battery_label.pack(padx=5, pady=5)

        # 电量状态标签
        status_text = "已获取电量" if self.battery_acquired else "等待获取电量..."
        self.status_label = ttk.Label(status_frame, text=status_text)
        self.status_label.pack(padx=5, pady=2)

        # 日志框架
        log_frame = ttk.LabelFrame(main_frame, text="通信日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建日志区域和滚动条
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.text_area = tk.Text(log_container, height=10, wrap=tk.WORD)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_container, command=self.text_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area['yscrollcommand'] = scrollbar.set
        self.text_area.config(state=tk.DISABLED)

        # 日志控制按钮
        log_controls = ttk.Frame(log_frame)
        log_controls.pack(fill=tk.X, pady=5)

        self.clear_log_button = ttk.Button(log_controls, text="清除日志", command=self.clear_log)
        self.clear_log_button.pack(side=tk.RIGHT, padx=5)

        # 设置窗口大小和位置
        self.root.geometry("500x700")  # 增加窗口高度以适应新增的设置
        self.root.minsize(400, 500)  # 设置最小窗口大小
        self.center_window(self.root)

        # 窗口关闭处理 - 现在是真正的销毁窗口
        self.root.protocol("WM_DELETE_WINDOW", self.destroy_window)

        # 如果有日志，显示在文本区域
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, self.log_buffer)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

        self.root.mainloop()

    def destroy_window(self):
        """完全销毁窗口而不仅仅是隐藏"""
        if hasattr(self, 'root'):
            self.root.destroy()

    def clear_log(self):
        if hasattr(self, 'text_area'):
            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete(1.0, tk.END)
            self.text_area.config(state=tk.DISABLED)
        self.log_buffer = ""
        self.display_data("日志已清除\n")

    def center_window(self, window):
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def apply_settings(self):
        new_port = self.port_combo.get()
        new_baudrate = int(self.baudrate_combo.get())
        new_interval = int(self.interval_combo.get())
        new_style = self.style_var.get()
        new_font_size = float(self.font_size_combo.get())
        new_battery_size = float(self.battery_size_combo.get())
        new_auto_start = self.autostart_var.get()

        # 检查是否需要重启监控
        restart_needed = self.running and (new_port != self.port or new_baudrate != self.baudrate)

        if restart_needed:
            self.stop_reading()

        self.port = new_port
        self.baudrate = new_baudrate
        self.query_interval = new_interval

        # 检查是否需要更新图标
        icon_update_needed = (new_style != self.icon_style or
                              (new_style == "number" and abs(new_font_size - self.number_font_size) > 0.01) or
                              (new_style == "battery" and abs(new_battery_size - self.battery_size) > 0.01))

        # 更新图标样式（如果有变化）
        if new_style != self.icon_style:
            self.icon_style = new_style
            self.display_data(f"图标样式已更改为: {self.icon_style}\n")

        # 更新纯数字图标字体大小（如果有变化）
        if abs(new_font_size - self.number_font_size) > 0.01:
            self.number_font_size = new_font_size
            self.display_data(f"纯数字图标字体大小已更改为: {self.number_font_size}\n")

        # 更新电池图标大小（如果有变化）
        if abs(new_battery_size - self.battery_size) > 0.01:
            self.battery_size = new_battery_size
            self.display_data(f"电池图标大小已更改为: {self.battery_size}\n")

        # 更新开机自启动设置（如果有变化）
        if new_auto_start != self.auto_start:
            self.auto_start = new_auto_start
            self.set_auto_start(self.auto_start)
            status = "开启" if self.auto_start else "关闭"
            self.display_data(f"开机自启已{status}\n")

        # 如果需要，更新图标
        if icon_update_needed:
            new_icon = self.create_icon_by_style(self.current_battery)
            self.icon.icon = new_icon

        # 保存配置
        self.save_config()

        # 更新菜单以反映新的选择状态
        self.update_menu()

        self.display_data(f"设置已更新: 端口={self.port}, 波特率={self.baudrate}, 查询间隔={self.query_interval}秒\n")

        if restart_needed:
            # 重置电量获取标志，以便重新获取电量
            self.battery_acquired = False
            if hasattr(self, 'status_label'):
                self.status_label.config(text="等待获取电量...")
            self.start_reading()

    def start_reading(self):
        if not self.running:
            self.running = True
            if hasattr(self, 'start_button'):
                self.start_button.config(state=tk.DISABLED)
            if hasattr(self, 'stop_button'):
                self.stop_button.config(state=tk.NORMAL)

            self.thread = threading.Thread(target=self.read_serial)
            self.thread.daemon = True  # 设为守护线程，避免退出时挂起
            self.thread.start()
            self.display_data("串口监控已启动\n")

    def stop_reading(self):
        if self.running:
            self.running = False
            if hasattr(self, 'start_button'):
                self.start_button.config(state=tk.NORMAL)
            if hasattr(self, 'stop_button'):
                self.stop_button.config(state=tk.DISABLED)
            self.display_data("串口监控已停止\n")

            # 关闭串口连接
            if self.serial_port and hasattr(self.serial_port, 'is_open') and self.serial_port.is_open:
                self.serial_port.close()
                self.display_data("已关闭串口连接\n")

    def read_serial(self):
        try:
            self.serial_port = serial.Serial(self.port, int(self.baudrate), timeout=0.1)
            self.serial_port.write(b'at+adb\r\n')
            self.display_data(f"成功连接到 {self.port} (波特率: {self.baudrate})\n")

            # 通信策略：未获取电量前快速查询，获取后定时查询
            fast_query_time = time.time()  # 记录上次快速查询时间

            while self.running:
                try:
                    # 读取可用数据
                    data = self.serial_port.readline()
                    if data:
                        data_str = data.decode(errors='replace')
                        self.display_data(data_str)
                        self.check_battery_status(data_str)

                    current_time = time.time()

                    # 如果尚未获取电量，使用快速查询策略（每0.5秒一次）
                    if not self.battery_acquired:
                        if current_time - fast_query_time >= 0.5:
                            if self.running:
                                self.serial_port.write(b'at+adb\r\n')
                                fast_query_time = current_time
                                self.display_data("发送查询命令 (快速模式)\n")
                    else:
                        # 已获取电量，按设定的时间间隔查询
                        if current_time - fast_query_time >= self.query_interval:
                            if self.running:
                                self.serial_port.write(b'at+adb\r\n')
                                fast_query_time = current_time
                                self.display_data(f"发送查询命令 (间隔 {self.query_interval}秒)\n")

                    # 短暂休眠，避免CPU占用过高
                    time.sleep(0.1)

                except Exception as e:
                    self.display_data(f"读取数据错误: {str(e)}\n")
                    time.sleep(1)

        except Exception as e:
            self.display_data(f"串口错误: {str(e)}\n")
            # 在出错后尝试自动重连
            time.sleep(5)
            if self.running:
                self.display_data("尝试重新连接...\n")
                self.battery_acquired = False  # 重置电量获取状态
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="等待获取电量...")
                threading.Thread(target=self.read_serial, daemon=True).start()
                return
        finally:
            if self.serial_port and hasattr(self.serial_port, 'is_open') and self.serial_port.is_open:
                self.serial_port.close()
                self.display_data("已关闭串口连接\n")

    def check_battery_status(self, data):
        """检查数据中是否包含电池信息并更新状态"""
        match = re.search(r'\+BATCG=\d+,(?P<percentage>\d+),', data)
        if match:
            percentage = match.group('percentage')
            self.current_battery = percentage

            # 第一次获取电量时更新状态
            if not self.battery_acquired:
                self.battery_acquired = True
                self.display_data("成功获取电量！切换到定时查询模式\n")
                if hasattr(self, 'status_label'):
                    self.status_label.config(text=f"已获取电量，每 {self.query_interval} 秒更新一次")

            # 更新托盘图标
            new_icon = self.create_icon_by_style(percentage)
            self.icon.icon = new_icon

            # 更新托盘图标提示文本
            self.icon.title = f"电池电量: {percentage}%"

            # 更新设置窗口中的电量显示（如果存在）
            if hasattr(self, 'battery_label'):
                self.battery_label.config(text=f"当前电量: {percentage}%")

            # 更新菜单，显示当前电量
            self.update_menu()

    def display_data(self, data):
        # 添加时间戳
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        data_with_timestamp = f"[{timestamp}] {data}"

        # 保存所有日志到缓冲区，以便在打开设置窗口时显示
        self.log_buffer += data_with_timestamp

        # 如果日志太长则截断
        if len(self.log_buffer) > 10000:
            self.log_buffer = self.log_buffer[-10000:]

        # 如果设置窗口已打开，则更新文本区域
        if hasattr(self, 'text_area'):
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, data_with_timestamp)
            self.text_area.see(tk.END)
            self.text_area.config(state=tk.DISABLED)

    def exit_app(self):
        self.stop_reading()
        # 先停止图标，然后调度退出
        self.icon.stop()
        # 使用threading模块创建一个延迟退出的线程
        threading.Timer(0.1, lambda: os._exit(0)).start()

    def run(self):
        # 启动图标
        self.icon.run()


if __name__ == "__main__":
    app = BatteryMonitorApp()
    # 运行托盘图标
    app.run()