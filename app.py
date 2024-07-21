from flask import Flask, render_template, request , Response ,session ,render_template_string
import threading
import logging
import time
import subprocess
import glob
import os
import json
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', '12345678')
# JSON 文件路径


# 设定初始变量值
vars = {
    'TELEGRAM_BOT_TOKEN': '',
    'TELEGRAM_CHAT_ID': '',
    'TELEGRAM_API_URL': '',
    'EMBY_SERVER_URL': '',
    'EMBY_API_KEY': '',
    'source_dir': '',
    'strm_dir': '',
    'docker_dir': '',
    'library_dir': '',
    'cloud_dir': '',
    'path_layers': '',
    'path_delete': 'False',
}

script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, 'config.json')
log_dir = os.path.join(script_dir, 'logs')
# 获取当前脚本的文件名（不包括扩展名）
prefix_name = Path(__file__).stem
log_filename = os.path.join(log_dir, f'{prefix_name}.log')
os.makedirs(log_dir, exist_ok=True)
script_file = os.path.join(script_dir, 'ssjk.py') 
# 加载变量
def load_vars():
    if os.path.isfile(CONFIG_FILE) and os.path.getsize(CONFIG_FILE) > 3:  # 检查文件存在且非空
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        # 这里返回一个默认值或者处理未找到或空文件的情况
        return vars

# 保存变量
def save_vars(vars):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(vars, f)

# 初始化变量
vars = load_vars()

def configure_logging():
    
    # 获取当前时间并格式化为字符串
    log_time = time.strftime("%Y%m%d-%H%M%S")
    prefix = prefix_name + '_'

    
    # 定义日志文件名格式，包含时间戳
    #log_filename = os.path.join(log_dir, f'{prefix}{log_time}.log')
    log_filename = os.path.join(log_dir, f'{prefix_name}.log')
    
    # 创建日志记录器
    logger = logging.getLogger('myapp')
    logger.setLevel(logging.DEBUG)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    #formatter = logging.Formatter('%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s')
    formatter = logging.Formatter('%(levelname)s %(asctime)s %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 将处理器添加到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
def check_and_rotate_log():
    global logger
    current_date = time.strftime("%Y%m%d")
    if not hasattr(check_and_rotate_log, "last_date"):
        check_and_rotate_log.last_date = current_date
    
    if check_and_rotate_log.last_date != current_date:
        logger = configure_logging()
        check_and_rotate_log.last_date = current_date
logger = configure_logging()

monitor_thread = None
monitor_running = False
ssjk_log = os.path.join(log_dir, 'ssjk.log')

def run_script():
    global monitor_running
    while monitor_running:
        logger.info("Running ssjk.py script...")
        env_vars = {key: value for key, value in vars.items()}
        subprocess.run(["python3", script_file], env={**os.environ, **env_vars})  # 传递环境变量并运行ssjk.py
        time.sleep(5)

def get_latest_log_file():
    log_files = glob.glob(log_filename )
    if not log_files:
        return None
    latest_log_file = max(log_files, key=os.path.getctime)
    return latest_log_file

@app.route('/', methods=['GET', 'POST'])
def index():
    global monitor_thread, monitor_running, vars , monitoring
    if request.method == 'POST':
        for key in vars.keys():
            vars[key] = request.form[key]
        save_vars(vars)
        # 检查并设置session状态
        if 'start' in request.form and not session.get('monitoring', False):
            session['monitoring'] = True
            monitor_running = True
            monitor_thread = threading.Thread(target=run_script)
            monitor_thread.start()
            logger.info("Started monitoring")
        elif 'stop' in request.form:
            session['monitoring'] = False
            monitor_running = False
            if monitor_thread and monitor_thread.is_alive():
                monitor_thread.join()
            logger.info("Stopped monitoring")
    # 页面初次加载或刷新时，根据session状态决定是否显示"开始监控"或"停止监控"
    monitoring_status = session.get('monitoring', False)

    return render_template('index.html', vars=vars,monitoring=monitoring_status) #,monitoring=monitoring_status 
    


@app.route('/logs')

def stream_logs():
    def generate():
        logger.info(f"log路径：{ssjk_log}")
        with open(ssjk_log, 'r') as f:
            # 读取现有日志内容
            yield f.read()
            # 定位到文件末尾，准备监听新内容
            f.seek(0, 2)  # 0代表文件开头，2代表文件末尾
            while True:
                line = f.readline()
                if not line:
                    time.sleep(1)  # 没有新日志时等待，避免CPU占用过高
                    continue
                yield f"data: {line.strip()}\n\n"
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=5432)
