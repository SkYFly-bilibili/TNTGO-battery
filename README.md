# 电池监控工具使用说明

## 简介

电池监控工具是一个用于实时监控设备电池电量的Windows应用程序。它通过串口与设备通信，获取电池电量信息，并在系统托盘显示直观的电量图标。

## 主要功能

- **实时电量监控**：通过串口读取设备电池电量
- **系统托盘显示**：在Windows系统托盘中显示电量图标
- **多种图标样式**：支持电池图标和纯数字图标两种显示方式
- **定制化设置**：可自定义串口、波特率、查询间隔等参数
- **开机自启动**：支持Windows开机自动启动功能
- **图标尺寸调整**：可调整电池图标和数字图标的显示大小

## 使用方法

1. 启动程序后，应用将自动连接设置的串口并开始监控
2. 右键点击系统托盘图标可以打开菜单，进行各种设置

## 设置说明

### 连接设置

- **串口号**：选择设备连接的COM端口（默认COM3）
- **波特率**：设置串口通信速率（默认115200）
- **查询间隔**：设置获取电量后的定时查询间隔（默认30秒）

### 图标设置

- 图标样式

  ：选择显示方式

  - 电池图标：以电池形状直观显示电量
  - 纯数字图标：以数字形式显示电量百分比

- **电池大小**：调整电池图标的显示比例（0.5-1.0）

- **数字大小**：调整纯数字图标的字体大小（0.5-1.0）

### 系统设置

- **开机自启**：设置程序是否随Windows启动

## 电量显示逻辑

- 电量颜色：
  - 电量>70%：绿色
  - 30%<电量≤70%：橙色
  - 电量≤30%：红色
  - 未获取到电量：灰色
- 查询模式：
  - 未获取电量：快速查询模式（每0.5秒查询一次）
  - 已获取电量：定时查询模式（按设定间隔查询）

## 系统要求

- Windows 10或更高版本
- 支持串口通信的设备

------

# Battery Monitor Tool User Guide

## Introduction

The Battery Monitor Tool is a Windows application designed for real-time monitoring of device battery levels. It communicates with devices via serial port, retrieves battery information, and displays intuitive battery icons in the system tray.

## Main Features

- **Real-time Battery Monitoring**: Reads battery levels through serial port communication
- **System Tray Display**: Shows battery status directly in the Windows system tray
- **Multiple Icon Styles**: Supports both battery icon and numeric display styles
- **Customizable Settings**: Allows customization of port, baud rate, query interval, and more
- **Auto-startup**: Supports Windows startup automation
- **Icon Size Adjustment**: Adjustable sizes for both battery and numeric icons

## How to Use

1. After launching the program, it will automatically connect to the configured serial port and begin monitoring
2. Right-click the system tray icon to open the menu for various settings

## Settings Guide

### Connection Settings

- **COM Port**: Select the device's COM port (default: COM3)
- **Baud Rate**: Set the serial communication rate (default: 115200)
- **Query Interval**: Set the polling interval after battery level is acquired (default: 30 seconds)

### Icon Settings

- Icon Style

  : Choose display style

  - Battery Icon: Displays battery level in a battery shape
  - Numeric Icon: Displays battery percentage as a number

- **Battery Size**: Adjust the battery icon's display scale (0.5-1.0)

- **Number Size**: Adjust the font size of the numeric icon (0.5-1.0)

### System Settings

- **Auto-startup**: Configure whether the program launches with Windows

## Battery Display Logic

- Color Coding:
  - Level >70%: Green
  - 30% < Level ≤70%: Orange
  - Level ≤30%: Red
  - Level not acquired: Gray
- Query Modes:
  - Before level acquisition: Fast query mode (every 0.5 seconds)
  - After level acquisition: Timed query mode (based on set interval)

## System Requirements

- Windows 10 or higher
- Device with serial port communication support
