FROM lambci/lambda:build-python3.8

WORKDIR /tmp

# We install rezoning_api and mangum

COPY README.md /app/README.md
COPY rezoning_api/ /app/rezoning_api/
COPY setup.py /app/setup.py 
RUN pip install /app/. "mangum>=0.9.0" -t /var/task --no-binary numpy

# Reduce package size and remove useless files
RUN cd /var/task && find . -type f -name '*.pyc' | while read f; do n=$(echo $f | sed 's/__pycache__\///' | sed 's/.cpython-[2-3][0-9]//'); cp $f $n; done;
RUN cd /var/task && find . -type d -a -name '__pycache__' -print0 | xargs -0 rm -rf
RUN cd /var/task && find . -type f -a -name '*.py' -print0 | xargs -0 rm -f
RUN find /var/task -type d -a -name 'tests' -print0 | xargs -0 rm -rf
RUN rm -rdf /var/task/numpy/doc/
RUN rm -rdf /var/task/stack

# boto3 and botocore are installed on python lambda images, and botocore is gigantic (78M unzipped, 1/5 of size budget)
RUN rm -rf /var/task/boto3* /var/task/botocore*

RUN cd /var/task && zip -r9q /tmp/package.zip *

COPY lambda/handler.py handler.py
RUN zip -r9q /tmp/package.zip handler.py
