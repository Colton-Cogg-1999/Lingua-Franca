FROM python:3.14-slim
WORKDIR /app
COPY pyproject.toml ./
COPY galapagos ./galapagos
RUN pip install --no-cache-dir .
ENTRYPOINT ["python", "-m", "galapagos"]
CMD ["--output", "/data/run"]
