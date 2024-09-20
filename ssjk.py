import os
import time
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Optional, List, Union
from glob import glob  
from pathlib import Path
import yaml
import threading 

source_file = '/backup/config.yaml.bak'  
destination_dir = '/app/config'  
destination_file = os.path.join(destination_dir, 'config.yaml')    
# 确保目标目录存在  
os.makedirs(destination_dir, exist_ok=True)    
# 检查目标文件是否存在  
if not os.path.isfile(destination_file):  
    print("File does not exist, copying from backup")  
    # 复制文件  
    shutil.copy(source_file, destination_file)
#输入config信息    
with open('/app/config/config.yaml', 'r') as file:  
    data = yaml.safe_load(file)
#输入路径参数集合
dir_set = set(data['dir_set'])  # 使用映射的键来创建集合 

# Telegram Bot API配置
TELEGRAM_BOT_TOKEN = data['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = data['TELEGRAM_CHAT_ID']
TELEGRAM_API_URL =  f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
# Emby API配置
EMBY_SERVER_URL = data['EMBY_SERVER_URL']
EMBY_API_KEY = data['EMBY_API_KEY']


#采集待通知库信息
result_set = set() #非填写项
media_set = set() #非填写项
error_set = set()
#path_layers = int(path_layers)
def configure_logging():
    # 获取当前脚本的文件名（不包括扩展名）
    prefix_name = Path(__file__).stem
    # 获取当前时间并格式化为字符串
    log_time = time.strftime("%Y%m%d-%H%M%S")
    
    prefix = prefix_name + '_'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
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
# 发送Telegram通知的函数
def send_telegram_notification(message):
    global TELEGRAM_BOT_TOKEN,TELEGRAM_CHAT_ID,TELEGRAM_API_URL
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_API_URL:
        max_length = 4000
        for i in range(0, len(message), max_length):
            chunk = message[i:i + max_length]
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': chunk
            }
            session = requests.Session()
            # 设置重试策略
            retry = Retry(
                        total=5,  # 总重试次数
                        backoff_factor=0.5,  # 重试间隔时间因子
                        status_forcelist=[500, 502, 503, 504]  # 针对哪些状态码重试
                        )

            # 安装适配器到会话
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('https://', adapter)

            # 使用会话发送请求
            try:
                response = session.post(TELEGRAM_API_URL, data=payload)
                response.raise_for_status()  # 检查请求是否成功
                #print(response.text)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"发送Telegram通知失败: {response.text}")


