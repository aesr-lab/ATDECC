FROM debian:latest

RUN apt-get update -qq && apt-get install git cmake build-essential python3 python3-pip python3.11-venv libclang1-15 libclang-dev libpcap-dev -yy

WORKDIR /atdecc

COPY . .

RUN python3 -m venv venv
RUN /bin/bash -c "source venv/bin/activate && pip install -r requirements.txt && pip freeze > requirements.txt"
RUN /bin/bash -c "source venv/bin/activate && make clean && make"
