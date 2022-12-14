FROM alpine:3.16

RUN apk add --no-cache python3-dev \
    && apk add cmd:pip3 \
    && pip3 install --upgrade pip

WORKDIR /app

COPY . /app

RUN pip3 --no-cache-dir install -r requirements.txt

EXPOSE 5000

CMD ["python3", "src/app.py"]