# EmbyRefresh 类定义
class EmbyRefresh:
    def __init__(self, api_key, emby_addr):
        self.api_key = api_key
        self.emby_addr = emby_addr
        self.library_item_ids = self._get_library_item_ids()
    def _get_library_item_ids(self):
        itemIds=[]
        url = f"{self.emby_addr}/Items"
        headers = {
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json"
        }
        params = {
            "Recursive": True,
            "Fields": "Path",
            "IncludeItemTypes": "Folder"
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("Items", []):
                if item.get("Path") in result_set:
                    itemIds.append(item.get("Id"))
        return itemIds

    def refresh_library(self):      
        if self.library_item_ids:
            for item_id in self.library_item_ids:
                url = f"{self.emby_addr}/Items/{item_id}/Refresh"
                headers = {
                    "X-Emby-Token": self.api_key,
                    "Content-Type": "application/json"
                }
                params = {
                    "Recursive": True
                }
                response = requests.post(url, headers=headers, params=params)
                if response.status_code == 204:
                    logger.info(f"Library refresh initiated successfully for item ID: {item_id}.")
                else:
                    logger.info(f"Failed to refresh library for item ID: {item_id}. Status code: {response.status_code}")
                
                # 每次请求后等待 2 秒钟
                time.sleep(2)
        else:
            logger.info("Library item IDs not found.")


def cleanup_old_logs():
    # 获取当前脚本的文件名（不包括扩展名）
    prefix_name = Path(__file__).stem
    max_files=3 
    prefix = prefix_name + '_'
    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    log_dir = os.path.join(script_dir, 'logs') 
    log_files = glob(os.path.join(log_dir, f'{prefix}*.log'))  
    log_files.sort(key=os.path.getmtime, reverse=True)  # 按修改时间排序  
    if len(log_files) > max_files:  
        for file in log_files[max_files:]:  # 删除超过max_files个的最旧文件  
            try:  
                os.remove(file)  
                logger.info(f'Removed old log file: {file}')  
            except OSError as e:  
                logger.info(f'Error removing file {file}: {e.strerror}') 

def get_head_dir(file_path, path_layers):
    
    # 去除路径末尾的文件名部分，只留下目录部分
    #  
    directory_path = '/'.join(file_path.split('/')[:-1])  
    # 分割目录路径  
    parts = directory_path.split('/')  
    # 根据实际情况选择返回的路径  
    if len(parts) >= path_layers:  
        # 如果路径至少有path_layers层级，返回前path_layers-1个层级  
        return '/'.join(parts[:path_layers-1])  
    else:  
        # 如果路径层级不足path_layers，返回整个目录路径  
        return directory_path
def delete_directories_at_level(root, path_layers):  
    current_level = 1  
    stack = [root]  
    while stack:  
        current_dir = stack.pop()
        delete_dir = Path(current_dir)
        #logger.info(f"current_dir： {current_dir} ")  
        if delete_dir.is_dir():  
            if current_level == path_layers:  
                # 删除当前级别的目录  
                print(f'Deleting {delete_dir}')  
                shutil.rmtree(str(delete_dir))  
            else:  
                # 如果不是要删除的级别，继续遍历子目录  
                stack.extend(delete_dir.iterdir())  
                current_level += 1 if current_level < path_layers else 0  
            # 回退到上一级目录时，级别减1  
            if not stack and current_level > 1:  
                current_level -= 1 

def process_file(file_path,source_dir,strm_dir,docker_dir,library_dir,cloud_dir,path_layers,path_delete):
        global result_set, media_set,error_set
        filename = os.path.basename(file_path)
          
        if filename.endswith('.py'):  
            return  # 如果是.py文件，则跳过处理        
        # 计算相对于源目录的路径（不包括源目录本身）
        relative_path = os.path.relpath(file_path, source_dir)
        directory = os.path.dirname(relative_path)
        filename_without_ext, ext = os.path.splitext(relative_path)
        media_info = os.path.join(directory, filename_without_ext)
        # 在strm_dir下创建相同的子目录结构
        strm_file_path = os.path.join(strm_dir, relative_path)
        strm_dir_path = os.path.dirname(strm_file_path)
        os.makedirs(strm_dir_path, exist_ok=True)
        # 在library_dir下创建相同的子目录结构
        library_file_path = os.path.join(library_dir, relative_path)
        library_dir_path = os.path.dirname(library_file_path)
        os.makedirs(library_dir_path, exist_ok=True)
        # 根据扩展名生成.strm文件或拷贝nfo、jpg、png文件
        base_name,extension_with_dot = os.path.splitext(filename)
        extension = extension_with_dot[1:].lower()    
        if extension.lower() in ['mp4', 'mkv', 'avi', 'ts', 'wmv']:
         strm_file = os.path.join(strm_dir_path, base_name + '.strm')
         s_path = os.path.normpath(relative_path).replace('\\', '/')  
         with open(strm_file, 'w', encoding='utf-8') as f:
            f.write(f"{cloud_dir}/{s_path}")
        elif extension.lower() in ['nfo', 'jpg', 'png','srt','ass','mp3']:
             shutil.copy(file_path, strm_dir_path)
        #print(f"{file_path}strm制作完成 ")     
        try:
        # 尝试移动文件
         #print(f"尝试移动文件 {file_path} ")
         #head = relative_path.split('/')[0]
         head = get_head_dir(relative_path,path_layers)
         #media_path = os.path.relpath(relative_path, head)
         #media = media_path.split('/')[0]
         shutil.move(file_path, library_dir_path)
         #print(f"移动文件 {file_path} 到:{library_dir_path}")
         emby_path = os.path.join(docker_dir, head)
         #print(f"要查询的emby库:{emby_path}")
         result_set.add(emby_path)
         media_set.add(filename_without_ext)
         
        except Exception as e:
         # 如果出现任何异常，打印错误信息
         error_message = "移动文件 {file_path}出错" 
         logger.error(f"移动文件时出错: {e}")
         error_set.add(error_message)
         # 发送Telegram通知
         
         
def format_time(seconds):  
    hours, remainder = divmod(seconds, 3600)  
    minutes, seconds = divmod(remainder, 60)  
    return f"{int(hours)}小时{int(minutes)}分钟{int(seconds)}秒"

# 监控文件夹的函数
def monitor_folder(item):
    global result_set,media_set,error_set,dir_set,TELEGRAM_BOT_TOKEN,TELEGRAM_CHAT_ID,TELEGRAM_API_URL
    #print(f"Monitoring {item}")
    parts = item.split('|')
    source_dir =  parts[0]
    #logger.info(f"source_dir为{source_dir}")
    library_dir = parts[1]
    #logger.info(f"library_dir为{library_dir}")
    strm_dir = parts[2]
    docker_dir = parts[3]
    cloud_dir = parts[4]
    path_layers = int(parts[5])
    #logger.info(f"path_layers为{path_layers}")
    path_delete = parts[6]
    #logger.info("路径设置完毕")

    while True:  
        check_and_rotate_log()          
        start_time = time.time()  # 记录开始时间
        log_time = time.strftime("%Y%m%d-%H%M%S")  
        #with ThreadPoolExecutor(max_workers=8) as executor:  # 假设最多4个线程  
        for root, dirs, files in os.walk(source_dir):
            if files:
                for file in files:  
                    file_path = os.path.join(root, file)  
                    process_file(file_path,source_dir,strm_dir,docker_dir,library_dir,cloud_dir,path_layers,path_delete)
                    logger.info(f"新增文件{file}处理完成")
                        #send_telegram_notification(f"新增文件{file}处理完成")
        #executor.shutdown(wait=True)
        end_time = time.time()  # 记录结束时间  
        total_time = end_time - start_time  # 计算总运行时间
        formatted_time = format_time(total_time)  # 格式化总运行时间
        cleanup_old_logs()   
        #logger.info(f"新增文件处理完成，总共用了 {formatted_time}。")                
        #logger.info("脚本输出:")
        #logger.info(result.stdout)
        #开始扫库
        # 判断 result_set 是否有内容
        if result_set:
            #logger.info(f"{result_set}")error_set
            if error_set:
                errors = "\n".join(sorted(error_set))
                logger.info(f"移动文件时出错:\n{errors}\n")
            else:
                logger.info(f"大吉大利")
            #send_telegram_notification(f"移动文件时出错: {errors}")
            if path_delete == 'true':
                delete_directories_at_level(source_dir, path_layers)
                logger.info(f"已清理目录残留")
            emby_refresh = EmbyRefresh(EMBY_API_KEY, EMBY_SERVER_URL)
            emby_refresh.refresh_library()
            logger.info("完成emby刷新通知.")
            media = "\n".join(sorted(media_set))
            logger.info(f"\n新增媒体：\n\n{media}\n\n处理完成\n")
            
            send_telegram_notification(f"\n新增媒体：\n\n{media}\n\n处理完成\n")    
        result_set=set()
        media_set=set() 
        error_set=set()           
        time.sleep(5)
        # 更新初始文件列表

def main():
    # 为集合中的每个项目启动一个线程  
    threads = []  
    for item in dir_set:  
        # 创建一个Thread对象，target参数指定线程要执行的函数，args参数是传递给该函数的元组  
        thread = threading.Thread(target=monitor_folder, args=(item,), name=f"Thread-{item}")  
        # 将线程添加到列表中，以便稍后可以等待它们完成  
        threads.append(thread)  
        # 启动线程  
        thread.start()  
  
    # 等待所有线程完成  
    for thread in threads:  
        thread.join()      

if __name__ == "__main__":   
    # 启动文件夹监控
    main()  
