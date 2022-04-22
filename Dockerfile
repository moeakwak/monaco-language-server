# syntax=docker/dockerfile:1

FROM python:3.9-slim-bullseye

RUN apt-get update
RUN apt-get -y install ccls

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY ./app .
CMD [ "python3", "server.py"]