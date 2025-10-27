import os
import winreg
from enum import Enum
import subprocess
import time
import pystray
from PIL import Image
import sys
import webbrowser
import logging
from logging.handlers import RotatingFileHandler


# port of system proxy in reg
PROXY_PORT = 7890
# wait below interval for mihomo starting
WAIT_MIHOMO_START_SECONDS = 3
# url of mihomo console
CONSOLE_URL = 'http://127.0.0.1:9090/ui/zashboard/#/proxies'
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
# config file part
CONFIG_FILE_NAME = 'config.yaml'
CONFIG_FILE_PATH = os.path.join(WORK_DIR, CONFIG_FILE_NAME)
# mihomo part
MIHOMO_EXE = "mihomo.exe"
MIHOMO_EXE_PATH = os.path.join(WORK_DIR, MIHOMO_EXE)


class MihomoIcon(Enum):
    BROWN = 'tray_brown.ico'
    GREEN = 'tray_green.ico'
    LIGHT_BLUE = 'tray_light_blue.ico'
    BLUE = 'tray_blue.ico'
    ORANGE = 'tray_orange.ico'
    PINK = 'tray_pink.ico'
    PURPLE = 'tray_purple.ico'
    YELLOW = 'tray_yellow.ico'

    def getIconImage(self):
        return Image.open(os.path.join(WORK_DIR, 'asset', self.value))


def setupLogging():
    """配置日志：保存到用户文档目录，支持轮转，避免日志过大"""
    logDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    # 创建日志目录（不存在则自动创建）
    os.makedirs(logDir, exist_ok=True)
    logFile = os.path.join(logDir, "mihomo_tray.log")
    # 配置日志格式：时间 - 级别 - 模块/函数 - 消息
    logFormat = logging.Formatter("%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s")
    # 日志轮转：单个文件最大 5MB，保留 5 个备份（避免日志文件过大）
    fileHandler = RotatingFileHandler(
        logFile,
        maxBytes=5 * 1024 * 1024,  # 5MB
        encoding="utf-8"  # 支持中文
    )
    fileHandler.setFormatter(logFormat)
    # 获取全局日志器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # 日志级别：INFO（日常记录）、DEBUG（调试）、ERROR（错误）
    logger.addHandler(fileHandler)
    # 若脚本以 .py 运行（有控制台），同时输出到控制台（方便调试）
    if sys.stdout is not None:  # .pyw 运行时 sys.stdout 为 None
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormat)
        logger.addHandler(consoleHandler)
    # 记录启动信息
    logging.info("logging initialized")


def checkProcessRunning(exeName: str) -> bool:
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {exeName}'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return exeName in result.stdout
    except Exception as e:
        logging.error(f'check process {exeName} failed: {e}')
        return False


def toggleProxyInReg(enable=False, server=None):
    """设置系统代理"""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE
    ) as proxyKey:
        # 设置代理启用状态
        winreg.SetValueEx(proxyKey, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
        # 设置代理服务器
        if server:
            winreg.SetValueEx(proxyKey, "ProxyServer", 0, winreg.REG_SZ, server if enable and server else '')

    # 刷新代理设置使其生效
    result = subprocess.run(
        ["rundll32.exe", "wininet.dll,InternetSetOptionA", "0", "39", "0", "0"],
        check=True,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    logSubprocessResult(result, 'refresh reg to 39')
    result = subprocess.run(
        ["rundll32.exe", "wininet.dll,InternetSetOptionA", "0", "37", "0", "0"],
        check=True,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    logSubprocessResult(result, 'refresh reg to 37')


def openProxy(tray: pystray.Icon):
    try:
        # 1.use subprocess to start mihomo
        if not checkProcessRunning(MIHOMO_EXE):
            logging.info('mihomo not found, try to start it')
            # subprocess.run will wait mihomo end, so use Popen here
            subprocess.Popen(
                f'{MIHOMO_EXE_PATH} -d {WORK_DIR} -f {CONFIG_FILE_PATH}',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # 2.wait WAIT_MIHOMO_START_SECONDS for mihomo initialized
            time.sleep(WAIT_MIHOMO_START_SECONDS)
            # 3.check mihomo is running, otherwise change icon to orange
            if not checkProcessRunning(MIHOMO_EXE):
                logging.error('start mihomo failed')
                # set icon to orange for failure
                tray.icon = MihomoIcon.ORANGE.getIconImage()
                return
            else:
                logging.info('start mihomo done')
        else:
            logging.info("mihomo is running, so directly toggle reg")
        # 4. open system proxy in reg
        toggleProxyInReg(enable=True, server=f"127.0.0.1:{PROXY_PORT}")
        logging.info(f'system proxy started, port is {PROXY_PORT}')
        tray.icon = MihomoIcon.YELLOW.getIconImage()
    except Exception as e:
        logging.error(f'start mihomo or toggle reg failed: {e}')
        tray.icon = MihomoIcon.ORANGE.getIconImage()
        return


def logSubprocessResult(result: subprocess.CompletedProcess, action: str):
    if result.stdout.strip():
        logging.info(f'{action} is done, info is {result.stdout.strip()}')
    if result.stderr.strip():
        logging.error(f'error occurred when {action}, error is {result.stderr.strip()}')


def closeProxy(tray: pystray.Icon):
    try:
        # 1.close system proxy in reg
        toggleProxyInReg(enable=False)
        logging.info('system proxy closed')
        # 2.close mihomo
        if checkProcessRunning(MIHOMO_EXE):
            logging.info('mihomo is running, try to terminate it')
            result = subprocess.run(
                ["taskkill", "/F", "/IM", f"{MIHOMO_EXE}*"],
                check=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logSubprocessResult(result, 'kill mihomo')
            if not checkProcessRunning(MIHOMO_EXE):
                logging.info("terminate mihomo done")
                tray.icon = MihomoIcon.BLUE.getIconImage()
            else:
                logging.error("terminate mihomo failed")
                tray.icon = MihomoIcon.ORANGE.getIconImage()
        else:
            tray.icon = MihomoIcon.BLUE.getIconImage()
    except Exception as e:
        logging.error(f"terminate mihomo or toggle reg failed: {e}")
        return


def openConsole(icon, item):
    # click to open console in browser
    webbrowser.open(CONSOLE_URL)


def exitTray(tray: pystray.Icon):
    if checkProcessRunning(MIHOMO_EXE):
        closeProxy(tray)
    tray.stop()


def createTray():
    # create right click menu
    menu = pystray.Menu(
        pystray.MenuItem("开启代理", openProxy),
        pystray.MenuItem("关闭代理", closeProxy),
        pystray.MenuItem("控制台", openConsole),
        pystray.MenuItem("退出", exitTray)
    )
    # create tray
    icon = pystray.Icon("mihomo_proxy", MihomoIcon.BLUE.getIconImage(), "Mihomo", menu)
    return icon


if __name__ == "__main__":
    setupLogging()
    tray = createTray()
    tray.run()
