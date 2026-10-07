FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tietokanta/ tietokanta/
COPY luokittelu/ luokittelu/
COPY llm/ llm/
COPY arviointi/ arviointi/
COPY raportti/ raportti/
COPY kehotteet/ kehotteet/
COPY webui/ webui/
COPY Opserver.md .

# Ajossa oleva versio infomodaaliin ("<commit> <päivä>"; ./asenna antaa). Viimeisenä,
# ettei joka commitin uusi arvo mitätöi pip-kerroksen välimuistia.
ARG OPSERVER_VERSIO=""
ENV OPSERVER_VERSIO=$OPSERVER_VERSIO

EXPOSE 12121

CMD ["uvicorn", "webui.palvelin:sovellus", "--host", "0.0.0.0", "--port", "12121"]
