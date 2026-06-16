FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tietokanta/ tietokanta/
COPY llm/ llm/
COPY kehoteet/ kehoteet/
COPY webui/ webui/

EXPOSE 12121

CMD ["uvicorn", "webui.palvelin:sovellus", "--host", "0.0.0.0", "--port", "12121"]
