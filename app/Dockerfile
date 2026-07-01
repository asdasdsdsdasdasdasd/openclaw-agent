FROM python:3.12-slim

# No extra OS packages — keep attack surface minimal
WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Non-root user
RUN useradd -m -u 1000 openclaw
USER openclaw

EXPOSE 8080

CMD ["python", "main.py"]
