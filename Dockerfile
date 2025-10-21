FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
&& apt-get install -y --no-install-recommends python3 python3-pip ca-certificates curl software-properties-common -y \
&& add-apt-repository ppa:heyarje/makemkv-beta -y \
&& apt-get update \
&& apt-get install eject makemkv-bin makemkv-oss ffmpeg abcde cdparanoia python3 python3-pyquery flac -y  \
&& rm -rf /var/lib/apt/lists/*

COPY . /opt/rippa
COPY ./makemkv.settings.conf /root/.MakeMKV/settings.conf

VOLUME ["/app"]
WORKDIR /app

# Update MakeMKV key during build to allow image use without network access
RUN python3 /opt/rippa/makemkvkey.py

CMD ["python3", "/opt/rippa/rippa.py"]