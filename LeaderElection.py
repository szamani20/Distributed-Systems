import socket
import threading
from time import sleep
import json

import sys

BASE_PORT = 5000
ELECTION_MESSAGE = 'ELECTION'
LEADER_ADVERTISEMENT = 'I AM LEADER'


class Message:
    def __init__(self, message_type, value):
        self.message_type = message_type
        self.value = value

    def __str__(self):
        return '{} {}'.format(self.message_type, self.value)


class Process:
    def __init__(self, uid, sending_port, receiving_port, delay):
        self.receiver_socket = socket.socket()
        self.sender_socket = socket.socket()
        self.sending_port = sending_port
        self.delay = delay
        self.uid = uid
        self.participant = False
        self.leader = False
        self.leader_uid = None
        threading.Thread(target=self.init_receiver_socket, args=(socket.gethostname(), receiving_port)).start()

    def init_receiver_socket(self, receive_host, receive_port):
        self.receiver_socket.bind((receive_host, receive_port))
        self.receiver_socket.listen(1)
        sender_connection_socket, address = self.receiver_socket.accept()

        while True:
            data = sender_connection_socket.recv(1024).decode()
            if not data:
                break
            m = Message(**json.loads(data, encoding='utf-8'))

            print('in node {} received'.format(self.uid), m)

            if m.message_type == ELECTION_MESSAGE and not self.leader:
                if m.value > self.uid:
                    self.send_data(m)
                elif m.value < self.uid and not self.participant:
                    self.send_data(Message(ELECTION_MESSAGE, self.uid))
                elif m.value < self.uid and self.participant:
                    continue
                elif m.value == self.uid:
                    self.leader = True
                    self.leader_uid = self.uid
                    self.send_data(Message(LEADER_ADVERTISEMENT, self.uid), False)
            elif m.message_type == LEADER_ADVERTISEMENT and not self.leader:
                self.leader_uid = m.value
                self.send_data(m, False)
            elif m.message_type == LEADER_ADVERTISEMENT and self.leader:
                print('Election is over. Leader UID is {}'.format(self.uid))
                self.close_sockets()

    def init_sender_socket(self):
        self.sender_socket.connect((socket.gethostname(), self.sending_port))

    def send_data(self, message, participant=True):
        threading.Thread(target=self._send_data, args=(message, participant)).start()

    def _send_data(self, message, participant):
        # print('in node {} and time {} sending'.format(self.uid, TOTAL_DELAY), message)
        sleep(self.delay)
        self.participant = participant
        self.sender_socket.sendall(json.dumps(message.__dict__).encode('utf-8'))

    def close_sockets(self):
        self.receiver_socket.close()
        self.sender_socket.close()
        # sys.exit(0)


if __name__ == '__main__':
    size = int(input())
    processes = []
    for i in range(size):
        spec = input().split(' ')
        processes.append(Process(spec[0],
                                 BASE_PORT + i,
                                 BASE_PORT + i - 1 if i != 0 else BASE_PORT + size - 1,
                                 float(spec[1])))
    [p.init_sender_socket() for p in processes]
    for p in processes:
        p.send_data(Message(ELECTION_MESSAGE, p.uid))
