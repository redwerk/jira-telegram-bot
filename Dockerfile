FROM alpine:3.6

RUN apk add --update --no-cache git build-base bash python3 python3-dev ca-certificates libffi-dev openssl-dev && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache


ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt --src /usr/local/src
