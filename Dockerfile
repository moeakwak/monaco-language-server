# syntax=docker/dockerfile:1
FROM python:3.9-slim-bullseye
EXPOSE 3000

RUN apt-get update
RUN apt-get -y install ccls
RUN apt-get -y install clang-format
# RUN apt-get -y clang
# RUN apt-get -y clangd
RUN apt-get -y install vim

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY ./app .
RUN mkdir log
CMD ["python3", "server.py"]