# sterling312/logtail
#
FROM sterling312/base

MAINTAINER Gang Huang doc.n.try@gmail.com

COPY . /logtail
RUN pip install -r /logtail/requirements.txt
RUN chmod +x /logtail/startup.sh

ENTRYPOINT /logtail/startup.sh

EXPOSE 8000 6379
