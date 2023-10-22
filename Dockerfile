FROM debian:latest

RUN apt-get update -qq && apt-get install git cmake build-essential python3 python3-pip python3.11-venv libclang1-15 libclang-dev libpcap-dev -yy

WORKDIR /atdecc

COPY . .

# activate venv
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install -r requirements.txt
RUN pip freeze > requirements.txt
RUN make clean && make

ENV LD_LIBRARY_PATH=/atdecc/src
CMD ["/atdecc/src/atdecc.py", "-d"]
