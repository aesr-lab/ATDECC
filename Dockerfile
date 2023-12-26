FROM debian:latest

RUN apt-get update -qq && apt-get install git cmake build-essential python3 python3-dev python3-pip python3-venv clang libclang-dev libpcap-dev -yy

WORKDIR /atdecc

COPY . .

# activate venv
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install -r requirements.txt
#RUN pip freeze > requirements.txt

# Make project
RUN make clean && make -j$(nproc)
# Install in developer mode
RUN pip install -e .

# Start daemon in debug mode
CMD ["atdecc-py", "-d", "-c", "./tests/fixtures/config.yml" ]
