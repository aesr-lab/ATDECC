FROM debian:latest

RUN apt-get update -qq && apt-get install git cmake build-essential python3 python3-dev python3-pip python3-venv clang libclang-dev libpcap-dev build-essential -yy

WORKDIR /atdecc

COPY . .

# activate venv
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install -r requirements.txt
RUN pip freeze > requirements.txt

WORKDIR /atdecc/src/atdecc

RUN make clean && make

WORKDIR /atdecc

COPY ./tests/fixtures/config.yml /etc/atdecc/config.yml

ENV LD_LIBRARY_PATH=/atdecc/src/atdecc
CMD ["/atdecc/src/atdecc/atdecc.py", "-d"]
