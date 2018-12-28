FROM python:3.6
ADD . /code
WORKDIR /code
COPY requirements/base.txt /code/requirements.txt
RUN pip install -r requirements.txt
