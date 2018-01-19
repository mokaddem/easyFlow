#!/usr/bin/env python3.5
# -*-coding:UTF-8 -*
import sys, os
sys.path.append(os.environ['FLOW_HOME'])

from process_no_input import Process_no_input
import time
import socket, zmq, redis

class Remote_input(Process_no_input):
    def generate_data(self):
        remote_protocol = self.custom_config['remote_protocol']
        host = self.custom_config['remote_host']
        port = self.custom_config['remote_port']
        self.logger.info('Trying to listen on (%s, %s)', host, port)

        if remote_protocol == 'socket':
            sock = None
            for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                              socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
                af, socktype, proto, canonname, sa = res
                try:
                    sock = socket.socket(af, socktype, proto)
                except OSError as msg:
                    self.logger.error('Socket creation error', exc_info=True)
                    self.state = 'crashed'
                    sock = None
                    continue
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(sa)
                    self.custom_message = 'Listening on {}'.format(sa)
                    sock.listen(1)
                except OSError as msg:
                    self.logger.error('Socket binding/listening error', exc_info=True)
                    sock.close()
                    sock = None
                    self.state = 'crashed'
                    continue
                break
            if sock is None:
                self.logger.error('Could not open socket')
                self.state = 'crashed'
                # sys.exit(1)
                return
            self.logger.info('Listening on socket')
            while True:
                conn, addr = sock.accept()
                with conn:
                    self.logger.info('Connected by %s', addr)
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            self.logger.info('No data, sleeping %s sec', self.custom_config['sleepTime'])
                            time.sleep(self.custom_config['sleepTime'])
                            break
                        remote_message = data.decode('utf8')
                        self.forward(remote_message)

        elif remote_protocol == 'ZMQ':
            context = zmq.Context()
            sock = context.socket(zmq.SUB)
            sock.connect('tcp://{host}:{port}'.format(host=host, port=port))
            topic = self.custom_config.get('zmq_topic', '')
            sock.setsockopt_string(zmq.SUBSCRIBE, topic)
            self.logger.info('Listen on topic %s', topic)

            while True:
                data = sock.recv()
                remote_message = data.decode('utf8')
                self.forward(remote_message)


        elif remote_protocol == 'redis_pubsub':
            db = self.custom_config.get('redis_db', 0)
            channel = self.custom_config.get('redis_channel', '')
            r_serv = redis.StrictRedis(host, port, db)
            pubsub = r_serv.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel)
            self.logger.info('Listen on channel %s', channel)
            for data in pubsub.listen():
                remote_message = data['data'].decode('utf8')
                self.forward(remote_message)

        else:
            self.logger.error('Unknown remote protocol %s', remote_protocol)


if __name__ == '__main__':
    uuid = sys.argv[1]
    p = Remote_input(uuid)
