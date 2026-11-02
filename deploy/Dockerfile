FROM python:3.11-slim
WORKDIR /app
COPY coordinator.py node.py skills.py corpus.py ./
EXPOSE 8765
CMD ["sh", "-c", "python3 coordinator.py 8765 \"$TOKEN\""]
