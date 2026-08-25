FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# ATENÇÃO: --workers 1 é obrigatório.
# O asyncio.Semaphore de rate limiting da IA é por-processo (não distribuído).
# Múltiplos workers multiplicariam o limite de 10 slots por N workers.
# Para escalar horizontalmente, adicione mais réplicas do container no Cloud Run,
# não adicione workers dentro do mesmo container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
