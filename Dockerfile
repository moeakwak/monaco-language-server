# syntax=docker/dockerfile:1

FROM python:3.9-bullseye

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY ./app .
CMD [ "python3", "server.py"]