FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY botkernel botkernel
RUN pip install --no-cache-dir .
COPY . .
CMD ["uvicorn","botkernel.api:app","--host","0.0.0.0"]
