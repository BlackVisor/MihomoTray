## 预览
![预览](./asset/preview.png)

## 用途
- 仅适用于windows系统；
- 仅会创建一个托盘程序用于控制开启代理和内核，以及打开控制台；
- 适合裸核使用mihomo的情况，py脚本中开头的配置项需要根据实际情况修改；
- 推荐通过给pythonw.exe创建快捷方式，然后属性的目标一栏中增加该脚本路径的方式来实现静默化启动
- 托盘icon借用的CFW项目的，可自行修改
- 通过将pystray替换成这个https://github.com/xfangfang/pystray.git这个二开过的，可以支持左键打开菜单
- MY_DIRECT_RULES_FILE和EDITOR_PATH是用来快速打开自定义rule的，需要调整为本地对应路径
- reloadConfig里用的是zashboard的url和端口，可自行调整
