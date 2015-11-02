FROM infoshift/python

RUN pip install flask==0.10.1
RUN pip install redis==2.10.3
RUN pip install gevent==1.0.1
RUN pip install boto==2.38.0
RUN pip install flask-sqlalchemy==2.0.0
RUN pip install pymysql==0.6.6
RUN pip install simplejson==3.7.3
RUN pip install flask-script==2.0.5
RUN pip install flask-migrate==1.4.0
RUN pip install requests==2.7.0
RUN pip install gunicorn==19.3.0
