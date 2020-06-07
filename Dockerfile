FROM python:3.8-slim-buster
WORKDIR /app
COPY app.py requirements.txt version.txt ./
RUN pip install -r requirements.txt
ENTRYPOINT ["python", "app.py"]
CMD ["-c", "config.toml"]
