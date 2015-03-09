FROM infoshift/python

RUN pip install flask==0.10.1
RUN pip install redis==2.10.3
RUN pip install gevent==1.0.1
