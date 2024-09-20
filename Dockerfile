# 使用官方 Python 运行时作为父镜像  
FROM python:3-alpine
  
# 设置工作目录  
WORKDIR /app  
  
# 将当前目录内容复制到位于 /app 中的容器中  
COPY . /app
RUN chmod +x /app/ssjk.py
  
# 安装 requirements.txt 中指定的任何依赖
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt  
RUN apk update && apk add --no-cache tzdata 
ENV TZ=Asia/Shanghai  
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
  
# 让容器监听端口 5000  
EXPOSE 5432
  
# 定义环境变量  
ENV NAME World  
  
# 在容器启动时运行 Flask 应用  
ENTRYPOINT ["python3"]
CMD ["/app/ssjk.py"]
