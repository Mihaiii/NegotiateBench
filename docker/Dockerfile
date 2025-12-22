FROM python:3-slim

RUN apt-get update && apt-get install -y git gcc build-essential

COPY script.sh .

RUN chmod +x ./script.sh
RUN chmod 777 .

RUN git clone https://github.com/Mihaiii/NegotiateBench.git
RUN cd NegotiateBench && pip install -r requirements.txt
RUN chmod 777 ./NegotiateBench

CMD ["./script.sh"]