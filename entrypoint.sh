#!/bin/bash  
  
# 检查文件是否存在  
if [ ! -f ./config/config.yaml ]; then  
    echo "File does not exist, copying from backup"  
    cp ./backup/config.yaml.bak ./config/config.yaml
fi  
  
# 现在可以运行你的应用  
exec python3 /app/ssjk.py
