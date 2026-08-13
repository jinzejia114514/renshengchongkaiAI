FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 创建 session 存储目录
RUN mkdir -p .sessions

# 暴露端口（与 config.json 的 app.port 保持一致）
EXPOSE 3000

# 启动
CMD ["python", "app.py"]
